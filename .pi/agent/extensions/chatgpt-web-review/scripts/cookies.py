# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""Extract ChatGPT session cookies from the local Firefox profile.

Default (human-safe) mode prints cookie *names and value lengths* only — never
values. Use ``--emit-json`` to print a JSON object (consumed by review.py via a
controlled subprocess; do not pipe this into a terminal/log you share).

Resolves the Firefox profile that actually holds the ChatGPT session by scanning
moz_cookies across all profiles, then reassembles the chunked
``__Secure-next-auth.session-token`` JWT (NextAuth splits it across .0/.1/...
when it exceeds the 4 KB cookie limit).
"""

from __future__ import annotations

import argparse
import configparser
import json
import os
import shutil
import sqlite3
import sys
import tempfile
from pathlib import Path

# Hosts that carry the ChatGPT session/backbone cookies.
HOST_FRAGMENTS = ("chatgpt.com", "openai.com", "auth0.openai.com")
SESSION_TOKEN_BASE = "__Secure-next-auth.session-token"


def _firefox_roots() -> list[Path]:
    """Return platform-specific Firefox configuration roots.

    ``FIREFOX_PROFILE_ROOT`` can override discovery for portable, Developer
    Edition, or otherwise non-standard installations.
    """
    override = os.environ.get("FIREFOX_PROFILE_ROOT")
    if override:
        return [Path(override).expanduser()]

    home = Path.home()
    roots: list[Path] = []
    if sys.platform == "darwin":
        roots.append(home / "Library" / "Application Support" / "Firefox")
    elif os.name == "nt":
        appdata = os.environ.get("APPDATA")
        if appdata:
            roots.append(Path(appdata) / "Mozilla" / "Firefox")
    else:
        roots.extend([
            home / ".mozilla" / "firefox",
            home / "snap" / "firefox" / "common" / ".mozilla" / "firefox",
            home / ".var" / "app" / "org.mozilla.firefox" / ".mozilla" / "firefox",
        ])

    return [root for root in roots if root.exists()]


def _scan_profiles() -> list[Path]:
    """Return candidate profile directories from profiles.ini + filesystem."""
    candidates: list[Path] = []
    defaults: set[str] = set()
    seen: set[str] = set()

    for firefox_dir in _firefox_roots():
        ini = firefox_dir / "profiles.ini"
        if ini.exists():
            cp = configparser.ConfigParser()
            try:
                cp.read(ini)
            except configparser.Error:
                cp = configparser.ConfigParser()
            for section in cp.sections():
                if not section.lower().startswith("profile"):
                    continue
                path = cp.get(section, "Path", fallback=None)
                rel = cp.getboolean(section, "IsRelative", fallback=True)
                if not path:
                    continue
                profile = (firefox_dir / path) if rel else Path(path).expanduser()
                key = str(profile.resolve())
                if profile.is_dir() and key not in seen:
                    seen.add(key)
                    candidates.append(profile)
                if cp.getboolean(section, "Default", fallback=False):
                    defaults.add(key)

        # Fallback for incomplete or missing profiles.ini files. macOS normally
        # stores profiles below Firefox/Profiles; Linux commonly stores them
        # directly below the Firefox root.
        for cookie_db in sorted(firefox_dir.glob("**/cookies.sqlite")):
            profile = cookie_db.parent
            key = str(profile.resolve())
            if key not in seen:
                seen.add(key)
                candidates.append(profile)

    # Put profiles declared as default first without disturbing root order.
    candidates.sort(key=lambda profile: str(profile.resolve()) not in defaults)
    return candidates


def _read_cookies_from_profile(profile: Path) -> list[dict]:
    """Copy cookies.sqlite (+wal/shm) to a temp dir and query moz_cookies."""
    src = profile / "cookies.sqlite"
    if not src.exists():
        return []
    tmp = Path(tempfile.mkdtemp(prefix="ffcookies-"))
    try:
        dst = tmp / "c.sqlite"
        shutil.copy2(src, dst)
        for ext in ("-wal", "-shm"):
            w = profile / f"cookies.sqlite{ext}"
            if w.exists():
                shutil.copy2(w, tmp / f"c.sqlite{ext}")
        rows: list[dict] = []
        # read-only, short timeout in case of residual lock.
        con = sqlite3.connect(f"file:{dst}?mode=ro", uri=True, timeout=2.0)
        try:
            con.row_factory = sqlite3.Row
            cur = con.execute(
                "SELECT name, value, host, path, expiry, isSecure, isHttpOnly, "
                "sameSite, originAttributes FROM moz_cookies"
            )
            for r in cur.fetchall():
                rows.append(dict(r))
        finally:
            con.close()
        return rows
    except sqlite3.Error as e:
        print(f"[cookies] sqlite error reading {profile.name}: {e}", file=sys.stderr)
        return []
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _profile_with_chatgpt() -> tuple[Path, list[dict]]:
    """Scan all profiles; return the one with the most ChatGPT cookies + its rows."""
    best: tuple[Path, list[dict]] | None = None
    best_hits = -1
    for prof in _scan_profiles():
        rows = _read_cookies_from_profile(prof)
        hits = sum(1 for r in rows if any(f in (r.get("host") or "") for f in HOST_FRAGMENTS))
        if hits > best_hits:
            best_hits = hits
            best = (prof, rows)
        names = sorted({r["name"] for r in rows if any(f in (r.get("host") or "") for f in HOST_FRAGMENTS)})
        print(
            f"[cookies] profile={prof.name} total={len(rows)} chatgpt_hits={hits}",
            file=sys.stderr,
        )
        if names:
            print(f"[cookies]   names: {', '.join(names)}", file=sys.stderr)
    if not best:
        raise SystemExit("[cookies] no Firefox profiles found")
    if best_hits <= 0:
        raise SystemExit(
            "[cookies] no ChatGPT cookies found in any profile — is the account "
            "logged in via this Firefox?"
        )
    return best


def _reassemble_session_token(rows: list[dict]) -> str | None:
    """Reassemble chunked __Secure-next-auth.session-token.{0,1,...} into one JWT."""
    chunks: dict[int, str] = {}
    whole: str | None = None
    for r in rows:
        name = r["name"]
        if name == SESSION_TOKEN_BASE:
            whole = r["value"]
        elif name.startswith(SESSION_TOKEN_BASE + "."):
            suffix = name[len(SESSION_TOKEN_BASE) + 1:]
            if suffix.isdigit():
                chunks[int(suffix)] = r["value"]
    if chunks:
        return "".join(chunks[i] for i in sorted(chunks))
    return whole


def _device_id(rows: list[dict]) -> str | None:
    for r in rows:
        if r["name"] == "oai-did":
            return r["value"]
    return None


def _chat_rows() -> tuple[Path, list[dict]]:
    profile, rows = _profile_with_chatgpt()
    chat_rows = [r for r in rows if any(f in (r.get("host") or "") for f in HOST_FRAGMENTS)]
    return profile, chat_rows


def build_playwright_cookies() -> list[dict]:
    """Return cookies in Playwright's context.add_cookies() format.

    Chunked __Secure-next-auth.session-token.{0,1,...} are emitted as separate
    cookies so NextAuth's chunked reader reassembles them server-side (do NOT
    merge here). Values are included — consume via subprocess, do not log.
    """
    _profile, chat_rows = _chat_rows()
    ss_map = {0: "None", 1: "Lax", 2: "Strict"}
    out: list[dict] = []
    for r in chat_rows:
        secure = bool(r.get("isSecure"))
        ss = ss_map.get(int(r.get("sameSite") or 0), "Lax")
        # Playwright rejects sameSite=None without secure; coerce to Lax.
        if ss == "None" and not secure:
            ss = "Lax"
        expiry_raw = int(r.get("expiry") or 0)
        cookie = {
            "name": r["name"],
            "value": r["value"],
            "domain": r["host"],
            "path": r.get("path") or "/",
            "secure": secure,
            "httpOnly": bool(r.get("isHttpOnly")),
            "sameSite": ss,
        }
        # Playwright wants expires in Unix SECONDS (float), or omitted for session
        # cookies. Firefox's moz_cookies.expiry was historically seconds but recent
        # versions store milliseconds; detect via magnitude (>1e11 => ms).
        if expiry_raw > 0:
            secs = expiry_raw / 1000.0 if expiry_raw > 100_000_000_000 else float(expiry_raw)
            cookie["expires"] = secs
        out.append(cookie)
    return out


def build_payload() -> dict:
    profile, chat_rows = _chat_rows()

    session_token = _reassemble_session_token(chat_rows)
    if not session_token:
        raise SystemExit(
            "[cookies] __Secure-next-auth.session-token not found — not logged in, "
            "or session expired. Log into chatgpt.com in Firefox first."
        )

    # Build a Cookie header from all session-relevant cookies. If the session
    # token was chunked, replace the chunk fragments with the reassembled value.
    parts: list[str] = []
    emitted: set[str] = set()
    for r in chat_rows:
        name = r["name"]
        if name.startswith(SESSION_TOKEN_BASE + ".") and name[len(SESSION_TOKEN_BASE) + 1:].isdigit():
            continue  # drop chunks; emit reassembled below
        if name in emitted:
            continue
        emitted.add(name)
        parts.append(f"{name}={r['value']}")
    # Session token under its canonical (un-suffixed) name.
    if SESSION_TOKEN_BASE not in emitted:
        parts.append(f"{SESSION_TOKEN_BASE}={session_token}")
        emitted.add(SESSION_TOKEN_BASE)

    cookie_header = "; ".join(parts)
    return {
        "profile": profile.name,
        "cookie_header": cookie_header,
        "session_token": session_token,
        "device_id": _device_id(chat_rows),
        "cookie_names": sorted(emitted),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--emit-json",
        action="store_true",
        help="Print the full JSON payload (includes cookie VALUES). For review.py only.",
    )
    ap.add_argument(
        "--emit-playwright",
        action="store_true",
        help="Print cookies as a JSON list in Playwright add_cookies() format (values included).",
    )
    ap.add_argument(
        "--debug",
        action="store_true",
        help="Print profile/cookie names + value lengths (values never shown).",
    )
    args = ap.parse_args()

    if args.emit_playwright:
        json.dump(build_playwright_cookies(), sys.stdout)
        sys.stdout.write("\n")
        return 0

    payload = build_payload()

    if args.emit_json:
        json.dump(payload, sys.stdout)
        sys.stdout.write("\n")
        return 0

    # Default + --debug: human-safe.
    print(f"profile: {payload['profile']}")
    print(f"device_id present: {bool(payload['device_id'])}")
    print(f"session_token length: {len(payload['session_token'])}")
    print(f"session_token looks like JWT (eyJ..): {payload['session_token'].startswith('eyJ')}")
    print(f"cookie count: {len(payload['cookie_names'])}")
    print("cookies:")
    # Lengths of each emitted cookie value from the header.
    for part in payload["cookie_header"].split("; "):
        if "=" in part:
            name, val = part.split("=", 1)
            print(f"  {name} (len={len(val)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

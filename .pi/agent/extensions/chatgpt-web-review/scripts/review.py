# /// script
# requires-python = ">=3.10"
# dependencies = ["httpx==0.27.2"]
# ///
"""Request a repo code review from ChatGPT via the logged-in web session.

Replays Firefox session cookies against ChatGPT's first-party backend API:
  session cookie -> /api/auth/session (access token)
  /backend-api/sentinel/chat-requirements (requirements + proof-of-work + arkose)
  /backend-api/files (zip upload -> file_id, DRIFT-PRONE; inline mode bypasses it)
  /backend-api/conversation (SSE stream -> review markdown)

By default the repository sources are inlined into the prompt as text (robust and
avoids the fragile file-upload endpoint). Fragile by design (reverse-engineered).
Always run --dry-run first to verify the handshake. See SKILL.md for caveats.

Usage:
    uv run scripts/review.py --repo /path/to/repo [--prompt "..."] [--model auto]
    uv run scripts/review.py --zip  /tmp/repo.zip [--dry-run] [--dump-events]
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import itertools
import json
import os
import random
import re
import subprocess
import sys
import time
import uuid
import zipfile
from pathlib import Path

import httpx

# Surfaced as a realistic Firefox/Linux client so cookies issued to Firefox have
# the best chance of being honored. NOTE: cf_clearance/__cf_bm are TLS-fingerprint
# bound; httpx's fingerprint differs from Firefox, so Cloudflare may still 403.
USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64; rv:128.0) Gecko/20100101 Firefox/128.0"
)
BASE = "https://chatgpt.com"
DEFAULT_PROMPT = (
    "Review the repository whose contents are provided below. Output a code "
    "review as markdown with these sections: Summary, Security, "
    "Bugs & Correctness, Architecture & Design, Maintainability, Performance, "
    "and Top Actionable Suggestions (prioritized, with file paths). Be specific "
    "and concise."
)


# --------------------------------------------------------------------------
# Cookies
# --------------------------------------------------------------------------

def load_cookies() -> dict:
    """Invoke the sibling cookies.py --emit-json and parse its payload."""
    cookies_py = Path(__file__).parent / "cookies.py"
    if not cookies_py.exists():
        raise SystemExit(f"[review] missing {cookies_py}")
    # cookies.py is stdlib-only, so the current interpreter (set up by uv) runs it.
    proc = subprocess.run(
        [sys.executable, str(cookies_py), "--emit-json"],
        capture_output=True, text=True,
    )
    if proc.returncode != 0:
        sys.stderr.write(proc.stderr)
        raise SystemExit("[review] cookie extraction failed (see above)")
    try:
        payload = json.loads(proc.stdout)
    except json.JSONDecodeError as e:
        raise SystemExit(f"[review] could not parse cookies.py output: {e}")
    sys.stderr.write(
        f"[review] cookies: profile={payload.get('profile')} "
        f"device_id={'yes' if payload.get('device_id') else 'NO'} "
        f"cookies={len(payload.get('cookie_names', []))}\n"
    )
    return payload


# --------------------------------------------------------------------------
# Auth + requirements
# --------------------------------------------------------------------------

def _common_headers(cookie_header: str, device_id: str | None, bearer: str | None = None) -> dict:
    h = {
        "User-Agent": USER_AGENT,
        "Accept-Language": "en-US,en;q=0.9",
        "Cookie": cookie_header,
        "Origin": BASE,
        "Referer": BASE + "/",
        "oai-language": "en-US",
    }
    if device_id:
        h["oai-device-id"] = device_id
    if bearer:
        h["Authorization"] = f"Bearer {bearer}"
    return h


def get_access_token(client: httpx.Client, cookie_header: str, device_id: str | None) -> str:
    r = client.get(
        f"{BASE}/api/auth/session",
        headers=_common_headers(cookie_header, device_id),
    )
    if r.status_code != 200:
        raise SystemExit(
            f"[review] /api/auth/session -> {r.status_code}: {r.text[:300]}. "
            f"Session cookie likely expired or Cloudflare blocked the client."
        )
    data = r.json()
    token = data.get("accessToken")
    if not token:
        raise SystemExit(
            f"[review] /api/auth/session returned no accessToken: {json.dumps(data)[:300]}. "
            f"Not logged in (re-log into chatgpt.com in Firefox)."
        )
    sys.stderr.write("[review] access token obtained\n")
    return token


def chat_requirements(client: httpx.Client, cookie_header: str, device_id: str | None,
                      access_token: str) -> dict:
    r = client.post(
        f"{BASE}/backend-api/sentinel/chat-requirements",
        headers={**_common_headers(cookie_header, device_id, access_token),
                 "Content-Type": "application/json"},
        json={},  # some accounts need {"p": <arkose>}; left empty for the dry-run path.
    )
    if r.status_code != 200:
        raise SystemExit(
            f"[review] chat-requirements -> {r.status_code}: {r.text[:300]}"
        )
    data = r.json()
    pow_info = data.get("proofofwork") or {}
    arkose = data.get("arkose") or {}
    sys.stderr.write(
        f"[review] chat-requirements: token={'yes' if data.get('token') else 'NO'} "
        f"pow.required={pow_info.get('required')} "
        f"arkose.required={arkose.get('required')}\n"
    )
    return data


# --------------------------------------------------------------------------
# Proof-of-work  (best-effort, reverse-engineered — the most likely failure point)
# --------------------------------------------------------------------------

def solve_pow(seed: str, difficulty: str, user_agent: str) -> str:
    """Best-effort sentinel PoW. Returns the `openai-sentinel-proof-token` value.

    The exact algorithm has changed repeatedly and is not documented. This
    implements the widely-published 2024 shape: find a nonce so that
    sha3_512(seed + prefix + base64(config,nonce)) is lexicographically <= the
    difficulty string over its leading chars. If ChatGPT rejects this (401/403 on
    /conversation), inspect the real seed/difficulty via --dry-run and adjust.
    """
    if not seed or not difficulty:
        return ""
    cores = random.choice([4, 8, 12, 16])
    screen = random.choice([1920, 2560, 3840])
    now = {"time": int(time.time())}
    config = [
        screen, 2560, 24, cores,
        f"{BASE}/",  # locale-ish
        now,
    ]
    prefix = "gAAAAAB"
    diff_len = len(difficulty)
    target = difficulty
    for nonce in itertools.count():
        payload = json.dumps([config, nonce], separators=(",", ":")).encode()
        candidate = prefix + base64.b64encode(payload).decode()
        digest = hashlib.sha3_512((seed + candidate).encode()).hexdigest()
        if digest[:diff_len] <= target:
            return candidate
        if nonce > 2_000_000:
            raise SystemExit("[review] PoW: gave up after 2M iterations (difficulty too high / algorithm wrong)")
    return ""


# --------------------------------------------------------------------------
# File upload
# --------------------------------------------------------------------------

def _find_file_id(obj: dict) -> str | None:
    """Hunt for a file id under several known response shapes."""
    if isinstance(obj, dict):
        for k in ("file_id", "id"):
            v = obj.get(k)
            if isinstance(v, str) and v:
                return v
        if isinstance(obj.get("file"), dict):
            return _find_file_id(obj["file"])
        if isinstance(obj.get("data"), dict):
            return _find_file_id(obj["data"])
    return None


def upload_zip(client: httpx.Client, cookie_header: str, device_id: str | None,
               access_token: str, zip_path: Path) -> str:
    data = zip_path.read_bytes()
    r = client.post(
        f"{BASE}/backend-api/files",
        headers={**_common_headers(cookie_header, device_id, access_token)},
        files={"file": ("repo.zip", data, "application/zip")},
        data={"purpose": "fileapi"},  # best-effort; field may differ across versions
    )
    if r.status_code not in (200, 201):
        raise SystemExit(
            f"[review] /backend-api/files -> {r.status_code}: {r.text[:300]}. "
            f"The upload endpoint shape may have changed."
        )
    try:
        body = r.json()
    except Exception:
        raise SystemExit(f"[review] /backend-api/files returned non-JSON: {r.text[:300]}")
    file_id = _find_file_id(body)
    if not file_id:
        raise SystemExit(
            f"[review] could not find file_id in upload response: {json.dumps(body)[:300]}"
        )
    sys.stderr.write(f"[review] uploaded zip -> file_id={file_id} bytes={len(data)}\n")
    return file_id


# --------------------------------------------------------------------------
# Conversation (SSE)
# --------------------------------------------------------------------------

def _extract_text(obj: dict, acc_delta: list[str]) -> str | None:
    """Tolerantly extract the *current full* assistant text from an SSE event.

    Returns the full replacement text if the event carries `message.content.parts`,
    or None (appending delta into acc_delta if a delta field is present).
    Two known shapes:
      v1: {"v": {"message": {"content": {"parts": ["full text..."]}, "status": ...}}}
      delta: {"v": {"delta": "chunk"}} or {"p": <json-with-message>}
    """
    v = obj.get("v") if isinstance(obj, dict) else None
    # replacement form
    candidates = []
    if isinstance(v, dict):
        candidates.append(v.get("message"))
    candidates.append(obj.get("message"))
    for msg in candidates:
        if isinstance(msg, dict):
            content = msg.get("content")
            if isinstance(content, dict):
                parts = content.get("parts")
                if isinstance(parts, list) and parts:
                    last = parts[-1]
                    if isinstance(last, str) and last:
                        return last
            author = msg.get("author") or {}
    # delta form
    if isinstance(v, dict) and isinstance(v.get("delta"), str):
        acc_delta.append(v["delta"])
        return None
    # nested "p" json
    p = obj.get("p")
    if isinstance(p, str):
        try:
            inner = json.loads(p)
            return _extract_text(inner, acc_delta)
        except json.JSONDecodeError:
            return None
    return None


def send_conversation(client: httpx.Client, headers: dict, payload: dict,
                      dump_events: bool) -> str:
    last_full: str | None = None
    delta: list[str] = []
    done = False
    with client.stream("POST", f"{BASE}/backend-api/conversation",
                       headers=headers, json=payload, timeout=None) as r:
        if r.status_code != 200:
            body = r.read().decode(errors="replace")
            raise SystemExit(
                f"[review] /backend-api/conversation -> {r.status_code}: {body[:400]}"
            )
        for raw in r.iter_lines():
            if not raw:
                continue
            if dump_events:
                sys.stderr.write("EV " + raw[:500] + "\n")
            if not raw.startswith("data:"):
                continue
            data = raw[len("data:"):].strip()
            if data == "[DONE]":
                done = True
                break
            try:
                obj = json.loads(data)
            except json.JSONDecodeError:
                continue
            if not isinstance(obj, dict):
                continue
            full = _extract_text(obj, delta)
            if full:
                last_full = full
            # end markers
            v = obj.get("v")
            if isinstance(v, dict):
                msg = v.get("message") or {}
                if isinstance(msg, dict) and msg.get("status") == "finished_successfully":
                    done = True
            if done:
                break
    if last_full:
        return last_full
    if delta:
        return "".join(delta)
    raise SystemExit(
        "[review] conversation ended with no extracted text. Re-run with --dump-events "
        "to inspect the SSE shape (it has likely changed)."
    )


# --------------------------------------------------------------------------
# Inline bundle (robust alternative to file upload)
# --------------------------------------------------------------------------

def build_inline_bundle(zip_path: Path, per_file_cap: int = 20000,
                         total_cap: int = 120_000) -> str:
    """Concatenate text entries from the safety-scanned zip into a prompt bundle."""
    out: list[str] = []
    total = 0
    nfiles = 0
    with zipfile.ZipFile(zip_path) as z:
        for info in z.infolist():
            if info.is_dir():
                continue
            nfiles += 1
            try:
                text = z.read(info.filename).decode("utf-8")
            except (UnicodeDecodeError, KeyError, OSError):
                out.append(f"\n=== {info.filename} (non-text, skipped) ===")
                continue
            if len(text) > per_file_cap:
                text = text[:per_file_cap] + f"\n... [truncated, {len(text)} bytes total]"
            if total + len(text) > total_cap:
                text = text[: max(0, total_cap - total)]
                out.append(f"\n=== {info.filename} ===\n{text}\n[total cap reached; further files omitted]")
                total += len(text)
                break
            out.append(f"\n=== {info.filename} ===\n{text}")
            total += len(text)
    return f"# Repository contents ({nfiles} files)\n" + "\n".join(out)


# --------------------------------------------------------------------------
# Orchestration
# --------------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--repo", help="Repository to zip & review (mutually exclusive with --zip).")
    ap.add_argument("--zip", help="Use an existing zip file instead of zipping a repo.")
    ap.add_argument("--prompt", default=DEFAULT_PROMPT, help="Review prompt to send.")
    ap.add_argument("--model", default="auto", help="ChatGPT model slug (auto, gpt-5, gpt-4o, ...).")
    ap.add_argument("--dry-run", action="store_true",
                    help="Stop after chat-requirements and print the handshake verdict.")
    ap.add_argument("--mode", choices=["inline", "attach", "none"], default="inline",
                    help="inline: embed sources as text in the prompt (default, robust). "
                         "attach: upload zip + reference file_id (drift-prone). "
                         "none: plain prompt, no sources (use for handshake tests).")
    ap.add_argument("--dump-events", action="store_true",
                    help="Print every SSE line for debugging the parser.")
    args = ap.parse_args()

    if args.dry_run and args.repo and not args.zip:
        pass  # dry-run still needs cookies + access token + requirements; skip upload/send
    if not args.repo and not args.zip:
        ap.error("one of --repo or --zip is required")

    # 1. cookies
    cookies = load_cookies()
    cookie_header = cookies["cookie_header"]
    device_id = cookies.get("device_id")

    # zip (unless --zip given)
    if args.zip:
        zip_path = Path(args.zip).expanduser().resolve()
        if not zip_path.is_file():
            raise SystemExit(f"[review] zip not found: {zip_path}")
    else:
        zip_repo_py = Path(__file__).parent / "zip_repo.py"
        proc = subprocess.run(
            [sys.executable, str(zip_repo_py), str(Path(args.repo).expanduser().resolve())],
            capture_output=True, text=True,
        )
        sys.stderr.write(proc.stderr)
        if proc.returncode != 0:
            raise SystemExit(f"[review] zip_repo failed (exit {proc.returncode})")
        zip_path = Path(proc.stdout.strip().splitlines()[-1])

    # 2. session cookie -> access token
    with httpx.Client(http2=False, follow_redirects=True, timeout=30.0) as client:
        access_token = get_access_token(client, cookie_header, device_id)

        # 3. chat-requirements
        req = chat_requirements(client, cookie_header, device_id, access_token)
        pow_info = req.get("proofofwork") or {}
        arkose = req.get("arkose") or {}

        if args.dry_run:
            print(json.dumps({
                "status": "dry-run-ok",
                "access_token": "yes",
                "requirements_token": bool(req.get("token")),
                "pow_required": bool(pow_info.get("required")),
                "pow_seed": pow_info.get("seed"),
                "pow_difficulty": pow_info.get("difficulty"),
                "arkose_required": bool(arkose.get("required")),
                "zip": str(zip_path),
                "model": args.model,
            }, indent=2))
            print(
                "\nVerdict: " + ("SENDABLE" if not arkose.get("required") else
                                 "BLOCKED (arkose.required=true — cannot solve headlessly)"),
                file=sys.stderr,
            )
            return 0

        # 4. arkose gate
        if arkose.get("required"):
            raise SystemExit(
                "[review] ABORT: chat-requirements requires Arkose. This client cannot "
                "solve FunCaptcha headlessly. Retry later, or switch to a browser-driven "
                "approach. (see SKILL.md 'Known failure points')"
            )

        # 5. proof-of-work
        extra_headers = {"openai-sentinel-chat-requirements-token": req.get("token", "")}
        if pow_info.get("required"):
            proof = solve_pow(str(pow_info.get("seed", "")), str(pow_info.get("difficulty", "")),
                              USER_AGENT)
            if not proof:
                raise SystemExit("[review] PoW required but solve returned empty.")
            extra_headers["openai-sentinel-proof-token"] = proof
            sys.stderr.write(f"[review] PoW solved len={len(proof)}\n")

        # 6. Prepare message: inline text bundle (robust default) vs file attachment (drift-prone).
        prompt_text = args.prompt
        attachments = []
        if args.mode == "attach":
            file_id = upload_zip(client, cookie_header, device_id, access_token, zip_path)
            attachments = [{
                "id": file_id,
                "name": "repo.zip",
                "size": zip_path.stat().st_size,
                "type": "application/zip",
            }]
        elif args.mode == "inline":
            bundle = build_inline_bundle(zip_path)
            prompt_text = bundle + "\n\n---\n\n" + args.prompt
            sys.stderr.write(f"[review] inline bundle chars={len(bundle)}\n")
        # mode == "none": plain prompt, no bundle, no attachment.

        # 7. conversation
        msg_id = str(uuid.uuid4())
        parent_id = str(uuid.uuid4())
        user_msg = {
            "id": msg_id,
            "author": {"role": "user"},
            "content": {"content_type": "text", "parts": [prompt_text]},
            "metadata": {"serialization_metadata": {"custom_symbol_offsets": []}},
        }
        if attachments:
            user_msg["attachments"] = attachments
        payload = {
            "action": "next",
            "messages": [user_msg],
            "model": args.model,
            "parent_message_id": parent_id,
            "timezone_offset_min": -120,
            "suggestions": [],
            "history_and_training_disabled": False,
            "conversation_mode": {"kind": "primary_assistant"},
            "force_paragen": False,
            "force_paragen_model_slug": "",
            "force_nulligen": False,
            "force_rate_limit": False,
            "websocket_request_id": str(uuid.uuid4()),
        }
        conv_headers = {
            **_common_headers(cookie_header, device_id, access_token),
            **extra_headers,
            "Accept": "text/event-stream",
            "Content-Type": "application/json",
        }
        sys.stderr.write(f"[review] sending conversation (mode={args.mode}), streaming...\n")
        review = send_conversation(client, conv_headers, payload, args.dump_events)
        sys.stderr.write(f"[review] done, review chars={len(review)}\n")

    # Final stdout = the review markdown (captured by the extension as tool content).
    sys.stdout.write(review)
    if not review.endswith("\n"):
        sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

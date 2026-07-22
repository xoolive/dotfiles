# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""Zip a repo's git-tracked files for ChatGPT review.

Only files reported by ``git ls-files`` are included (so gitignored ``.env`` /
secrets are excluded by definition). On top of that we apply a secret **denylist**
(tracked files can still contain committed secrets) and a regex **pre-scan** that
aborts loudly on likely secrets before any zip is written or uploaded.

Usage:
    uv run scripts/zip_repo.py /path/to/repo [--out PATH] [--no-scan]
"""

from __future__ import annotations

import argparse
import fnmatch
import os
import re
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

# Path/basename globs that are always excluded (committed secrets + noise).
DENYLIST = [
    # secrets
    ".env", ".env.*", "*.pem", "*.key", "*.p12", "*.pfx", "*.keystore", "*.jks",
    "id_rsa", "id_rsa.*", "id_dsa*", "id_ecdsa*", "id_ed25519*",
    "credentials", "credentials.json", ".npmrc", ".pypirc", ".netrc", ".htpasswd",
    "secrets.*", "*.secret", "*.sqlite", "*.sqlite3",
    ".aws/credentials", ".aws/config",
    # heavy / low-value noise
    "node_modules/**", "dist/**", "build/**", "out/**", ".venv/**", "venv/**",
    "vendor/**", "__pycache__/**", ".git/**", "*.min.js", "*.min.css", "*.map",
    # large lockfiles (override with --include-locks to keep)
    "package-lock.json", "yarn.lock", "pnpm-lock.yaml", "go.sum", "composer.lock",
]

# Lockfile globs removed from the denylist when --include-locks is passed.
LOCKFILES = {"package-lock.json", "yarn.lock", "pnpm-lock.yaml", "go.sum", "composer.lock"}

MAX_FILE_BYTES = 2 * 1024 * 1024  # skip individual files larger than 2 MB

# Regex secret pre-scan. Patterns are intentionally conservative; a hit ABORTS.
# Each entry: (rule_name, compiled_regex).
SECRET_PATTERNS = [
    ("aws_access_key_id", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("aws_secret_access_key", re.compile(r"(?i)aws_secret_access_key\s*[=:]\s*['\"]?[A-Za-z0-9/+=]{40}")),
    ("private_key_block", re.compile(r"-----BEGIN (?:RSA |EC |DSA |OPENSSH |PGP )?PRIVATE KEY-----")),
    ("github_pat", re.compile(r"\b(?:ghp|gho|ghu|ghs|ghr|github_pat)_[A-Za-z0-9]{20,}\b")),
    ("google_api_key", re.compile(r"\bAIza[0-9A-Za-z_\-]{35}\b")),
    ("slack_token", re.compile(r"\bxox[bp]-[0-9A-Za-z]{10,}-[0-9A-Za-z]{10,}\b")),
    ("stripe_key", re.compile(r"\b(?:sk|pk|rk)_(?:live|test)_[0-9A-Za-z]{20,}\b")),
    ("jwt", re.compile(r"\beyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\b")),
    # generic assignment of a long high-entropy value next to secret-ish key names
    ("assigned_secret", re.compile(
        r"(?i)(?:api[_-]?key|secret|password|passwd|token|auth|private[_-]?key)"
        r"\s*[=:]\s*['\"]?[A-Za-z0-9+/=_\-]{32,}")),
]


def _git_ls_files(repo: Path) -> list[str]:
    try:
        out = subprocess.run(
            ["git", "-C", str(repo), "ls-files"],
            check=True, capture_output=True, text=True,
        )
    except FileNotFoundError:
        raise SystemExit("[zip] git not found")
    except subprocess.CalledProcessError as e:
        raise SystemExit(f"[zip] not a git repo or git failed: {e.stderr.strip()}")
    return [line for line in out.stdout.splitlines() if line.strip()]


def _excluded(path: str, denylist: list[str]) -> bool:
    base = os.path.basename(path)
    for pat in denylist:
        if fnmatch.fnmatch(path, pat) or fnmatch.fnmatch(base, pat):
            return True
    return False


def _is_binary(data: bytes) -> bool:
    # NUL byte in the first 8KB → almost certainly binary.
    return b"\x00" in data[:8192]


def _redact(text: str, match: re.Match[str]) -> str:
    s, e = match.span()
    snippet = text[max(0, s - 20): min(len(text), e + 20)]
    return snippet.replace(match.group(0), "*" * min(len(match.group(0)), 12))


def _scan_secrets(files: list[tuple[str, bytes]]) -> None:
    hits: list[str] = []
    for rel, data in files:
        try:
            text = data.decode("utf-8", errors="ignore")
        except Exception:
            continue
        for rule, rx in SECRET_PATTERNS:
            m = rx.search(text)
            if m:
                redacted = _redact(text, m)
                # strip newlines for a tidy one-line report
                redacted = " ".join(redacted.split())
                hits.append(f"  {rel}: rule={rule} near=...{redacted}...")
    if hits:
        sys.stderr.write(
            "\n[zip] SECRET SCAN ABORTED — likely secret(s) detected in tracked files:\n"
        )
        for h in hits:
            sys.stderr.write(h + "\n")
        sys.stderr.write(
            "\nRefusing to zip. Remove/rotate the secret, or re-run with --no-scan "
            "(NOT recommended) to proceed.\n"
        )
        raise SystemExit(2)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("repo", help="Path to the git repository to review.")
    ap.add_argument("--out", help="Output zip path (default: temp file).")
    ap.add_argument("--no-scan", action="store_true", help="Skip the secret pre-scan (dangerous).")
    ap.add_argument("--include-locks", action="store_true", help="Keep large lockfiles in the zip.")
    args = ap.parse_args()

    repo = Path(args.repo).expanduser().resolve()
    if not repo.is_dir():
        raise SystemExit(f"[zip] not a directory: {repo}")

    denylist = list(DENYLIST)
    if args.include_locks:
        denylist = [p for p in denylist if os.path.basename(p) not in LOCKFILES]

    tracked = _git_ls_files(repo)
    if not tracked:
        raise SystemExit("[zip] no tracked files (empty `git ls-files`).")

    kept: list[tuple[str, bytes]] = []
    excluded: list[tuple[str, str]] = []
    for rel in tracked:
        if _excluded(rel, denylist):
            excluded.append((rel, "denylist"))
            continue
        abspath = repo / rel
        try:
            data = abspath.read_bytes()
        except OSError as e:
            excluded.append((rel, f"unreadable ({e})"))
            continue
        if len(data) > MAX_FILE_BYTES:
            excluded.append((rel, f"oversize ({len(data)} bytes)"))
            continue
        if _is_binary(data):
            excluded.append((rel, "binary"))
            continue
        kept.append((rel, data))

    if not args.no_scan:
        _scan_secrets(kept)
    elif args.no_scan:
        sys.stderr.write("[zip] WARNING: --no-scan set; secret pre-scan skipped.\n")

    out = Path(args.out).expanduser().resolve() if args.out else Path(
        tempfile.gettempdir()) / f"chatgpt-review-{repo.name}-{os.getpid()}.zip"
    if out.exists():
        out.unlink()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for rel, data in kept:
            z.writestr(rel, data)

    sys.stderr.write(
        f"[zip] repo={repo.name} tracked={len(tracked)} kept={len(kept)} "
        f"excluded={len(excluded)} zip_bytes={out.stat().st_size} -> {out}\n"
    )
    # Final stdout line is the zip path (consumed by review.py / the extension).
    print(str(out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

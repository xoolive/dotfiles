# /// script
# requires-python = ">=3.10"
# dependencies = ["playwright>=1.45"]
# ///
"""Drive ChatGPT's web UI with a real browser to get a repo review.

This is the robust route: it runs ChatGPT's own sentinel/proof-of-work JS, so it
is not subject to the headless-client 403 that blocks the cookie-replay path
(review.py). A dedicated persistent Firefox profile is used so you log in once
and stay logged in.

One-time setup (needs a display — run in your terminal):

    uv run scripts/browser_review.py --setup

Then reviews (the extension calls this):

    uv run scripts/browser_review.py --repo /path/to/repo [--prompt "..."]
    uv run scripts/browser_review.py --repo /path/to/repo --headless
    uv run scripts/browser_review.py --repo /path/to/repo --dry-run

Selector drift caveat: ChatGPT's DOM changes. Selectors below try multiple known
shapes; if they break, run with --dump-dom to capture the composer HTML and patch
the SELECTORS dict.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import zipfile
from pathlib import Path

try:
    from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
except ImportError:
    raise SystemExit(
        "[browser] playwright not installed. Run: uv pip install playwright && "
        "uv run --with playwright playwright install firefox"
    )

BASE = "https://chatgpt.com"
DEFAULT_PROMPT = (
    "Review the repository whose file contents are attached (or inlined below). "
    "Output a code review as markdown with sections: Summary, Security, "
    "Bugs & Correctness, Architecture & Design, Maintainability, Performance, "
    "and Top Actionable Suggestions (prioritized, with file paths). Be specific "
    "and concise."
)

# Candidate selectors, tried in order. Tunable when the DOM drifts.
SEL_COMPOSER = ["#prompt-textarea", "textarea#prompt-textarea",
                "div#prompt-textarea", "div[contenteditable=true][role='textbox']"]
SEL_FILE_INPUT = ["input[type=file]", "input[type=file][accept]"]
SEL_SEND_BUTTON = ["button[data-testid='send-button']",
                   "button[aria-label='Send prompt']",
                   "button[aria-label*='Send']"]
SEL_STOP_BUTTON = ["button[data-testid='stop-button']",
                   "button[aria-label='Stop generating']",
                   "button[aria-label*='Stop']"]
SEL_ASSISTANT_MSG = ["div[data-message-author-role='assistant']",
                     "article[data-message-author-role='assistant']"]
SEL_MSG_MARKDOWN = [".markdown", "[class*='markdown']", ".whitespace-pre-wrap"]


def profile_dir(override: str | None) -> Path:
    p = Path(override).expanduser() if override else Path(
        os.environ.get("XDG_CACHE_HOME", str(Path.home() / ".cache"))
    ) / "chatgpt-web-review-profile"
    p.mkdir(parents=True, exist_ok=True)
    return p


def first_visible(page, selectors: list[str], timeout: int = 8000):
    """Return the first locator among selectors that becomes visible, else None."""
    for sel in selectors:
        loc = page.locator(sel).first
        try:
            loc.wait_for(state="visible", timeout=timeout)
            return loc
        except PWTimeout:
            continue
    return None


def any_present(page, selectors: list[str], timeout: int = 3000):
    for sel in selectors:
        try:
            page.locator(sel).first.wait_for(state="attached", timeout=timeout)
            return sel
        except PWTimeout:
            continue
    return None


def is_logged_in(page) -> bool:
    """Authoritative: a __Secure-next-auth.session-token cookie means logged in.
    ChatGPT's landing page renders a composer even when logged out, so composer
    presence alone is NOT sufficient (it produced false positives)."""
    try:
        cookies = page.context.cookies([BASE])
    except Exception:
        cookies = []
    for c in cookies:
        if str(c.get("name", "")).startswith("__Secure-next-auth.session-token"):
            return True
    # Logged-out pages show Log in / Sign up affordances.
    for sel in ["button:has-text('Log in')", "a:has-text('Log in')",
                "button:has-text('Sign up')", "a:has-text('Sign up')",
                "[data-testid='login-button']"]:
        try:
            loc = page.locator(sel).first
            if loc.count() > 0 and loc.is_visible(timeout=1500):
                return False
        except Exception:
            continue
    # Last resort: require composer AND no login URL.
    if any(frag in page.url for frag in ("/auth/login", "/auth/", "login")):
        return False
    return first_visible(page, SEL_COMPOSER, timeout=8000) is not None


def make_zip(args) -> Path:
    if args.zip:
        p = Path(args.zip).expanduser().resolve()
        if not p.is_file():
            raise SystemExit(f"[browser] zip not found: {p}")
        return p
    zip_repo_py = Path(__file__).parent / "zip_repo.py"
    proc = subprocess.run(
        [sys.executable, str(zip_repo_py), str(Path(args.repo).expanduser().resolve())],
        capture_output=True, text=True,
    )
    sys.stderr.write(proc.stderr)
    if proc.returncode != 0:
        raise SystemExit(f"[browser] zip_repo failed (exit {proc.returncode})")
    return Path(proc.stdout.strip().splitlines()[-1])


def build_inline_bundle(zip_path: Path, per_file_cap: int = 20000,
                        total_cap: int = 120_000) -> str:
    import zipfile
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


def attach_zip(page, zip_path: Path, dump_dom: bool) -> bool:
    """Attach the zip via the hidden file input. Returns True on success."""
    inp = first_visible(page, SEL_FILE_INPUT, timeout=6000)
    # File inputs are often display:none; try attached-but-not-visible too.
    if inp is None:
        for sel in SEL_FILE_INPUT:
            loc = page.locator(sel).first
            try:
                loc.wait_for(state="attached", timeout=3000)
                inp = loc
                break
            except PWTimeout:
                continue
    if inp is None:
        sys.stderr.write("[browser] no file input found; will fall back to inline.\n")
        if dump_dom:
            sys.stderr.write("COMPOSER DOM:\n" + page.content()[:4000] + "\n")
        return False
    try:
        inp.set_input_files(str(zip_path))
        # Wait for the upload to settle: an attachment chip appears and/or the
        # send button becomes enabled. Poll up to 40s (large zips / slow upload)
        # instead of a fixed 1.5s, so type_prompt_and_send() doesn't race.
        t0 = time.time()
        settled = False
        while time.time() - t0 < 40:
            page.wait_for_timeout(800)
            chip = (any_present(page, ["[data-testid*='attachment']"], timeout=400)
                    or any_present(
                        page, [f"div:has-text('{zip_path.name}')"], timeout=400))
            try:
                sb = page.locator(SEL_SEND_BUTTON[0]).first
                if sb.count() and sb.get_attribute("disabled") is None:
                    settled = True
                    break
            except Exception:
                pass
            if chip and time.time() - t0 > 4:
                settled = True
                break
        if not settled:
            sys.stderr.write(
                "[browser] upload may not have settled; continuing best-effort.\n")
        sys.stderr.write(f"[browser] attached {zip_path.name}\n")
        return True
    except Exception as e:
        sys.stderr.write(f"[browser] attach failed ({e}); falling back to inline.\n")
        return False


def type_prompt_and_send(page, text: str) -> None:
    composer = first_visible(page, SEL_COMPOSER, timeout=8000)
    if composer is None:
        raise SystemExit("[browser] composer not found after login. DOM changed? --dump-dom.")
    composer.click()
    # press_sequentially works for contenteditable divs and textareas alike.
    try:
        composer.press_sequentially(text, delay=3)
    except Exception:
        composer.type(text, delay=3)
    page.wait_for_timeout(300)
    sent = False
    btn = first_visible(page, SEL_SEND_BUTTON, timeout=4000)
    if btn is not None:
        try:
            btn.click()
            sent = True
        except Exception:
            pass
    if not sent:
        # Fallback: Enter in the composer.
        try:
            composer.press("Enter")
            sent = True
        except Exception:
            pass
    if not sent:
        raise SystemExit("[browser] could not submit the prompt (no send button, Enter failed).")


def wait_for_completion(page, max_seconds: int = 360) -> bool:
    """Wait until the assistant finishes generating; report whether it did."""
    # Allow a moment for generation to start (stop button may appear).
    start = time.time()
    # Wait for at least one assistant message to appear.
    first_visible(page, SEL_ASSISTANT_MSG, timeout=20000)
    # Poll: done when stop button is gone AND text stable for ~2.5s.
    last_text = ""
    stable_since = None
    while time.time() - start < max_seconds:
        page.wait_for_timeout(1000)
        stop = any_present(page, SEL_STOP_BUTTON, timeout=500)
        current = scrape_last_assistant(page)
        if current and current == last_text:
            if stable_since is None:
                stable_since = time.time()
            if stop is None and time.time() - stable_since > 2.5:
                return True
        else:
            stable_since = None
            last_text = current or last_text
        if not stop and current:
            # No stop button but text present — likely done; confirm stability shortly.
            if stable_since is None:
                stable_since = time.time()
            if time.time() - stable_since > 3.0:
                return True
    sys.stderr.write("[browser] wait_for_completion hit max timeout; returning best-effort.\n")
    return False


def scrape_last_assistant(page) -> str:
    # Try each assistant selector; pick the first that yields text.
    best = ""
    for sel in SEL_ASSISTANT_MSG:
        lc = page.locator(sel)
        try:
            n = lc.count()
        except Exception:
            n = 0
        if n == 0:
            continue
        last = lc.nth(n - 1)
        for msel in SEL_MSG_MARKDOWN:
            try:
                ml = last.locator(msel).first
                if ml.count() > 0:
                    best = ml.inner_text(timeout=2000)
                    break
            except Exception:
                continue
        if not best:
            try:
                best = last.inner_text(timeout=2000)
            except Exception:
                pass
        if best:
            return best
    return best


def seed_cookies(ctx, page) -> bool:
    """Inject the real Firefox session cookies via context.add_cookies, then reload.

    This bypasses the login/OAuth flow (where Playwright's patched Firefox is
    flagged 'insecure') by making the browser already-authenticated on first
    navigation. Logs cookie names only, never values.
    """
    cookies_py = Path(__file__).parent / "cookies.py"
    proc = subprocess.run(
        [sys.executable, str(cookies_py), "--emit-playwright"],
        capture_output=True, text=True,
    )
    if proc.returncode != 0:
        sys.stderr.write(proc.stderr)
        sys.stderr.write("[browser] cookie extraction for seeding failed (see above).\n")
        return False
    try:
        cookies = json.loads(proc.stdout)
    except json.JSONDecodeError:
        sys.stderr.write("[browser] could not parse cookies.py --emit-playwright output.\n")
        return False
    if not cookies:
        sys.stderr.write("[browser] no cookies to seed.\n")
        return False
    try:
        ctx.add_cookies(cookies)
    except Exception as e:
        sys.stderr.write(f"[browser] add_cookies failed: {e}\n")
        return False
    names = sorted({c["name"] for c in cookies})
    sys.stderr.write(f"[browser] seeded {len(cookies)} cookies: {', '.join(names)}\n")
    return True


def safe_goto(page, label: str = "navigate", url: str = BASE) -> None:
    """Navigate safely, tolerating redirect-induced NS_BINDING_ABORTED."""
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=45000)
    except Exception as e:
        sys.stderr.write(
            f"[browser] {label} load issue ({type(e).__name__}); continuing.\n"
        )


def ensure_logged_in(page, ctx, allow_seed: bool) -> bool:
    """End logged-in on a hydrated chatgpt.com page.

    The persistent Firefox profile resumes on about:blank with its cookies
    already set, so is_logged_in() returns True from the cookie alone — but the
    ChatGPT SPA has not loaded, so the composer/file-input are not in the DOM
    yet. We must navigate to BASE and wait for the composer to render before
    callers probe selectors, otherwise every selector wait times out with
    "composer not found after login".
    """
    need_seed = not is_logged_in(page)
    if need_seed and not allow_seed:
        return False
    if need_seed:
        sys.stderr.write(
            "[browser] not logged in; seeding cookies from real Firefox...\n")
        if not seed_cookies(ctx, page):
            return False
    # Always (re)load chatgpt.com so the SPA hydrates. With valid cookies the
    # navigation lands logged-in; an expired cookie may hit a login wall, which
    # is_logged_in() then detects.
    safe_goto(page, "open-chat")
    page.wait_for_timeout(3000)
    if not is_logged_in(page):
        return False
    composer = first_visible(page, SEL_COMPOSER, timeout=20000)
    if composer is None:
        sys.stderr.write(
            "[browser] logged in but composer did not hydrate; DOM may have changed.\n")
        return False
    return True


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--repo", help="Repository to zip & review (or --zip).")
    ap.add_argument("--zip", help="Use an existing zip file instead of zipping a repo.")
    ap.add_argument("--prompt", default=DEFAULT_PROMPT)
    ap.add_argument("--headless", action="store_true", help="Run browser headless (riskier for detection).")
    ap.add_argument("--setup", action="store_true",
                    help="One-time: open headed browser, wait for you to log in, then save profile and exit.")
    ap.add_argument("--dry-run", action="store_true",
                    help="Open profile, report login state, and exit (no send).")
    ap.add_argument("--inline", action="store_true",
                    help="Inline sources as text instead of attaching the zip (fallback if upload selectors break).")
    ap.add_argument("--profile", help="Override the persistent profile directory.")
    ap.add_argument("--dump-dom", action="store_true", help="Save page HTML on selector failures.")
    ap.add_argument(
        "--max-wait", type=int, default=360,
        help="Maximum seconds to wait locally; timed-out conversations remain in ChatGPT history.",
    )
    ap.add_argument("--no-seed", action="store_true",
                    help="Do not auto-inject real-Firefox cookies when not logged in.")
    args = ap.parse_args()

    if not args.setup and not args.repo and not args.zip and not args.dry_run:
        ap.error("one of --setup, --repo, --zip, or --dry-run is required")

    prof = profile_dir(args.profile)
    conversation_url = ""
    sys.stderr.write(f"[browser] profile: {prof}\n")

    with sync_playwright() as p:
        # setup is always headed so you can see the login page; otherwise honor --headless.
        headless = (not args.setup) and args.headless
        try:
            ctx = p.firefox.launch_persistent_context(
                user_data_dir=str(prof),
                headless=headless,
                viewport={"width": 1280, "height": 900},
            )
        except Exception as e:
            raise SystemExit(
                f"[browser] failed to launch Firefox: {e}. "
                f"Did you run `uv run --with playwright playwright install firefox`?"
            )
        page = ctx.pages[0] if ctx.pages else ctx.new_page()

        if args.setup:
            safe_goto(page, "setup")
            print("[browser] --setup: log into ChatGPT in the opened window. "
                  "Waiting up to 5 min for the composer to appear...", file=sys.stderr)
            if is_logged_in_with_wait(page, 300):
                print("[browser] login detected; profile saved. Re-run without --setup.", file=sys.stderr)
                ctx.close()
                return 0
            print("[browser] --setup timed out without detecting login. Try again.", file=sys.stderr)
            ctx.close()
            return 1

        # Non-setup: enforce headless preference by relaunching if needed.
        if args.dry_run:
            logged = ensure_logged_in(page, ctx, allow_seed=not args.no_seed)
            print(f"logged_in={logged}\nurl={page.url}\ncomposer={'yes' if logged else 'no'}")
            ctx.close()
            return 0 if logged else 2

        # Real review path.
        if not ensure_logged_in(page, ctx, allow_seed=not args.no_seed):
            ctx.close()
            raise SystemExit(
                "[browser] not logged in even after seeding. The ChatGPT session cookie may "
                "be expired, or OpenAI requires device verification for this browser "
                "fingerprint. Open chatgpt.com in your real Firefox to refresh the session, "
                "then re-run; or run --setup (headed) once and complete any device-verification "
                "email."
            )
        zip_path = make_zip(args)
        prompt = DEFAULT_PROMPT
        if args.prompt and args.prompt != DEFAULT_PROMPT:
            prompt = args.prompt

        attached = False
        if not args.inline:
            attached = attach_zip(page, zip_path, args.dump_dom)
        if args.inline or not attached:
            bundle = build_inline_bundle(zip_path)
            prompt = bundle + "\n\n---\n\n" + prompt
            sys.stderr.write(f"[browser] inline bundle chars={len(bundle)}\n")

        type_prompt_and_send(page, prompt)
        page.wait_for_timeout(1_500)
        conversation_url = page.url if "/c/" in page.url else ""
        if conversation_url:
            sys.stderr.write(f"[browser] conversation: {conversation_url}\n")
        sys.stderr.write("[browser] prompt sent; waiting for completion...\n")
        completed = wait_for_completion(page, max_seconds=max(1, args.max_wait))
        review = scrape_last_assistant(page) or ""

        # File-heavy reviews can finish server-side just after the local wait.
        # Reload the known conversation once before handing recovery to history.py.
        if not review and conversation_url:
            safe_goto(page, "reload-conversation", conversation_url)
            page.wait_for_timeout(5_000)
            review = scrape_last_assistant(page) or ""

        if not review:
            recovery = {
                "timestamp": int(time.time()),
                "conversation": conversation_url,
                "completed_locally": completed,
                "repo": str(Path(args.repo).resolve()) if args.repo else None,
            }
            recovery_path = prof / "review-history.jsonl"
            with recovery_path.open("a", encoding="utf-8") as stream:
                stream.write(json.dumps(recovery) + "\n")
            if conversation_url:
                sys.stderr.write(
                    "[browser] response not yet available locally. Retrieve it later with:\n"
                    f"  uv run {Path(__file__).parent / 'history.py'} "
                    f"--conversation {conversation_url}\n"
                )
        if not review and args.dump_dom:
            dump_path = Path(tempfile.gettempdir()) / "chatgpt-web-review-dom.html"
            dump_path.write_text(page.content(), encoding="utf-8")
            sys.stderr.write(f"[browser] DOM saved to {dump_path}\n")
        ctx.close()

    if not review.strip():
        if conversation_url:
            raise SystemExit(
                "[browser] no assistant text available yet; the conversation was retained at "
                f"{conversation_url}. Use scripts/history.py --conversation to retrieve it later."
            )
        raise SystemExit("[browser] no assistant text scraped. Re-run with --dump-dom.")
    sys.stdout.write(review)
    if not review.endswith("\n"):
        sys.stdout.write("\n")
    return 0


def is_logged_in_with_wait(page, seconds: int) -> bool:
    deadline = time.time() + seconds
    while time.time() < deadline:
        if is_logged_in(page):
            return True
        page.wait_for_timeout(3000)
    return False


if __name__ == "__main__":
    raise SystemExit(main())

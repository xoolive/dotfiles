---
name: chatgpt-web-review
description: Request a full-repository code review from the ChatGPT web account by zipping git-tracked files (secret denylist + pre-scan) and driving a real Firefox browser (Playwright) authenticated via cookie seeding from your real Firefox profile — no interactive login (bypasses the "insecure browser" login block), and the browser runs ChatGPT's own sentinel JS so it succeeds where pure cookie-replay gets 403. Use when the user wants a holistic repo review routed through their ChatGPT Plus web session instead of the OpenAI API.
---

# ChatGPT Web Repo Review

Zip a repository's git-tracked files, drive ChatGPT's web UI in a real Firefox
browser (cookie-seeded persistent profile), attach or inline the sources, ask
for a code review, and inject the review text back into the current pi session
via the `chatgpt_web_review` tool.

## Why a real browser (not cookie replay)

An earlier `review.py` replays Firefox session cookies against ChatGPT's
backend API. **Live testing proved it gets 403 "Unusual activity" at the
conversation send** because the server-side sentinel/proof-of-work rejects the
headless client — even though auth and `chat-requirements` pass and Arkose is
off. Only a real browser runs ChatGPT's own sentinel JS, so `browser_review.py`
is the supported path. `review.py` is kept as a documented (broken) experiment
and a `--dry-run` account-handshake probe. See the appendix.

## How it works

1. **Zip** — `scripts/zip_repo.py` enumerates `git ls-files` (tracked files only,
   so gitignored `.env`/secrets are excluded by default) and applies an extra
   **denylist + regex secret pre-scan** that aborts loudly on likely secrets.
2. **Auth (cookie seed)** — `scripts/browser_review.py` launches a persistent
   Firefox (Playwright). **If not already logged in, it auto-injects the ChatGPT
   session cookies extracted from your real Firefox profile** (`cookies.py
   --emit-playwright` → `context.add_cookies()`). This makes the browser
   already-authenticated on first navigation, so it never touches the login/OAuth
   flow that rejects Playwright's patched Firefox as "insecure". No interactive
   login is needed as long as you're logged into chatgpt.com in your real
   Firefox. The seeded cookies persist in the dedicated profile at
   `~/.cache/chatgpt-web-review-profile/`, so subsequent runs are pre-authed.
3. **Send** — navigates to `chatgpt.com`, attaches the zip via the real UI file
   input (or inlines sources as text if the upload selector breaks), types the
   review prompt, submits, waits for streaming to finish, and scrapes the last
   assistant message.
4. **Inject** — the `chatgpt_web_review` tool returns the review as tool content,
   so it lands in the conversation. The agent then triages it.

## Setup (once)

```bash
# 1. Install the Playwright browser binary (one-time, ~hundreds of MB):
uv run --with 'playwright>=1.45' playwright install firefox

# 2. Make sure you're logged into chatgpt.com in your real Firefox (the cookie
#    source). That's it — no interactive Playwright login required.
#
#    (Optional fallback) If cookie seeding ever fails (e.g. OpenAI forces device
#    verification on the Playwright fingerprint), run --setup once in a terminal
#    with a display to complete verification in the headed window:
#      uv run ~/.pi/agent/extensions/chatgpt-web-review/scripts/browser_review.py --setup
```

The extension tool loads automatically from `~/.pi/agent/extensions/`. Run
`/reload` after first install.

## Usage

```
# via the tool (agent). Headless is the validated in-session mode (no display needed):
chatgpt_web_review({ repoPath: "/path/to/repo", headless: true })
chatgpt_web_review({ repoPath: ".", headless: true, prompt: "Focus on security and error handling." })
chatgpt_web_review({ repoPath: ".", headless: true, dryRun: true })   # report login state only
chatgpt_web_review({ repoPath: "." })   # headed (needs a display; slightly more reliable vs bot detection)

# force the skill then ask in natural language:
/skill:chatgpt-web-review
review the repo at ~/projects/foo
```

## Honest caveats

- **Headed vs headless.** `browser_review.py` defaults to **headed** (needs a
  display). For in-session agent runs, pass `headless: true` — that's the
  validated path. Headed is marginally more reliable against bot detection if you
  have a display and hit challenges.
- **Selector drift.** ChatGPT's DOM changes. Selectors are tried in multiples;
  if they break, run `uv run scripts/browser_review.py --repo <p> --dump-dom`
  and patch the `SEL_*` dicts in `browser_review.py`.
- **Bot detection / "insecure browser".** Playwright's patched Firefox is
  rejected by the *login* flow — which is why auth is done by **cookie seeding**,
  not interactive login. Headless + seeded cookies is the validated default. If
  OpenAI ever forces device-verification on the Playwright fingerprint even with
  a valid session cookie, run `--setup` (headed, with a display) once to complete
  the email verification, then resume headless.
- **Size.** "Full repo" really means *small-to-medium* repo — the model context,
  not the upload limit, is the ceiling. Inline fallback caps total source text
  (~120 KB); for large repos, scope the review or expect a shallow pass.
- **Committed secrets.** Tracked ≠ safe. The denylist + regex scan is a guard,
  not a guarantee. Inspect the printed zip path before sending if the repo is
  sensitive.
- **ToS.** Automating ChatGPT web violates OpenAI's terms. Low-volume personal
  use is low-risk but non-zero. Do not use at scale.

## Debugging

- `browser_review.py --dry-run` → prints `logged_in=…` and the composer state
  (auto-seeds cookies if not logged in).
- `browser_review.py --dry-run --no-seed` → baseline login state without seeding.
- `browser_review.py --repo <p> --dump-dom` → dumps composer HTML on selector
  failure; `--inline` bypasses the UI upload and types sources as text.
- `review.py --dry-run` (legacy replay) → still useful as an account handshake
  probe (auth token + chat-requirements verdict).

## Validated status (2026-07-21, live)

- ✅ Cookie extraction from real Firefox + chunked JWT kept in `.0/.1` chunks.
- ✅ `context.add_cookies()` injection (ms→s expiry fix; session cookies omit expires).
- ✅ Headless `--dry-run` on a fresh profile: `logged_in=True` via seed alone.
- ✅ Real send: inline trivial prompt → assistant reply scraped, exit 0.
- ⚠️ File upload via the browser UI (the default when `--inline` is not set) is
  not yet exercised live; `--inline` is the validated default. Try the UI attach;
  fall back to `--inline` on selector drift.

## Appendix: the cookie-replay experiment (legacy, blocked)

`scripts/cookies.py` + `scripts/review.py` replay Firefox cookies against the
backend API. Live-validated state (2026-07-20):

- ✅ Cookie extraction + chunked JWT reassembly.
- ✅ `/api/auth/session` → access token (Cloudflare does NOT block httpx here).
- ✅ `/backend-api/sentinel/chat-requirements` → token + PoW; Arkose NOT required.
- ❌ `/backend-api/files` → 422 (endpoint moved to a presigned-S3 flow).
- ❌ `/backend-api/conversation` → 403 "Unusual activity" — sentinel rejects the
  headless client's proof-of-work. **This is why the browser path exists.**

Run `review.py --dry-run` to re-check whether Arkose/Cloudflare conditions change
over time.

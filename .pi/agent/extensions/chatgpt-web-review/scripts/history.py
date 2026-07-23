# /// script
# requires-python = ">=3.10"
# dependencies = ["playwright>=1.45"]
# ///
"""List or retrieve completed ChatGPT conversations from the review profile.

Use this after a repository review times out locally but continues in ChatGPT:

    uv run scripts/history.py --list
    uv run scripts/history.py --latest --title-contains "Tidy Data"
    uv run scripts/history.py --conversation /c/<conversation-id>

No prompt is submitted. The script only reads existing conversation history.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

from browser_review import (
    BASE,
    SEL_ASSISTANT_MSG,
    ensure_logged_in,
    profile_dir,
    scrape_last_assistant,
)


def conversation_links(page) -> list[tuple[str, str]]:
    """Return visible sidebar conversations in display order."""
    page.goto(BASE, wait_until="domcontentloaded", timeout=45_000)
    page.wait_for_timeout(5_000)
    links = page.locator('a[href^="/c/"]')
    found: list[tuple[str, str]] = []
    seen: set[str] = set()
    for index in range(links.count()):
        link = links.nth(index)
        href = link.get_attribute("href")
        if not href or href in seen:
            continue
        seen.add(href)
        title = " ".join((link.inner_text() or "").split())
        found.append((href, title))
    return found


def normalize_conversation(value: str) -> str:
    value = value.strip()
    if value.startswith(BASE):
        return value
    if value.startswith("/c/"):
        return BASE + value
    if value.startswith("c/"):
        return BASE + "/" + value
    return BASE + "/c/" + value


def fetch_review(page, conversation: str, wait_seconds: int) -> str:
    """Open one existing conversation and return its latest assistant message."""
    url = normalize_conversation(conversation)
    deadline = time.time() + wait_seconds
    while True:
        page.goto(url, wait_until="domcontentloaded", timeout=45_000)
        try:
            page.locator(SEL_ASSISTANT_MSG[0]).first.wait_for(
                state="attached", timeout=15_000
            )
        except Exception:
            pass
        page.wait_for_timeout(2_000)
        review = scrape_last_assistant(page)
        if review:
            return review
        if time.time() >= deadline:
            return ""
        page.wait_for_timeout(5_000)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--list", action="store_true", help="List recent conversations.")
    action.add_argument("--latest", action="store_true", help="Fetch the newest matching conversation.")
    action.add_argument("--conversation", help="Conversation URL, /c/path, or conversation ID.")
    parser.add_argument("--title-contains", help="Case-insensitive title filter for --list/--latest.")
    parser.add_argument("--limit", type=int, default=30, help="Maximum list entries (default: 30).")
    parser.add_argument("--wait", type=int, default=30, help="Seconds to wait for an existing result.")
    parser.add_argument("--profile", help="Override the persistent Playwright profile directory.")
    args = parser.parse_args()

    with sync_playwright() as playwright:
        context = playwright.firefox.launch_persistent_context(
            user_data_dir=str(profile_dir(args.profile)),
            headless=True,
            viewport={"width": 1280, "height": 900},
        )
        page = context.pages[0] if context.pages else context.new_page()
        if not ensure_logged_in(page, context, allow_seed=True):
            context.close()
            raise SystemExit("[history] not logged in after Firefox cookie seeding")

        if args.conversation:
            review = fetch_review(page, args.conversation, args.wait)
            context.close()
            if not review:
                raise SystemExit("[history] no completed assistant response found")
            print(review)
            return 0

        links = conversation_links(page)
        if args.title_contains:
            needle = args.title_contains.casefold()
            links = [(href, title) for href, title in links if needle in title.casefold()]

        if args.list:
            context.close()
            for href, title in links[: max(0, args.limit)]:
                print(f"{href}\t{title}")
            return 0

        if not links:
            context.close()
            raise SystemExit("[history] no matching conversations found")
        href, title = links[0]
        print(f"[history] fetching {title!r} ({href})", file=sys.stderr)
        review = fetch_review(page, href, args.wait)
        context.close()
        if not review:
            raise SystemExit("[history] conversation exists but has no completed assistant response")
        print(review)
        return 0


if __name__ == "__main__":
    raise SystemExit(main())

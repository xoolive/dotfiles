#!/usr/bin/env python3
"""Fetch an Atlassian Confluence Cloud page to JSON/HTML/text files.

Credentials can come from environment variables or an .env file:
  ATLASSIAN_EMAIL
  ATLASSIAN_API_TOKEN
  ATLASSIAN_BASE_URL   # e.g. https://example.atlassian.net/wiki

Example:
  uv run --with atlassian-python-api --with beautifulsoup4 \
    fetch_confluence_page.py \
    --env-file /path/to/.env \
    --page-id 1629945864 \
    --output-dir ./confluence \
    --basename kickoff_page
"""

from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path

from atlassian import Confluence
from bs4 import BeautifulSoup


def load_env(path: Path) -> None:
    if not path.exists():
        raise FileNotFoundError(f".env file not found: {path}")

    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def safe_basename(value: str) -> str:
    value = value.strip() or "confluence_page"
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("._") or "confluence_page"


def html_to_text(html: str) -> str:
    text = BeautifulSoup(html, "html.parser").get_text("\n")
    return "\n".join(line.strip() for line in text.splitlines() if line.strip())


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, help="Path to a .env file with Atlassian credentials")
    parser.add_argument("--base-url", help="Confluence base URL, e.g. https://site.atlassian.net/wiki")
    parser.add_argument("--email", help="Atlassian account email")
    parser.add_argument("--token", help="Atlassian API token. Prefer .env or environment variable.")
    parser.add_argument("--page-id", required=True, help="Confluence page/content id")
    parser.add_argument("--output-dir", type=Path, default=Path("."), help="Directory where output files are written")
    parser.add_argument("--basename", help="Output basename without extension. Defaults to sanitized page title.")
    parser.add_argument(
        "--expand",
        default="body.storage,body.view,version,space,metadata.labels,children.attachment",
        help="Confluence REST expand parameter",
    )
    parser.add_argument("--no-html", action="store_true", help="Do not write HTML output")
    parser.add_argument("--no-text", action="store_true", help="Do not write text output")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.env_file:
        load_env(args.env_file)

    base_url = args.base_url or os.environ.get("ATLASSIAN_BASE_URL")
    email = args.email or os.environ.get("ATLASSIAN_EMAIL")
    token = args.token or os.environ.get("ATLASSIAN_API_TOKEN")

    missing = [name for name, value in {
        "ATLASSIAN_BASE_URL/--base-url": base_url,
        "ATLASSIAN_EMAIL/--email": email,
        "ATLASSIAN_API_TOKEN/--token": token,
    }.items() if not value]
    if missing:
        raise SystemExit("Missing required credentials/config: " + ", ".join(missing))

    confluence = Confluence(url=base_url, username=email, password=token, cloud=True)
    page = confluence.get_page_by_id(args.page_id, expand=args.expand)

    basename = safe_basename(args.basename or page.get("title") or f"page_{args.page_id}")
    args.output_dir.mkdir(parents=True, exist_ok=True)

    json_path = args.output_dir / f"{basename}.json"
    json_path.write_text(json.dumps(page, indent=2, ensure_ascii=False), encoding="utf-8")

    html = page.get("body", {}).get("view", {}).get("value") or page.get("body", {}).get("storage", {}).get("value", "")

    html_path = None
    if not args.no_html:
        html_path = args.output_dir / f"{basename}.html"
        html_path.write_text(html, encoding="utf-8")

    text_path = None
    if not args.no_text:
        text_path = args.output_dir / f"{basename}.txt"
        text_path.write_text(html_to_text(html), encoding="utf-8")

    print(f"Fetched: {page.get('title')} / version {page.get('version', {}).get('number')}")
    print(f"JSON: {json_path}")
    if html_path:
        print(f"HTML: {html_path}")
    if text_path:
        print(f"Text: {text_path}")


if __name__ == "__main__":
    main()

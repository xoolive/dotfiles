---
name: atlassian
description: Access Atlassian Cloud Confluence/Jira spaces using a local .env with ATLASSIAN_EMAIL and ATLASSIAN_API_TOKEN. Use when fetching Confluence pages, searching spaces, exporting content, or scripting against atlassian.net with token auth.
---

# Atlassian Cloud access

Use this skill when the user wants to access `*.atlassian.net` content programmatically.

## Credential pattern

For Atlassian Cloud API tokens, use **Basic Auth** with:

- username: `ATLASSIAN_EMAIL`
- password: `ATLASSIAN_API_TOKEN`

Do **not** use `Authorization: Bearer` for user API tokens. Tokens do not bypass permissions; the Atlassian account must have access to the target site/space/page.

Recommended `.env` keys:

```dotenv
ATLASSIAN_EMAIL=user@example.org
ATLASSIAN_API_TOKEN=...
ATLASSIAN_BASE_URL=https://example.atlassian.net/wiki
CONFLUENCE_SPACE=SPACEKEY
CONFLUENCE_PAGE_ID=123456789
```

You may need to remind the user to create a token here:
https://id.atlassian.com/manage-profile/security/api-tokens

Keep `.env` mode `600` and never print token values.

## Fetch a Confluence page

Use the bundled generic script at `scripts/fetch_confluence_page.py`. It has no project-specific page IDs or output names; pass these as arguments.

```bash
uv run --with atlassian-python-api --with beautifulsoup4 \
  /home/xo/.pi/agent/skills/atlassian/scripts/fetch_confluence_page.py \
  --env-file /path/to/.env \
  --page-id 123456789 \
  --output-dir ./confluence \
  --basename page_name
```

Arguments:

- `--env-file`: optional `.env` file containing credentials/config.
- `--base-url`: Confluence base URL if not provided by `ATLASSIAN_BASE_URL`.
- `--email`: Atlassian email if not provided by `ATLASSIAN_EMAIL`.
- `--token`: Atlassian API token if not provided by `ATLASSIAN_API_TOKEN`; prefer `.env` over CLI to avoid shell history leaks.
- `--page-id`: required Confluence content/page id.
- `--output-dir`: directory for output files.
- `--basename`: output basename; defaults to sanitized page title.

The script writes `<basename>.json`, `<basename>.html`, and `<basename>.txt` unless disabled with `--no-html` or `--no-text`.

## Python library

For custom operations, use `atlassian-python-api` directly:

```bash
uv run --with atlassian-python-api --with beautifulsoup4 script.py
```

## Useful API calls

- Get page by id: `/rest/api/content/{id}?expand=body.storage,body.view,version,space`
- Search CQL: `/rest/api/content/search?cql=space=KEY and text~"query"`
- List space content: `/rest/api/space/{key}/content/page`
- Children: `/rest/api/content/{id}/child/page`
- Attachments: `/rest/api/content/{id}/child/attachment`


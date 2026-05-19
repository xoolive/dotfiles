---
name: movie
description: Take a list of movies and series watched by the user and produce a movie.md file with cast, director (when notable), and a short italic synopsis for each title. Trigger on requests like "enrich my watchlist", "add synopses to my movie list", or "/movie".
---

# Movie — Watched list enricher

Given a list of movies and series (one per line, with country flag emoji), produce a `movie.md` file where each entry has its main cast, optionally a director, and a short synopsis in a blockquote.

## Input format

The user provides a list like the one below. Preserve everything: original titles, translations, country flags, ✈︎ markers, season numbers.

```
- Vår tid är nu (Le restaurant) 🇸🇪
- 웰컴투 삼달리 (Welcome to Samdal-ri) 🇰🇷
- ✈︎ Midnight in Paris
- 더 글로리 (The Glory 2/2) 🇰🇷
```

Rules to keep in mind:
- `✈︎` means the user watched it on a plane — preserve it in the title heading
- If a title appears twice (e.g. part 1 and part 2 of the same series), keep them as **two separate entries**
- The user tries to always use the original-language title first, then a translation; if the film is originally French, no translation is needed
- Preserve the order of the original list exactly
- **Never add, remove, or alter titles** — use the exact title the user gave. If the user gave only the original title (no translation), add the English translation in parentheses — **unless the film is originally French**, in which case keep the French title alone.

## Output format

Write `movie.md` with one `##` heading per title, followed by a metadata line, an empty line, and a blockquote synopsis:

```markdown
## [Original title] ([Translation if any]) [flag emoji]

**[Series/Film (year if known)]** | [Dir. Name if notable] | **Cast**: Actor One, Actor Two, Actor Three

> _Short synopsis in one or two sentences._

## ✈︎ [Title] [flag emoji]
**Film (year)** | **Cast**: Actor One, Actor Two

> _Short synopsis._
```

### Metadata line rules

- Start with `**Series**` or `**Film (year)**`
- Include `Dir. Name` **only if the director is widely famous** (e.g. Woody Allen, Jean-Luc Godard, Quentin Dupieux). Do not mention directors of individual episodes, production companies, or streaming platforms.
- Always include `**Cast**: ...` with 3–6 main actors. If a character name adds useful context, add it in parentheses: `Song Hye-kyo (Moon Dong-eun)`
- If cast is genuinely not found after research, **omit the Cast field entirely** rather than writing "not found"

### Synopsis rules

- One or two sentences maximum — tight and informative, no filler
- Always in a `>` blockquote with the text in italic: `> _Synopsis here._`
- There must be a **blank line** between the metadata line and the `> _..._` line
- Language: **English**, unless the title is originally French — in that case write the synopsis in **French**
- Do not mention streaming platforms, broadcast dates, episode counts, or source material unless it is essential to understanding the plot

## Research strategy

Work through the following sources in order, stopping when you have enough for cast + synopsis. Use `uv run --with requests` for all HTTP calls.

### 1. Wikipedia REST API (fastest, try first)

```python
import requests, time
r = requests.get(
    f"https://en.wikipedia.org/api/rest_v1/page/summary/{encoded_title}",
    headers={"User-Agent": "MovieResearch/1.0"}
)
# extract = r.json().get("extract", "")
```

**Always try the Wikipedia of the title's original language first** — it will have the most complete cast list and synopsis. Use the country flag(s) in the input to infer the language:

| Flag(s) | Wikipedia language to try first |
|---|---|
| 🇫🇷 🇧🇪 🇨🇭 🇨🇦 (francophone) | `fr.wikipedia.org` |
| 🇰🇷 | `ko.wikipedia.org` |
| 🇯🇵 | `ja.wikipedia.org` |
| 🇩🇪 🇦🇹 🇨🇭 | `de.wikipedia.org` |
| 🇩🇰 | `da.wikipedia.org` |
| 🇳🇴 | `no.wikipedia.org` |
| 🇸🇪 | `sv.wikipedia.org` |
| 🇫🇮 | `fi.wikipedia.org` |
| 🇪🇸 🇲🇽 🇦🇷 🇨🇱 🇨🇴 🇵🇪 | `es.wikipedia.org` |
| 🇵🇱 | `pl.wikipedia.org` |
| 🇨🇿 | `cs.wikipedia.org` |
| 🇭🇷 | `hr.wikipedia.org` |
| 🇮🇱 | `he.wikipedia.org` |
| 🇮🇷 | `fa.wikipedia.org` |
| 🇹🇼 🇨🇳 | `zh.wikipedia.org` |
| 🇷🇺 | `ru.wikipedia.org` |
| 🇮🇸 | `is.wikipedia.org` |
| 🇷🇼 🇳🇬 🇿🇦 (African) | `en.wikipedia.org` |
| 🇺🇸 🇬🇧 🇦🇺 🇮🇪 🇳🇿 | `en.wikipedia.org` |

Then try `en.wikipedia.org` as a fallback — English articles often exist even for foreign titles and include a translated synopsis.

For a fuller article (synopsis + cast), use the MediaWiki action API with `exsentences=10`:
```
https://[lang].wikipedia.org/w/api.php?action=query&prop=extracts&titles=TITLE&format=json&redirects&exsentences=10
```

**Rate limits**: Wikipedia rate-limits aggressively. Sleep **2–3 seconds between requests**. If you get HTTP 429, sleep 8–10 seconds before retrying.

Common title patterns to try when the obvious slug fails:
- `Title_(TV_series)`, `Title_(film)`, `Title_(2023_film)`
- Encoded special characters: `%C3%A0` for à, `%C3%A9` for é, etc.
- The original-language title (not the translated one)
- The English translation of the title
- Use Wikipedia's search API to find the correct slug: `https://[lang].wikipedia.org/w/api.php?action=query&list=search&srsearch=TITLE&format=json&srlimit=3`

### 2. Rotten Tomatoes (good for cast + synopsis)

```
https://www.rottentomatoes.com/m/title_slug       # films
https://www.rottentomatoes.com/tv/title_slug      # series
```

Parse the rendered HTML — look for the "Cast & Crew" and "Synopsis" sections after stripping scripts/styles.

### 3. AlloCiné (excellent for French films and series)

```
https://www.allocine.fr/film/fichefilm_gen_cfilm=XXXXXX.html
https://www.allocine.fr/series/ficheserie-XXXXXX/
```

AlloCiné pages include a clean `Synopsis` section in plain text. Excellent for French, Belgian, and Swiss productions that don't have Wikipedia articles. The film/series ID can be found by searching `allocine.fr TITLE` via DuckDuckGo.

### 4. Arte.tv (excellent for European series)

```
https://www.arte.tv/fr/search/?q=TITLE
```

Arte's search results often include a one-line French synopsis directly in the result snippet. Good for French, Belgian, Nordic, and German series.

### 4. NRK (Norwegian series)

```
https://tv.nrk.no/serie/SLUG
```

The page title and description are usually in plain text before JS content.

### 5. Namu.wiki (Korean dramas — requires Playwright)

Korean drama pages on Namu.wiki require JavaScript rendering. Use Playwright with Chromium:

```javascript
const { chromium } = require('playwright');
// npx playwright install chromium  (first time only)
const browser = await chromium.launch();
const page = await browser.newPage();
await page.goto(`https://namu.wiki/w/${encodeURIComponent(title)}`, {
    waitUntil: 'domcontentloaded', timeout: 20000
});
await page.waitForTimeout(3000);
const text = await page.evaluate(() => document.body.innerText);
```

Look for the 기획의도 (concept/intent) or the brief description paragraph near the top of the article — that is the cleanest synopsis source.

### 6. DuckDuckGo HTML search (fallback)

```
https://html.duckduckgo.com/html/?q=TITLE+series+synopsis+cast
```

Useful when no dedicated page is found. Parse the result snippets. Note: DDG rate-limits after a few requests — add 1.5s delays.

### 7. If nothing works

Write `*Not found*` for the synopsis. Do not invent plot details.

## Batch efficiently

Fetch all titles in a single Python script to avoid repeated tool calls. Process them in order, sleep between requests, and collect results before writing the file.

```python
import requests, time

results = {}
for name, wiki_slug in titles:
    try:
        r = requests.get(f"https://en.wikipedia.org/api/rest_v1/page/summary/{wiki_slug}",
                         headers={"User-Agent": "MovieResearch/1.0"}, timeout=10)
        results[name] = r.json().get("extract", "") if r.status_code == 200 else ""
    except Exception:
        results[name] = ""
    time.sleep(2)
```

## Final file structure

```markdown
# [year or title of the list]

## Title One 🇸🇪
**Series** | **Cast**: Actor A, Actor B, Actor C

> _Synopsis._

## ✈︎ Title Two 🇺🇸
**Film (1963)** | **Cast**: Actor X, Actor Y

> _Synopsis._
```

No `---` horizontal rules between entries. No mentions of networks, streaming platforms, or production companies in the metadata line.

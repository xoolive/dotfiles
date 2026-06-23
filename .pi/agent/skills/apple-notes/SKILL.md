---
name: apple-notes
description: Work safely with Apple Notes when reading, exporting, importing, or editing notes as Markdown/HTML. Use when the user asks to inspect or edit Apple Notes, convert Apple Notes to Markdown, sync Markdown back into Apple Notes, or preserve newlines/lists/headings between Apple Notes and Markdown.
---

# Apple Notes ⇄ Markdown

Use this skill whenever working with Apple Notes content, especially when preserving newlines, headings, ordered lists, Devanagari/transliteration text, or Markdown round-trips.

## Core lessons

- Apple Notes is rich text, not Markdown.
- Apple Notes exposes note bodies through AppleScript as HTML-like rich text, but this is not clean semantic HTML.
- Reading `body` and writing it back is not idempotent: Apple Notes may rewrite tags, fonts, line breaks, headings, and the note title.
- Export/import must preserve the visual structure, not merely the raw HTML.
- Edit the smallest necessary section. Avoid rewriting the whole note unless the user explicitly asks or there is no safer option.
- Always export/backup in a temporary folder before writing back.
- If the user asks only to inspect/check, do not edit.

## Accessing Apple Notes

Use AppleScript via `osascript`.

### Find notes

```bash
osascript <<'APPLESCRIPT' 2>&1
 tell application "Notes"
   repeat with n in every note
     if (name of n) contains "My title" then
       log "---NOTE---"
       log "id: " & (id of n as text)
       log "name: " & (name of n)
       log "created: " & (creation date of n as string)
       log "modified: " & (modification date of n as string)
       try
         log "folder: " & (name of container of n)
       end try
     end if
   end repeat
 end tell
APPLESCRIPT
```

Notes with the same title can exist, including trashed notes. Prefer a stable `id` once identified. Check `container`/folder where possible, e.g. `Recently Deleted`.

### Export/read one note body

```bash
osascript <<'APPLESCRIPT' > Note.backup.html
 tell application "Notes"
   repeat with n in every note
     if (id of n as text) is "x-coredata://.../ICNote/p123" then
       return body of n
     end if
   end repeat
   error "Note not found"
 end tell
APPLESCRIPT
```

### Write/edit one note body

Only after creating a backup and preparing Apple Notes-compatible HTML:

```bash
osascript <<'APPLESCRIPT'
set htmlBody to read POSIX file "/tmp/note.updated.html" as «class utf8»
tell application "Notes"
  repeat with n in every note
    if (id of n as text) is "x-coredata://.../ICNote/p123" then
      set body of n to htmlBody
      return "updated " & (name of n)
    end if
  end repeat
  error "Note not found"
end tell
APPLESCRIPT
```

After writing, export/read again and verify the visual structure through the returned body and, when possible, by asking the user to visually check Apple Notes.

## Markdown and newline conversion rules

Markdown newlines and Apple Notes newlines do not match.

In Markdown:

- one newline often means “same paragraph”
- a blank line means “new paragraph”
- two trailing spaces or `<br>` means a hard line break

In Apple Notes:

- each visual paragraph/line may become a `<div>`
- a soft line break may become `<br>`
- a line break inside a list item may be a hidden Unicode separator, not a new `<li>`
- Apple Notes may rewrite `<h1>`, `<h2>`, `<b>`, `<span>`, `<font>`, and `<br>` combinations after import

When exporting Apple Notes to Markdown, explicitly decide whether each Apple Notes line should become:

```markdown
same paragraph
```

or a hard line break:

```markdown
line one  
line two
```

or a new paragraph:

```markdown
line one

line two
```

When importing Markdown back into Apple Notes, convert Markdown deliberately:

- `# Title` → one Apple Notes title/header line
- `## Subtitle` → one Apple Notes heading line
- blank Markdown line → explicit blank Apple Notes line, e.g. `<div><br></div>`
- ordered list → real `<ol><li>...</li></ol>`
- unordered list → real `<ul><li>...</li></ul>`
- inline code → `<code>...</code>` or another minimal style, knowing Apple Notes may rewrite it
- line break inside a list item → preserve as internal break, not as a new list item

## Headings

Do not use multiple heading tags for one visual heading.

Bad:

```html
<div>
  <h2>A</h2>
  <h2>・</h2>
  <h2>あ</h2>
</div>
```

Apple Notes may split that into multiple visual lines.

Safer:

```html
<div><h2>A・あ</h2></div>
```

The first line controls the Apple Notes title. If the first line changes, Apple Notes may rename the note.

## Lists

Preserve real list structure. This is a real ordered list:

```html
<ol>
  <li><b>first</b> lorem ipsum</li>
</ol>
```

This is only plain text and is not equivalent:

```text
1 first lorem ipsum...
```

If a list item visually contains an internal line break, keep it inside the same `<li>` rather than creating a second `<li>`.

## Verification checklist after any write

Check:

- correct note id was edited
- trashed/duplicate notes were not edited accidentally
- note title did not change unexpectedly
- headings that should be one line remain one line
- blank lines are preserved
- ordered/unordered lists are still real lists
- line breaks inside list items remain inside the same item
- transliteration text (pinyin, romaji, devanagari) is intact
- old text that should be removed is gone
- unrelated sections were not reformatted

## Safety workflow

1. Identify candidate notes by title/content.
2. Disambiguate duplicates and trashed notes; prefer stable note `id`.
3. Export the current body to a backup `.html` file.
4. Make the smallest possible HTML edit.
5. Write back with `osascript` using the stable `id`.
6. Export again to an `after` file.
7. Verify the checklist above.
8. Tell the user exactly what changed and where backups/exports were saved.

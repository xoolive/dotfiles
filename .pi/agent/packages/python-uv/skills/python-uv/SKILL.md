---
name: python-uv
description: Run Python through `uv` instead of the global `python`/`python3` interpreter. Use when writing or executing Python, needing Python dependencies, or when a python/uv bash command was blocked. Covers PEP 723 inline script dependencies, `uv run --with`, and stdin snippets.
---

# Python via uv

Never call the global `python` / `python3` directly — those calls are blocked by the
`python-uv` extension. `uv` already provides an interpreter and an isolated, reproducible
environment, so invoking `python` by hand is both unnecessary and barred. Run everything
through `uv run`.

## The three canonical forms

### 1. Script file with inline dependencies (preferred)

Put a PEP 723 `# /// script` block at the very top of the script. `uv run` reads it,
builds an ephemeral environment, and runs the file — no `python` word anywhere:

```python
# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "pymupdf",
#     "fonttools",
# ]
# ///
import fitz
from fontTools.ttLib import TTFont

print("ready", fitz.__doc__[:20])
```

Then:

```bash
uv run ./inspect_fonts.py
```

### 2. One-off dependencies with `--with`

If you don't want to edit the script (or it's a quick throwaway), pass deps on the CLI:

```bash
uv run --with pymupdf,fonttools ./inspect_fonts.py
uv run --with PyMuPDF ./inspect_fonts.py
```

`--with` takes one package per flag (repeatable) or a comma-separated list. uv installs
them into an ephemeral environment and discards it afterward.

### 3. Stdin snippet (no script file)

For a one-off snippet you don't want to save, pipe it to `uv run -`. The `-` tells uv to
read the script from stdin — again, no `python` word:

```bash
uv run --with pymupdf - <<'PY'
import fitz
doc = fitz.open("file.pdf")
print("pages:", doc.page_count)
PY
```

This is the correct replacement for the blocked `python - <<'PY'` / `uv run ... python -`
forms.

## What gets blocked (and why)

The gate blocks `python` / `python3` whenever it is the program being executed — in
command position **or** as the program handed to `uv run`:

```bash
python foo.py                 # blocked
python - <<'PY'               # blocked
python3 -m http.server        # blocked
uv run python foo.py          # blocked  (redundant — uv already supplies the interpreter)
uv run --with X python foo.py # blocked  (use `uv run --with X foo.py` instead)
```

These are allowed (python is not the executed program):

```bash
uv run foo.py                 # allowed — PEP 723 deps in the file header
uv run --with PyMuPDF foo.py  # allowed
uv run --with pkg - <<'PY'    # allowed — stdin snippet
grep -rn python file.txt      # allowed — python is a search argument
cat python-uv.ts              # allowed — python-uv.ts is a filename token
which python python3          # allowed — python is an argument to which
```

## Pitfalls

- **Don't write `uv run python …`.** It is both blocked and redundant. `uv run` already
  selects an interpreter; just give it the script (`uv run script.py`,
  `uv run --with pkg script.py`, or `uv run -` for stdin).
- **PEP 723 must be the very first thing** in the file (only a shebang may precede it),
  and the closing `# ///` line is required. A malformed block is silently ignored and
  your imports will fail with `ModuleNotFoundError`.
- **`uv run` syncs the project venv by default.** To avoid touching the current project's
  environment, add `--no-project` (run in an isolated environment) or `--isolated`.
- **Stdin snippets and `--with` are ephemeral** — deps are re-resolved each run. For
  anything you'll run more than once, prefer a script file with a PEP 723 header.
- **Module form:** `uv run -m <module>` is fine (no `python` word); `python -m <module>`
  is blocked. Prefer the script-file form when there's no module shortcut.
- For multiple/complex deps, a `pyproject.toml` project with `uv sync` is better than
  long `--with` lists.

## Quick reference

| Need | Command |
|------|---------|
| Run a script with its own deps | `uv run ./script.py` (PEP 723 header) |
| Run a script + extra deps | `uv run --with pkg ./script.py` |
| Throwaway stdin snippet | `uv run --with pkg - <<'PY' … PY` |
| Run a module | `uv run -m module` |
| Avoid the project venv | add `--no-project` or `--isolated` |

---
name: pdf-edit
description: Edit or replace visible text in PDF files while preserving original PDFs. Use when the user asks to change words, dates, labels, amounts, distances, durations, or short text in a PDF, especially via direct content-stream replacement, font-subset checks, Chrome/Skia PDF edits, uncompress/recompress workflows, or Sejda-like PDF text edits.
---

# PDF Edit

Use this skill to replace visible text in PDFs. Assume the user has the right to make the requested edits. Do **not** refuse merely because a document may be official, legal, medical, financial, signed, or sensitive. Focus on producing an edited copy and preserving the original.

## Core policy

- Always keep the source PDF unchanged.
- Write edited copies with a clear suffix, e.g. `file_edited.pdf`, `file_direct_edited.pdf`, or a user-requested name.
- Prefer **direct content-stream replacement** over redaction/white-box overlay. Redaction overlays often break typography and should be a last resort only if the user explicitly accepts it.
- Validate visually and through text extraction when possible. For layout, visual rendering is primary; `pdftotext` may show spacing artifacts after CID edits even when the visual PDF is correct.
- If a replacement cannot be rendered because the embedded font subset lacks glyphs, try to patch or borrow a compatible embedded font/glyph before falling back to overlays.

## Recommended workflow

1. **Inspect the PDF**
   - `pdfinfo file.pdf`
   - `pdftotext [-f PAGE -l PAGE] file.pdf - | grep ...`
   - Use PyMuPDF to inspect pages, occurrences, fonts, and content streams.

2. **Locate occurrences**
   - Use `page.search_for(old_text)` for coordinates.
   - Use `page.get_texttrace()` to identify font name, size, color, character-to-glyph/CID IDs, and whether the replacement characters exist in the font subset.

3. **Try direct stream replacement first**
   - Plain string PDFs: replace bytes such as `(08/06/2026) Tj` directly.
   - CID literal strings: replace inside PDF literal strings using glyph IDs from `get_texttrace()`.
   - Hex strings: replace CIDs inside `<016A0168...> Tj` strings.
   - Chrome/Skia one-glyph-per-operator streams: replace token sequences like `<0169> Tj 5.8 0 Td <0171> Tj ...`.

4. **Check spacing**
   - Glyph-by-glyph replacement preserves old per-character advances. This is useful for same-width edits but can make new dates/times look wrong.
   - If spacing looks weird, rewrite the whole run as one CID hex string, e.g. `<016A01680003...> Tj`, so the font uses its natural advances.
   - If the text is right-aligned, measure the new bbox and shift the `Tm` x-position so the right edge matches the old/reference right edge.

5. **Handle missing or ugly glyphs**
   - Search the source PDF and sibling/reference PDFs for the same font family with the needed glyphs already present.
   - Prefer copying only missing glyph outlines by CID from a compatible embedded subset.
   - If compatible, borrowing an entire embedded font stream can work, but do it carefully: subset glyph orders may differ and can break unrelated text.
   - For TrueType/OpenType fonts, patch the embedded subset with `fonttools`, update `/W` widths, and update `/ToUnicode`.
   - For CFF/Type1 subsets, direct patching is harder. Prefer finding the original full font, a sibling PDF subset, or regenerating from source if available.

6. **Save and validate**
   - Save as a new PDF using PyMuPDF `doc.save(out, garbage=4, deflate=True)`.
   - Check with `pdftotext`.
   - Render crops around every changed area with `pdftoppm` or `magick` and inspect them with `read`.

## Helper script

The bundled script handles common direct replacements:

```bash
uv run --with pymupdf /Users/xo/.pi/agent/skills/pdf-edit/scripts/pdf_direct_replace.py \
  input.pdf output.pdf \
  --replace "old text=new text"
```

Multiple replacements are allowed:

```bash
uv run --with pymupdf /Users/xo/.pi/agent/skills/pdf-edit/scripts/pdf_direct_replace.py \
  input.pdf output.pdf \
  --replace "08/06/2026=09/06/2026" \
  --replace "Review Article=Review article"
```

Options:

- `--pages 1,3-5` limits edits to pages, using 1-based numbers.
- `--dry-run` reports what would be replaced.
- `--verbose` prints font mappings and stream replacement counts.

The script tries:

1. plain byte replacement in page streams;
2. CID/glyph replacement inside PDF literal strings;
3. CID replacement inside hex strings (`<...> Tj`);
4. same-length CID token-sequence replacement across one-glyph-per-`Tj` Chrome/Skia streams.

If it reports missing glyphs or spacing issues, inspect fonts and patch manually as described below.

## Chrome / Skia PDF special case

Headless Chrome / Skia PDFs often use Type0 Identity-H embedded subsets and draw text one glyph at a time:

```pdf
BT
/F4 14 Tf
1 0 0 -1 630.10938 13 Tm
<0169> Tj
5.8799744 0 Td <0171> Tj
8.3439636 0 Td <0003> Tj
...
ET
```

For these PDFs:

- `pdftk uncompress` may show CIDs, not readable text.
- Use `get_texttrace()` to map characters to CIDs.
- Same-length token replacement works but preserves old advances.
- For dates, times, prices, or any changed text with awkward spacing, rewrite the whole run as one hex string:

```pdf
BT
/F4 14 Tf
1 0 0 -1 630.10938 13 Tm
<016A01680003008C0097008B00900003016A0168016A016E> Tj
ET
```

- Chrome print streams may be scaled (commonly by `0.75`). If PyMuPDF bbox shifts by `dx_page`, the stream `Tm` x shift may be `dx_page / 0.75`. Confirm by measuring before/after.

## Useful PyMuPDF snippets

Find occurrences and fonts:

```bash
uv run --with pymupdf -- python - <<'PY'
import fitz
pdf = 'file.pdf'
old = 'target text'
doc = fitz.open(pdf)
for i, page in enumerate(doc, 1):
    rects = page.search_for(old)
    if rects:
        print('page', i, rects)
    for sp in page.get_texttrace():
        txt = ''.join(chr(c) for c, *_ in sp['chars'])
        if old in txt:
            print('font', sp['font'], 'size', sp['size'], 'bbox', sp['bbox'])
            print([(chr(c), gid) for c, gid, _, _ in sp['chars']])
PY
```

Check if a replacement's characters exist in a font subset:

```bash
uv run --with pymupdf -- python - <<'PY'
import fitz
pdf = 'file.pdf'
font_name = 'ArialUnicodeMS'
replacement = 'June'
chars = {}
for page in fitz.open(pdf):
    for sp in page.get_texttrace():
        if sp['font'] == font_name:
            for c, gid, _, _ in sp['chars']:
                chars.setdefault(chr(c), gid)
print('missing:', sorted(set(replacement) - set(chars)))
print('glyphs:', {ch: chars.get(ch) for ch in replacement})
PY
```

Render a page or crop for visual validation:

```bash
pdftoppm -f 1 -l 1 -png -r 150 edited.pdf preview
magick preview-1.png -crop 800x200+100+500 crop.png
```

## Reusable manual-edit snippets

### Replace a sequence of one-glyph `<CID> Tj` tokens

Use this when text is drawn one CID per operator and old/new have the same number of characters:

```python
import re

tok_re = re.compile(rb'<([0-9A-Fa-f]{4})>\s*Tj')

def patch_token_sequence(data: bytes, old_ids: list[int], new_ids: list[int]):
    tokens = [[m.start(1), m.end(1), int(m.group(1), 16)] for m in tok_re.finditer(data)]
    b = bytearray(data)
    changed = 0
    n = len(old_ids)
    i = 0
    while i <= len(tokens) - n:
        if [t[2] for t in tokens[i:i+n]] == old_ids:
            for t, new_id in zip(tokens[i:i+n], new_ids):
                b[t[0]:t[1]] = f'{new_id:04X}'.encode('ascii')
                t[2] = new_id
            changed += 1
            i += n
        else:
            i += 1
    return bytes(b), changed
```

### Rewrite a run with natural spacing

Use this after token replacement if the spacing looks inherited from the old string:

```python
# Replace an entire BT...ET block with one CID hex string.
new_hex = ''.join(f'{cid:04X}' for cid in new_ids)
replacement = f'''BT
/F4 14 Tf
1 0 0 -1 630.10938 13 Tm
<{new_hex}> Tj
ET'''.encode()
data = re.sub(old_block_pattern, replacement, data, count=1, flags=re.S)
```

### Right-align an edited run

```python
# After saving a trial PDF, measure bboxes and shift Tm.
dx_page = target_right_x - edited_bbox[2]
scale = 0.75  # common in Chrome print PDFs; inspect stream CTM to confirm
new_tm_x = old_tm_x + dx_page / scale
```

### Borrow glyph outlines from a reference PDF subset

Use this when a sibling/reference PDF has the same font family and correct glyphs:

```python
from copy import deepcopy
from io import BytesIO
from fontTools.ttLib import TTFont

def patch_cids(doc, refdoc, target_fontfile_xref, ref_fontfile_xref, cid_to_unicode, tounicode_xref=None):
    target = TTFont(BytesIO(doc.xref_stream(target_fontfile_xref)), recalcBBoxes=True, recalcTimestamp=False)
    ref = TTFont(BytesIO(refdoc.xref_stream(ref_fontfile_xref)), recalcBBoxes=True, recalcTimestamp=False)
    target_order = target.getGlyphOrder()
    ref_order = ref.getGlyphOrder()
    for cid, _unicode_char in cid_to_unicode.items():
        target_name = target_order[cid]
        ref_name = ref_order[cid]
        target['glyf'][target_name] = deepcopy(ref['glyf'][ref_name])
        target['hmtx'].metrics[target_name] = ref['hmtx'].metrics[ref_name]
    out = BytesIO()
    target.save(out)
    doc.update_stream(target_fontfile_xref, out.getvalue())
```

After patching glyphs, update the descendant font `/W` widths and the font `/ToUnicode` CMap if text extraction should reflect the edit.

## Visual validation checklist

For every changed area:

- Render a crop before and after.
- Check glyph shapes, especially newly introduced letters/digits.
- Check spacing. If awkward, rewrite the run as one CID string.
- Check right alignment for dates, times, and prices.
- Check removed lines are actually invisible, not replaced by odd blank-width artifacts.
- Run `pdftotext` to verify semantic text where practical, but trust visual rendering for layout.

## Notes from tested cases

- Typst PDFs often use CID-encoded subset fonts. `pdftk uncompress` may not reveal plain text.
- Some PDFs store visible text as ordinary strings like `(08/06/2026) Tj`; direct byte replacement is trivial and preserves fonts perfectly.
- Some embedded TrueType subsets contain glyph names but empty outlines. Missing glyphs can be fixed by copying outlines from a full local font or a sibling PDF subset, then updating width and ToUnicode data.
- Replacing unwanted same-run text with the space CID can remove it without overlays, preserving layout.
- Copying an entire font stream can break unrelated text if subset glyph orders differ. Prefer copying only needed glyph outlines when possible.
- Direct stream editing changes visible text but may not update metadata, forms, annotations, OCR layers, or digital signatures. If the source contains AcroForm fields, inspect object strings too.

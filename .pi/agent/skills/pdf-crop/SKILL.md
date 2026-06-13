---
name: pdf-crop
description: Crops scanned PDF files by removing blank margins around meaningful content. Use when the user wants to crop or trim a scanned PDF, passport scan, ID scan, receipt scan, or remove blank whitespace from a PDF while keeping file size reasonable.
compatibility: Requires ImageMagick `magick`; optionally uses `pdfimages` to infer source DPI.
---

# PDF Crop

Use this skill when the user provides a scanned PDF and wants to keep only the meaningful content by removing blank margins or whitespace.

## Workflow

1. Confirm the input PDF path.
2. Create a new output file; never overwrite the original unless the user explicitly asks.
3. Use the helper script:

```bash
~/.pi/agent/skills/pdf-crop/scripts/crop_pdf_whitespace.py INPUT.pdf
```

By default this writes `INPUT_cropped.pdf` next to the input.

## Useful Options

```bash
# Choose the output path
~/.pi/agent/skills/pdf-crop/scripts/crop_pdf_whitespace.py INPUT.pdf -o OUTPUT.pdf

# Keep an original-like file size; use 200 dpi for most phone or scanner PDFs
~/.pi/agent/skills/pdf-crop/scripts/crop_pdf_whitespace.py INPUT.pdf --dpi 200 --quality 85

# Add a small padding around the detected content, in output pixels
~/.pi/agent/skills/pdf-crop/scripts/crop_pdf_whitespace.py INPUT.pdf --padding 12

# More aggressive white/noise removal
~/.pi/agent/skills/pdf-crop/scripts/crop_pdf_whitespace.py INPUT.pdf --threshold 210

# If top or bottom whitespace remains because of scan noise, require more dark pixels per row/column
~/.pi/agent/skills/pdf-crop/scripts/crop_pdf_whitespace.py INPUT.pdf --min-fraction 0.02

# If the crop is too tight or cuts off faint content, relax the row/column filter
~/.pi/agent/skills/pdf-crop/scripts/crop_pdf_whitespace.py INPUT.pdf --min-fraction 0.01 --padding 12
```

## Defaults

- The script uses `--min-fraction 0.015` by default. This avoids keeping full-page height or width because of tiny noise specks in otherwise blank areas.
- The script detects the content bounding box at low resolution, then crops at the output DPI.
- Avoid unnecessary `--dpi 300` for documents that are already 200 dpi, because it can inflate file size significantly.
- If `pdfimages` is available, the script tries to infer the original embedded image DPI and uses that as the default.
- The script is intended for single-page scanned PDFs. For multi-page PDFs, process pages separately or ask before deciding how to handle them.

## Verification

After cropping, compare file size and page dimensions:

```bash
ls -lh INPUT.pdf OUTPUT.pdf
pdfinfo OUTPUT.pdf | grep 'Page size'
pdfimages -list OUTPUT.pdf
```

If the output is not cropped vertically, rerun with `--min-fraction 0.02`. If the output is cropped too tightly, rerun with `--min-fraction 0.01 --padding 12`.

#!/usr/bin/env python3
"""Crop blank whitespace from a single-page scanned PDF using ImageMagick."""
from __future__ import annotations

import argparse
import math
import re
import subprocess
import sys
from pathlib import Path


def run(cmd: list[str], *, capture: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd,
        check=True,
        stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.PIPE if capture else None,
    )


def require_tool(name: str) -> None:
    try:
        run(["bash", "-lc", f"command -v {name}"], capture=True)
    except subprocess.CalledProcessError:
        raise SystemExit(f"Missing required tool: {name}")


def infer_pdf_dpi(pdf: Path) -> int | None:
    """Return the first image x-ppi reported by pdfimages, if available."""
    try:
        cp = subprocess.run(
            ["pdfimages", "-list", str(pdf)],
            check=True,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )
    except Exception:
        return None

    for line in cp.stdout.splitlines():
        parts = line.split()
        # pdfimages rows start with page number and include x-ppi y-ppi before size/ratio.
        if len(parts) >= 14 and parts[0].isdigit() and parts[1].isdigit():
            try:
                return int(parts[12])
            except ValueError:
                continue
    return None


def read_pgm(data: bytes) -> tuple[int, int, bytes]:
    # Parse a binary P5 PGM from ImageMagick. Supports comment lines.
    pos = 0

    def next_token() -> bytes:
        nonlocal pos
        while pos < len(data) and data[pos] in b" \t\r\n":
            pos += 1
        if pos < len(data) and data[pos] == ord("#"):
            while pos < len(data) and data[pos] not in b"\r\n":
                pos += 1
            return next_token()
        start = pos
        while pos < len(data) and data[pos] not in b" \t\r\n":
            pos += 1
        return data[start:pos]

    magic = next_token()
    if magic != b"P5":
        raise ValueError("Expected P5 PGM from ImageMagick")
    width = int(next_token())
    height = int(next_token())
    max_value = int(next_token())
    if max_value != 255:
        raise ValueError(f"Unsupported PGM max value: {max_value}")
    while pos < len(data) and data[pos] in b" \t\r\n":
        pos += 1
    pixels = data[pos:]
    if len(pixels) < width * height:
        raise ValueError("Truncated PGM data")
    return width, height, pixels[: width * height]


def detect_bbox(pdf: Path, detect_dpi: int, threshold: int, min_fraction: float) -> tuple[int, int, int, int, int, int]:
    cp = run([
        "magick",
        "-density", str(detect_dpi),
        str(pdf),
        "-background", "white",
        "-alpha", "remove",
        "-alpha", "off",
        "-colorspace", "Gray",
        "-depth", "8",
        "pgm:-",
    ])
    width, height, pixels = read_pgm(cp.stdout)

    min_row_dark = max(3, int(width * min_fraction))
    min_col_dark = max(3, int(height * min_fraction))

    rows: list[int] = []
    for y in range(height):
        row = pixels[y * width : (y + 1) * width]
        dark = sum(1 for p in row if p < threshold)
        if dark >= min_row_dark:
            rows.append(y)

    cols: list[int] = []
    for x in range(width):
        dark = 0
        for y in range(height):
            if pixels[y * width + x] < threshold:
                dark += 1
                if dark >= min_col_dark:
                    cols.append(x)
                    break

    if not rows or not cols:
        raise SystemExit("Could not detect non-white content. Try a higher --threshold or lower --min-fraction.")

    return min(cols), min(rows), max(cols) + 1, max(rows) + 1, width, height


def main() -> int:
    parser = argparse.ArgumentParser(description="Crop blank whitespace from a single-page scanned PDF.")
    parser.add_argument("input", type=Path, help="Input PDF")
    parser.add_argument("-o", "--output", type=Path, help="Output PDF path")
    parser.add_argument("--dpi", type=int, help="Output render DPI. Default: inferred from PDF image DPI, else 200.")
    parser.add_argument("--detect-dpi", type=int, default=100, help="DPI used for content detection. Default: 100.")
    parser.add_argument("--quality", type=int, default=85, help="JPEG quality for output PDF. Default: 85.")
    parser.add_argument("--threshold", type=int, default=220, help="Pixels darker than this count as content. Default: 220.")
    parser.add_argument("--min-fraction", type=float, default=0.015, help="Minimum dark-pixel fraction for a row/column. Default: 0.015.")
    parser.add_argument("--padding", type=int, default=0, help="Padding to add around detected content, in output pixels. Default: 0.")
    args = parser.parse_args()

    require_tool("magick")

    src = args.input.expanduser().resolve()
    if not src.exists():
        raise SystemExit(f"Input not found: {src}")
    if src.suffix.lower() != ".pdf":
        raise SystemExit("Input must be a PDF")

    output = args.output.expanduser().resolve() if args.output else src.with_name(f"{src.stem}_cropped.pdf")
    dpi = args.dpi or infer_pdf_dpi(src) or 200

    left, top, right, bottom, detect_w, detect_h = detect_bbox(src, args.detect_dpi, args.threshold, args.min_fraction)
    scale = dpi / args.detect_dpi
    crop_left = max(0, math.floor(left * scale) - args.padding)
    crop_top = max(0, math.floor(top * scale) - args.padding)
    crop_right = math.ceil(right * scale) + args.padding
    crop_bottom = math.ceil(bottom * scale) + args.padding
    crop_w = max(1, crop_right - crop_left)
    crop_h = max(1, crop_bottom - crop_top)
    geometry = f"{crop_w}x{crop_h}+{crop_left}+{crop_top}"

    run([
        "magick",
        "-density", str(dpi),
        str(src),
        "-background", "white",
        "-alpha", "remove",
        "-alpha", "off",
        "-crop", geometry,
        "+repage",
        "-compress", "JPEG",
        "-quality", str(args.quality),
        str(output),
    ], capture=True)

    print(f"Input:  {src}")
    print(f"Output: {output}")
    print(f"DPI: {dpi}; detection: {args.detect_dpi} dpi ({detect_w}x{detect_h})")
    print(f"Crop geometry: {geometry}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Direct PDF text replacement helper.

Keeps the input unchanged and writes a new PDF. Tries plain byte replacement,
CID/glyph replacement inside PDF literal strings, hex-string text objects, and
same-length Chrome/Skia one-glyph-per-Tj token sequences.
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path

import fitz  # PyMuPDF

LITERAL_RE = re.compile(rb"\((?:\\.|[^\\)])*\)", re.S)
HEX_TJ_RE = re.compile(rb"<([0-9A-Fa-f\s]+)>\s*Tj", re.S)
TOKEN_TJ_RE = re.compile(rb"<([0-9A-Fa-f]{4})>\s*Tj")


def pdf_unescape_literal(body: bytes) -> bytes:
    out = bytearray()
    i = 0
    maps = {
        ord("n"): 10,
        ord("r"): 13,
        ord("t"): 9,
        ord("b"): 8,
        ord("f"): 12,
        ord("("): 40,
        ord(")"): 41,
        ord("\\"): 92,
    }
    while i < len(body):
        if body[i] != 92:
            out.append(body[i])
            i += 1
            continue
        i += 1
        if i >= len(body):
            break
        c = body[i]
        if c in maps:
            out.append(maps[c])
            i += 1
        elif 48 <= c <= 55:
            j = i
            digs: list[str] = []
            while j < len(body) and len(digs) < 3 and 48 <= body[j] <= 55:
                digs.append(chr(body[j]))
                j += 1
            out.append(int("".join(digs), 8))
            i = j
        elif c in (10, 13):
            while i < len(body) and body[i] in (10, 13):
                i += 1
        else:
            out.append(c)
            i += 1
    return bytes(out)


def pdf_escape_literal(raw: bytes) -> bytes:
    # Conservative but valid: octal-escape every byte in the literal string.
    return b"(" + b"".join((b"\\%03o" % b) for b in raw) + b")"


def parse_pages(spec: str | None, page_count: int) -> set[int]:
    if not spec:
        return set(range(page_count))
    pages: set[int] = set()
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            a, b = part.split("-", 1)
            start = int(a) if a else 1
            end = int(b) if b else page_count
            pages.update(range(start - 1, end))
        else:
            pages.add(int(part) - 1)
    bad = [p + 1 for p in pages if p < 0 or p >= page_count]
    if bad:
        raise SystemExit(f"page number out of range: {bad}")
    return pages


@dataclass(frozen=True)
class Replacement:
    old: str
    new: str


def parse_replace(value: str) -> Replacement:
    if "=" not in value:
        raise argparse.ArgumentTypeError("replacement must be OLD=NEW")
    old, new = value.split("=", 1)
    if not old:
        raise argparse.ArgumentTypeError("OLD side must not be empty")
    return Replacement(old, new)


def glyph_ids(chars_to_gid: dict[str, int], text: str) -> list[int] | None:
    try:
        return [chars_to_gid[ch] for ch in text]
    except KeyError:
        return None


def glyph_bytes(chars_to_gid: dict[str, int], text: str) -> bytes | None:
    ids = glyph_ids(chars_to_gid, text)
    if ids is None:
        return None
    return b"".join(g.to_bytes(2, "big") for g in ids)


def collect_font_maps(doc: fitz.Document, page_indexes: set[int], verbose: bool) -> dict[str, dict[str, int]]:
    maps: dict[str, dict[str, int]] = {}
    for page_index in page_indexes:
        page = doc[page_index]
        for span in page.get_texttrace():
            font = span.get("font", "")
            chars = maps.setdefault(font, {})
            for c, gid, _origin, _bbox in span["chars"]:
                chars.setdefault(chr(c), gid)
    if verbose:
        for font, chars in sorted(maps.items()):
            print(f"font {font!r}: {len(chars)} chars", file=sys.stderr)
    return maps


def replace_literals(data: bytes, old_raw: bytes, new_raw: bytes) -> tuple[bytes, int]:
    count = 0

    def repl(match: re.Match[bytes]) -> bytes:
        nonlocal count
        raw = pdf_unescape_literal(match.group()[1:-1])
        n = raw.count(old_raw)
        if not n:
            return match.group()
        count += n
        return pdf_escape_literal(raw.replace(old_raw, new_raw))

    return LITERAL_RE.sub(repl, data), count


def replace_hex_tj_strings(data: bytes, old_raw: bytes, new_raw: bytes) -> tuple[bytes, int]:
    """Replace CIDs inside <...> Tj strings."""
    count = 0

    def repl(match: re.Match[bytes]) -> bytes:
        nonlocal count
        body = re.sub(rb"\s+", b"", match.group(1))
        try:
            raw = bytes.fromhex(body.decode("ascii"))
        except ValueError:
            return match.group()
        n = raw.count(old_raw)
        if not n:
            return match.group()
        count += n
        return b"<" + raw.replace(old_raw, new_raw).hex().upper().encode("ascii") + b"> Tj"

    return HEX_TJ_RE.sub(repl, data), count


def replace_token_sequence(data: bytes, old_ids: list[int], new_ids: list[int]) -> tuple[bytes, int]:
    """Replace same-length one-glyph-per-Tj CID token sequences.

    This preserves existing Td advances, which may be useful for same-width edits
    but can cause awkward spacing for changed text. If spacing looks bad, rewrite
    the whole run manually as one <...> Tj string.
    """
    if len(old_ids) != len(new_ids):
        return data, 0
    tokens = [[m.start(1), m.end(1), int(m.group(1), 16)] for m in TOKEN_TJ_RE.finditer(data)]
    if not tokens:
        return data, 0
    b = bytearray(data)
    changed = 0
    n = len(old_ids)
    i = 0
    while i <= len(tokens) - n:
        if [t[2] for t in tokens[i : i + n]] == old_ids:
            for t, new_id in zip(tokens[i : i + n], new_ids):
                b[t[0] : t[1]] = f"{new_id:04X}".encode("ascii")
                t[2] = new_id
            changed += 1
            i += n
        else:
            i += 1
    return bytes(b), changed


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("input", help="source PDF; never modified")
    ap.add_argument("output", help="edited output PDF")
    ap.add_argument("--replace", action="append", type=parse_replace, required=True, help="OLD=NEW; may be repeated")
    ap.add_argument("--pages", help="1-based pages, e.g. 1,3-5. Default: all pages")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()

    src = Path(args.input)
    dst = Path(args.output)
    if src.resolve() == dst.resolve():
        raise SystemExit("output must differ from input")

    doc = fitz.open(src)
    page_indexes = parse_pages(args.pages, len(doc))
    font_maps = collect_font_maps(doc, page_indexes, args.verbose)

    total = 0
    missing: list[str] = []

    for page_index in sorted(page_indexes):
        page = doc[page_index]
        for xref in page.get_contents() or []:
            data = doc.xref_stream(xref)
            changed = False
            for rep in args.replace:
                # 1. Plain byte replacement, good for WinAnsi/simple strings.
                old_b = rep.old.encode("latin1", "ignore")
                new_b = rep.new.encode("latin1", "ignore")
                if old_b and old_b.decode("latin1", "ignore") == rep.old:
                    n = data.count(old_b)
                    if n:
                        data = data.replace(old_b, new_b)
                        total += n
                        changed = True
                        if args.verbose:
                            print(f"page {page_index+1} xref {xref}: plain {rep.old!r} x{n}", file=sys.stderr)

                # 2-4. CID/glyph replacement. Try all font maps that can encode both strings.
                for font, fmap in font_maps.items():
                    old_g = glyph_bytes(fmap, rep.old)
                    new_g = glyph_bytes(fmap, rep.new)
                    old_ids = glyph_ids(fmap, rep.old)
                    new_ids = glyph_ids(fmap, rep.new)
                    if old_g is None or old_ids is None:
                        continue
                    if new_g is None or new_ids is None:
                        miss = sorted(set(rep.new) - set(fmap))
                        missing.append(f"{rep.new!r} in font {font!r}: missing {miss}")
                        continue

                    new_data, n = replace_literals(data, old_g, new_g)
                    if n:
                        data = new_data
                        total += n
                        changed = True
                        if args.verbose:
                            print(f"page {page_index+1} xref {xref}: literal font={font!r} {rep.old!r} x{n}", file=sys.stderr)

                    new_data, n = replace_hex_tj_strings(data, old_g, new_g)
                    if n:
                        data = new_data
                        total += n
                        changed = True
                        if args.verbose:
                            print(f"page {page_index+1} xref {xref}: hex-string font={font!r} {rep.old!r} x{n}", file=sys.stderr)

                    new_data, n = replace_token_sequence(data, old_ids, new_ids)
                    if n:
                        data = new_data
                        total += n
                        changed = True
                        if args.verbose:
                            print(
                                f"page {page_index+1} xref {xref}: token-sequence font={font!r} {rep.old!r} x{n} "
                                "(check spacing visually)",
                                file=sys.stderr,
                            )
            if changed and not args.dry_run:
                doc.update_stream(xref, data)

    # Some PDFs also keep values in object dictionaries / forms. This is not the main path,
    # but it helps simple AcroForm/object-string cases.
    for rep in args.replace:
        for xref in range(1, doc.xref_length()):
            try:
                obj = doc.xref_object(xref, compressed=False)
            except Exception:
                continue
            n = obj.count(rep.old)
            if n:
                total += n
                if args.verbose:
                    print(f"object {xref}: object-string {rep.old!r} x{n}", file=sys.stderr)
                if not args.dry_run:
                    doc.update_object(xref, obj.replace(rep.old, rep.new))

    print(f"replacements: {total}")
    if missing and args.verbose:
        print("missing glyph notes:", file=sys.stderr)
        for line in sorted(set(missing)):
            print("  " + line, file=sys.stderr)

    if args.dry_run:
        print("dry-run: not writing output")
        return 0
    if total == 0:
        print("warning: no replacements made", file=sys.stderr)
    doc.save(dst, garbage=4, deflate=True)
    print(f"wrote: {dst}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

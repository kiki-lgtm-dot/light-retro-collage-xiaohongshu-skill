#!/usr/bin/env python3
"""Create a compact contact sheet from rendered 3:4 page PNGs."""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
import warnings
from pathlib import Path

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError as exc:  # pragma: no cover
    raise SystemExit(
        "Pillow is required. Install scripts/requirements.txt in the active Python environment."
    ) from exc


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pages", type=Path, help="Directory containing numbered PNG pages")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--columns", type=int, default=3)
    args = parser.parse_args()
    paths = sorted(args.pages.glob("*.png"))
    if not paths:
        raise SystemExit(f"No PNG pages found in {args.pages}")
    if any(not re.fullmatch(r"[0-9]{2}\.png", path.name) for path in paths):
        raise SystemExit("Page directory contains a PNG that is not named with a two-digit page number")
    if len(paths) > 12:
        raise SystemExit("Contact sheets support at most 12 pages")
    manifest_path = args.pages.parent / "manifest.json"
    if manifest_path.is_file():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            count = int(manifest["page_count"])
        except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
            raise SystemExit(f"Invalid manifest beside page directory: {exc}") from exc
        if not 4 <= count <= 12:
            raise SystemExit("Manifest page_count must be between 4 and 12")
        expected = [f"{number:02d}.png" for number in range(1, count + 1)]
        actual = [path.name for path in paths]
        if actual != expected:
            raise SystemExit(f"Page files do not match manifest: expected {expected}, got {actual}")
    columns = min(max(1, args.columns), len(paths))
    thumb_w, thumb_h = 270, 360
    gap, label_h, outer = 24, 32, 32
    rows = math.ceil(len(paths) / columns)
    width = outer * 2 + columns * thumb_w + (columns - 1) * gap
    height = outer * 2 + rows * (thumb_h + label_h) + (rows - 1) * gap
    sheet = Image.new("RGB", (width, height), (236, 232, 220))
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default()
    for index, path in enumerate(paths):
        row, column = divmod(index, columns)
        x = outer + column * (thumb_w + gap)
        y = outer + row * (thumb_h + label_h + gap)
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(path) as page:
                page = page.convert("RGB")
                page.thumbnail((thumb_w, thumb_h), Image.Resampling.LANCZOS)
                px = x + (thumb_w - page.width) // 2
                py = y + (thumb_h - page.height) // 2
                sheet.paste(page, (px, py))
        draw.text((x, y + thumb_h + 8), path.stem, font=font, fill=(32, 35, 38))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(args.output, "PNG", optimize=True)
    print(args.output.resolve())
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
        print(f"ERROR: contact sheet could not be created ({type(exc).__name__})", file=sys.stderr)
        raise SystemExit(2) from None

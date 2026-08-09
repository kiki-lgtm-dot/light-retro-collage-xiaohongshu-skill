#!/usr/bin/env python3
"""Render sourced Xiaohongshu note pages and emit pixel-level layout evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import random
import re
import sys
import warnings
from datetime import date
from pathlib import Path, PureWindowsPath
from typing import Any
from urllib.parse import urlsplit

try:
    from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont
except ImportError as exc:  # pragma: no cover - exercised in dependency-poor installs
    raise SystemExit(
        "Pillow is required. Install scripts/requirements.txt in the active Python environment."
    ) from exc

try:
    from jsonschema import Draft202012Validator
    from jsonschema.exceptions import SchemaError
except ImportError as exc:  # pragma: no cover - exercised in dependency-poor installs
    raise SystemExit(
        "jsonschema is required. Install scripts/requirements.txt in the active Python environment."
    ) from exc


WIDTH = 1080
HEIGHT = 1440
TEXT_CLEARANCE = 36
TEXT_MARGIN = 72
NON_TEXT_MARGIN = 24
BUILTIN_MOTIFS = {
    "anatomy",
    "benefits",
    "blocks",
    "folder",
    "magnifier",
    "repeat",
    "sources",
    "workflow",
}

SKILL_ROOT = Path(__file__).resolve().parents[1]


def hex_rgba(value: str, alpha: int = 255) -> tuple[int, int, int, int]:
    value = value.lstrip("#")
    if len(value) != 6:
        raise ValueError(f"invalid six-digit hex color: {value}")
    return (int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16), alpha)


def load_palette() -> dict[str, tuple[int, int, int, int]]:
    path = SKILL_ROOT / "assets" / "palettes" / "light-retro-collage.json"
    with path.open("r", encoding="utf-8") as handle:
        raw = json.load(handle)
    palette = {key: hex_rgba(value) for key, value in raw.items()}
    palette["grid"] = (*palette["grid"][:3], 110)
    return palette


PALETTE = load_palette()

FONT_CANDIDATES = [
    "/System/Library/Fonts/Hiragino Sans GB.ttc",
    "/System/Library/Fonts/STHeiti Medium.ttc",
    "/System/Library/Fonts/PingFang.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/opentype/source-han-sans/SourceHanSansSC-Regular.otf",
    "C:/Windows/Fonts/msyh.ttc",
    "C:/Windows/Fonts/simhei.ttf",
]


def read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError("project.json must contain a JSON object")
    return data


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def short_tag_is_valid(value: str, ascii_limit: int) -> bool:
    if not value or any(char.isspace() for char in value):
        return False
    if re.fullmatch(r"[A-Za-z0-9]+", value):
        return len(value) <= ascii_limit
    return len(value) <= 4


def load_layout_config(layout: str) -> dict[str, Any]:
    filename = {
        "cover": "cover.json",
        "text_centered": "text-centered.json",
        "illustration_centered": "illustration-centered.json",
    }.get(layout)
    if not filename:
        return {}
    return read_json(SKILL_ROOT / "assets" / "layouts" / filename)


def count_caption_chars(text: str) -> int:
    return sum(1 for char in text if not char.isspace())


def schema_errors_for(spec: dict[str, Any]) -> list[str]:
    schema = read_json(SKILL_ROOT / "assets" / "project-schema.json")
    try:
        Draft202012Validator.check_schema(schema)
    except SchemaError as exc:
        raise ValueError(f"bundled project schema is invalid: {exc.message}") from exc
    validator = Draft202012Validator(schema)
    errors: list[str] = []
    for error in sorted(validator.iter_errors(spec), key=lambda item: list(item.absolute_path)):
        path = "$" + "".join(
            f"[{part}]" if isinstance(part, int) else f".{part}" for part in error.absolute_path
        )
        errors.append(f"schema {path}: {error.message}")
    return errors


def validate_spec(spec: dict[str, Any]) -> list[str]:
    errors = schema_errors_for(spec)
    if errors:
        return errors
    if spec.get("schema_version") != 1:
        errors.append("schema_version must equal 1")
    for key in ("concept", "resolved_scope", "audience"):
        if not isinstance(spec.get(key), str) or not spec[key].strip():
            errors.append(f"{key} must be a non-empty string")

    page_count = spec.get("page_count")
    pages = spec.get("pages")
    if not isinstance(page_count, int) or page_count < 4:
        errors.append("page_count must be an integer of at least 4")
    if not isinstance(pages, list):
        errors.append("pages must be an array")
        pages = []
    elif page_count != len(pages):
        errors.append("page_count must equal the number of pages")

    confirmation = spec.get("confirmation")
    if not isinstance(confirmation, dict):
        errors.append("confirmation must be an object")
    else:
        if confirmation.get("confirmed_by_user") is not True:
            errors.append("confirmation.confirmed_by_user must be true before rendering")
        if confirmation.get("approved_page_count") != page_count:
            errors.append("confirmation.approved_page_count must equal page_count")
        approved_layouts = set(confirmation.get("approved_layouts", []))

    titles = spec.get("titles")
    if not isinstance(titles, dict):
        errors.append("titles must be an object")
    else:
        recommended = titles.get("recommended")
        alternatives = titles.get("alternatives")
        if not isinstance(recommended, str) or not recommended.strip():
            errors.append("titles.recommended must contain exactly one title")
        if not isinstance(alternatives, list) or len(alternatives) != 2:
            errors.append("titles.alternatives must contain exactly two titles")
        elif any(not isinstance(item, str) or not item.strip() for item in alternatives):
            errors.append("both alternative titles must be non-empty strings")
        elif len({recommended, *alternatives}) != 3:
            errors.append("the recommended and alternative titles must be distinct")

    caption = spec.get("caption")
    if not isinstance(caption, str) or not caption.strip():
        errors.append("caption must be a non-empty string")
    elif count_caption_chars(caption) > 200:
        errors.append(f"caption exceeds 200 characters: {count_caption_chars(caption)}")

    corner_tags = spec.get("corner_tags")
    if not isinstance(corner_tags, dict):
        errors.append("corner_tags must be an object")
    else:
        for field in ("top_left", "top_right", "bottom_left"):
            value = corner_tags.get(field)
            if not isinstance(value, str) or not short_tag_is_valid(value, ascii_limit=8):
                errors.append(
                    f"corner_tags.{field} must be 1-4 characters or 1-8 ASCII letters/digits"
                )

    sources = spec.get("sources")
    source_ids: set[str] = set()
    source_groups: dict[str, str] = {}
    if not isinstance(sources, list) or not sources:
        errors.append("sources must contain at least one source")
        sources = []
    for index, source in enumerate(sources):
        if not isinstance(source, dict):
            errors.append(f"source {index + 1} must be an object")
            continue
        sid = str(source.get("id", "")).strip()
        if not sid or sid in source_ids:
            errors.append(f"source {index + 1} has a missing or duplicate id")
            continue
        source_ids.add(sid)
        for field in ("title", "publisher", "source_type"):
            if not str(source.get(field, "")).strip():
                errors.append(f"source {sid} needs {field}")
        group = str(source.get("publisher_group", "")).strip()
        source_groups[sid] = group
        if not group:
            errors.append(f"source {sid} needs publisher_group")
        url = str(source.get("url", ""))
        try:
            parsed_url = urlsplit(url)
            parsed_url.port  # Force validation of an explicit port.
            valid_url = (
                parsed_url.scheme in {"http", "https"}
                and bool(parsed_url.hostname)
                and parsed_url.username is None
                and parsed_url.password is None
            )
        except ValueError:
            valid_url = False
        if not valid_url:
            errors.append(f"source {sid} needs an http(s) URL with a host and no credentials")
        if not str(source.get("accessed_at", "")).strip():
            errors.append(f"source {sid} needs accessed_at")
        else:
            try:
                date.fromisoformat(source["accessed_at"])
            except ValueError:
                errors.append(f"source {sid} accessed_at must be a real YYYY-MM-DD date")

    claims = spec.get("claims")
    claim_ids: set[str] = set()
    if not isinstance(claims, list) or not claims:
        errors.append("claims must contain at least one claim")
        claims = []
    for index, claim in enumerate(claims):
        if not isinstance(claim, dict):
            errors.append(f"claim {index + 1} must be an object")
            continue
        cid = str(claim.get("id", "")).strip()
        if not cid or cid in claim_ids:
            errors.append(f"claim {index + 1} has a missing or duplicate id")
            continue
        claim_ids.add(cid)
        if not str(claim.get("text", "")).strip():
            errors.append(f"claim {cid} needs text")
        linked = claim.get("source_ids")
        if not isinstance(linked, list) or not linked:
            errors.append(f"claim {cid} needs at least one source_id")
            linked = []
        unknown = [sid for sid in linked if sid not in source_ids]
        if unknown:
            errors.append(f"claim {cid} references unknown sources: {unknown}")
        limitation = claim.get("source_limitation")
        if limitation is not None and (not isinstance(limitation, str) or not limitation.strip()):
            errors.append(f"claim {cid} source_limitation must be a non-empty string when present")
        if claim.get("core") is True:
            groups = {source_groups.get(sid, "") for sid in linked if source_groups.get(sid, "")}
            if len(groups) < 2 and not (isinstance(limitation, str) and limitation.strip()):
                errors.append(
                    f"core claim {cid} needs two independent publisher groups or a source_limitation"
                )

    used_claims: set[str] = set()
    for index, page in enumerate(pages):
        number = index + 1
        if not isinstance(page, dict):
            errors.append(f"page {number} must be an object")
            continue
        if page.get("number") != number:
            errors.append(f"page {number} must have number={number}")
        layout = page.get("layout")
        kind = page.get("kind")
        if number == 1:
            if kind != "cover" or layout != "cover":
                errors.append("page 1 must use kind=cover and layout=cover")
        elif kind != "inner" or layout not in {"text_centered", "illustration_centered"}:
            errors.append(f"page {number} must use a valid inner-page layout")
        elif layout not in approved_layouts:
            errors.append(f"page {number} uses layout {layout} without recorded user approval")
        if not str(page.get("title", "")).strip():
            errors.append(f"page {number} needs a title")
        ordered_lines: list[str] = []
        body_text = str(page.get("body", ""))
        if body_text.strip():
            ordered_lines.extend(line.strip() for line in body_text.splitlines() if line.strip())
        ordered_lines.extend(str(item).strip() for item in page.get("bullets", []) or [] if str(item).strip())
        circled = "①②③④⑤⑥⑦⑧⑨⑩"
        found_sequence: list[int] = []
        for line in ordered_lines:
            markers = [circled.index(char) + 1 for char in line if char in circled]
            if len(markers) > 1:
                errors.append(
                    f"page {number} numbered procedure must place one numbered item per line"
                )
                continue
            if markers:
                if not line.startswith(circled[markers[0] - 1]):
                    errors.append(
                        f"page {number} numbered procedure marker must start its own line"
                    )
                found_sequence.extend(markers)
        if found_sequence and found_sequence != list(
            range(found_sequence[0], found_sequence[0] + len(found_sequence))
        ):
            errors.append(f"page {number} numbered procedure must run in consecutive order")
        tag = str(page.get("keyword_tag", ""))
        english_tag = bool(re.fullmatch(r"[A-Za-z]+", tag))
        if not tag or (english_tag and len(tag) > 6) or (not english_tag and len(tag) > 4):
            errors.append(f"page {number} keyword_tag must be 1-4 characters or 1-6 ASCII letters")
        illustration = page.get("illustration", "")
        if illustration not in BUILTIN_MOTIFS:
            illustration_path = Path(illustration)
            if (
                illustration.startswith("~")
                or "\\" in illustration
                or ":" in illustration
                or illustration_path.is_absolute()
                or PureWindowsPath(illustration).is_absolute()
                or ".." in illustration_path.parts
                or not illustration_path.parts
                or illustration_path.parts[0] != "assets"
                or illustration_path.suffix.lower() != ".png"
            ):
                errors.append(
                    f"page {number} custom illustration must use a portable assets/... PNG path without parent traversal"
                )
        linked_claims = page.get("claim_ids", [])
        if not isinstance(linked_claims, list):
            errors.append(f"page {number} claim_ids must be an array")
            linked_claims = []
        unknown = [cid for cid in linked_claims if cid not in claim_ids]
        if unknown:
            errors.append(f"page {number} references unknown claims: {unknown}")
        used_claims.update(linked_claims)

    unused = sorted(claim_ids - used_claims)
    if unused:
        errors.append(f"claims are not mapped to any page: {unused}")
    return errors


def resolve_font(requested: str | None) -> Path:
    def required_font(value: str, source: str) -> Path:
        try:
            candidate = Path(value).expanduser()
            if candidate.is_file():
                return candidate.resolve()
        except (OSError, RuntimeError):
            pass
        raise FileNotFoundError(f"{source} font path does not exist or cannot be resolved")

    if requested is not None:
        return required_font(requested, "--font")
    environment_font = os.environ.get("XHS_FONT_PATH")
    if environment_font is not None:
        return required_font(environment_font, "XHS_FONT_PATH")
    for value in FONT_CANDIDATES:
        try:
            candidate = Path(value)
            if candidate.is_file():
                return candidate.resolve()
        except OSError:
            continue
    raise FileNotFoundError(
        "No CJK font found. Pass --font /path/to/a-licensed-CJK-font.ttf "
        "or set XHS_FONT_PATH. Noto Sans CJK SC and Source Han Sans SC are suitable."
    )


def load_font(path: Path, size: int) -> ImageFont.FreeTypeFont:
    try:
        return ImageFont.truetype(str(path), size=size)
    except OSError as exc:
        raise OSError(f"Unable to load font {path}: {exc}") from exc


def tokenize(text: str) -> list[str]:
    return re.findall(r"\n|[A-Za-z0-9][A-Za-z0-9_./:+#$-]*|\s+|.", text)


def text_width(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont) -> int:
    box = draw.textbbox((0, 0), text or " ", font=font)
    return box[2] - box[0]


def wrap_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.FreeTypeFont,
    max_width: int,
    stroke_width: int = 0,
) -> list[str]:
    lines: list[str] = []
    current = ""
    for token in tokenize(text):
        if token == "\n":
            lines.append(current.rstrip())
            current = ""
            continue
        if token.isspace() and not current:
            continue
        proposal = current + token
        proposal_box = draw.textbbox(
            (0, 0), proposal.rstrip() or " ", font=font, stroke_width=stroke_width
        )
        if proposal_box[2] - proposal_box[0] <= max_width:
            current = proposal
            continue
        if current.strip():
            lines.append(current.rstrip())
            current = ""
        token = token.lstrip()
        if not token:
            continue
        token_box = draw.textbbox((0, 0), token, font=font, stroke_width=stroke_width)
        if token_box[2] - token_box[0] <= max_width:
            current = token
            continue
        for char in token:
            proposal = current + char
            proposal_box = draw.textbbox(
                (0, 0), proposal, font=font, stroke_width=stroke_width
            )
            if current and proposal_box[2] - proposal_box[0] > max_width:
                lines.append(current)
                current = char
            else:
                current = proposal
    if current.strip() or not lines:
        lines.append(current.rstrip())
    return lines


def fit_text(
    text: str,
    box: tuple[int, int, int, int],
    font_path: Path,
    max_size: int,
    min_size: int,
    line_gap_ratio: float = 0.32,
    stroke_width: int = 0,
) -> tuple[ImageFont.FreeTypeFont, list[str], int]:
    probe = Image.new("L", (WIDTH, HEIGHT), 0)
    draw = ImageDraw.Draw(probe)
    max_width = box[2] - box[0]
    max_height = box[3] - box[1]
    for size in range(max_size, min_size - 1, -2):
        font = load_font(font_path, size)
        lines = wrap_text(draw, text, font, max_width, stroke_width=stroke_width)
        glyph_box = draw.textbbox((0, 0), "国Ag", font=font, stroke_width=stroke_width)
        line_height = glyph_box[3] - glyph_box[1]
        gap = max(4, round(size * line_gap_ratio))
        total = line_height * len(lines) + gap * max(0, len(lines) - 1)
        if total <= max_height:
            return font, lines, gap
    raise ValueError(f"text does not fit at the minimum font size {min_size}: {text!r}")


def paper_background(seed: int) -> Image.Image:
    image = Image.new("RGBA", (WIDTH, HEIGHT), PALETTE["paper"])
    draw = ImageDraw.Draw(image, "RGBA")
    for x in range(20, WIDTH, 48):
        draw.line((x, 0, x, HEIGHT), fill=PALETTE["grid"], width=1)
    for y in range(16, HEIGHT, 48):
        draw.line((0, y, WIDTH, y), fill=PALETTE["grid"], width=1)
    rng = random.Random(seed)
    paper_grain = (
        (237, 231, 218, 255),
        (252, 249, 239, 255),
        (226, 233, 232, 255),
    )
    for _ in range(3200):
        x = rng.randrange(WIDTH)
        y = rng.randrange(HEIGHT)
        draw.point((x, y), fill=rng.choice(paper_grain))
    return image


def rgba_mask(layer: Image.Image) -> Image.Image:
    return layer.getchannel("A").point(lambda value: 255 if value else 0)


def mask_pixels(mask: Image.Image) -> int:
    histogram = mask.histogram()
    return sum(histogram[1:])


def overlap_pixels(first: Image.Image, second: Image.Image) -> int:
    return mask_pixels(ImageChops.multiply(first, second))


def bbox_clearance(first: tuple[int, int, int, int], second: tuple[int, int, int, int]) -> float:
    dx = max(first[0] - second[2], second[0] - first[2], 0)
    dy = max(first[1] - second[3], second[1] - first[3], 0)
    return round(math.hypot(dx, dy), 2)


def dilate_mask(mask: Image.Image, bounds: tuple[int, int, int, int], radius: int) -> Image.Image:
    x1 = max(0, bounds[0] - radius)
    y1 = max(0, bounds[1] - radius)
    x2 = min(WIDTH, bounds[2] + radius)
    y2 = min(HEIGHT, bounds[3] + radius)
    crop = mask.crop((x1, y1, x2, y2)).filter(ImageFilter.MaxFilter(radius * 2 + 1))
    expanded = Image.new("L", (WIDTH, HEIGHT), 0)
    expanded.paste(crop, (x1, y1))
    return expanded


def slug(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_-]+", "-", value).strip("-")
    return cleaned or "element"


def custom_asset_paths(spec: dict[str, Any]) -> list[str]:
    return sorted(
        {
            page["illustration"]
            for page in spec["pages"]
            if page["illustration"] not in BUILTIN_MOTIFS
        }
    )


def resolve_project_asset(relative_path: str, project_dir: Path) -> Path:
    project_root = project_dir.resolve()
    candidate = (project_root / Path(relative_path)).resolve()
    candidate.relative_to(project_root)
    return candidate


def load_safe_alpha_png(path: Path) -> Image.Image:
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(path) as opened:
                has_alpha = "A" in opened.getbands() or "transparency" in opened.info
                if opened.format != "PNG" or not has_alpha:
                    raise ValueError("illustration asset must be an alpha PNG")
                if opened.width > 4096 or opened.height > 4096 or opened.width * opened.height > 16_777_216:
                    raise ValueError("illustration asset exceeds the 4096 px / 16.8 MP safety limit")
                return opened.convert("RGBA")
    except (OSError, Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
        raise ValueError("illustration asset is unsafe or unreadable") from exc


def save_sanitized_asset(source: Path, target: Path) -> None:
    image = load_safe_alpha_png(source)
    image.info.clear()
    target.parent.mkdir(parents=True, exist_ok=True)
    image.save(target, "PNG", optimize=True)


class PageBuilder:
    def __init__(self, number: int, font_path: Path, text_clearance: int = TEXT_CLEARANCE):
        self.number = number
        self.font_path = font_path
        self.text_clearance = text_clearance
        self.image = paper_background(number * 7919)
        self.elements: list[dict[str, Any]] = []
        self.errors: list[str] = []

    def add_layer(self, element_id: str, kind: str, layer: Image.Image, role: str = "main") -> None:
        mask = rgba_mask(layer)
        bounds = mask.getbbox()
        if not bounds:
            self.errors.append(f"{element_id} rendered no visible pixels")
            return
        self.image.alpha_composite(layer)
        self.elements.append(
            {"id": element_id, "kind": kind, "role": role, "mask": mask, "bbox": bounds}
        )

    def add_text(
        self,
        element_id: str,
        text: str,
        box: tuple[int, int, int, int],
        max_size: int,
        min_size: int,
        color: tuple[int, int, int, int] | None = None,
        align: str = "left",
        role: str = "main",
        panel: tuple[int, int, int, int] | None = None,
        stroke_width: int = 0,
        vertical_align: str = "top",
    ) -> None:
        if not text.strip():
            return
        try:
            font, lines, gap = fit_text(
                text,
                box,
                self.font_path,
                max_size,
                min_size,
                stroke_width=stroke_width,
            )
        except ValueError as exc:
            self.errors.append(f"{element_id}: {exc}")
            return
        layer = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
        draw = ImageDraw.Draw(layer)
        if panel is not None:
            draw.rounded_rectangle(panel, radius=8, fill=PALETTE["paper_light"], outline=(54, 58, 60, 145), width=2)
        glyph_box = draw.textbbox((0, 0), "国Ag", font=font, stroke_width=stroke_width)
        line_height = glyph_box[3] - glyph_box[1]
        total_height = line_height * len(lines) + gap * max(0, len(lines) - 1)
        if vertical_align == "bottom":
            y = box[3] - total_height
        elif vertical_align == "adaptive_bottom":
            available_height = box[3] - box[1]
            y = box[3] - total_height if total_height <= available_height * 0.72 else box[1]
        elif vertical_align == "top":
            y = box[1]
        else:
            self.errors.append(f"{element_id}: unknown vertical_align={vertical_align!r}")
            return
        for line in lines:
            line_box = draw.textbbox(
                (0, 0), line or " ", font=font, stroke_width=stroke_width
            )
            width = line_box[2] - line_box[0]
            x = box[0] if align == "left" else box[0] + (box[2] - box[0] - width) / 2
            text_color = color or PALETTE["charcoal"]
            draw.text(
                (x - line_box[0], y - line_box[1]),
                line,
                font=font,
                fill=text_color,
                stroke_width=stroke_width,
                stroke_fill=text_color,
            )
            y += line_height + gap
        self.add_layer(element_id, "text", layer, role=role)

    def add_badge(self, element_id: str, text: str, x: int, y: int, align: str, fill: tuple[int, int, int, int], role: str) -> None:
        font = load_font(self.font_path, 21)
        probe = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
        draw = ImageDraw.Draw(probe)
        box = draw.textbbox((0, 0), text, font=font)
        width = box[2] - box[0]
        height = box[3] - box[1]
        panel_width = width + 28
        panel_height = height + 18
        x1 = x if align == "left" else x - panel_width
        y1 = y
        layer = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
        draw = ImageDraw.Draw(layer)
        shadow = (x1 + 3, y1 + 4, x1 + panel_width + 3, y1 + panel_height + 4)
        draw.rounded_rectangle(shadow, radius=4, fill=(25, 28, 31, 28))
        draw.rounded_rectangle((x1, y1, x1 + panel_width, y1 + panel_height), radius=4, fill=fill, outline=(38, 42, 44, 120), width=1)
        fg = PALETTE["white"] if fill in {PALETTE["deep_blue"], PALETTE["coral"]} else PALETTE["charcoal"]
        draw.text((x1 + 14 - box[0], y1 + 9 - box[1]), text, font=font, fill=fg)
        self.add_layer(element_id, "text", layer, role=role)

    def add_corner_tags(self, keyword: str, labels: dict[str, str]) -> None:
        self.add_badge("tag-top-left", labels["top_left"], 46, 28, "left", PALETTE["paper_light"], "corner_tag")
        self.add_badge("tag-top-right", labels["top_right"], WIDTH - 46, 28, "right", PALETTE["paper_light"], "corner_tag")
        self.add_badge("tag-bottom-left", labels["bottom_left"], 46, 1368, "left", PALETTE["deep_blue"], "corner_tag")
        self.add_badge("tag-keyword", keyword, WIDTH - 46, 1368, "right", PALETTE["coral"], "corner_tag")

    def add_decorations(self, layout: str) -> None:
        positions = {
            "cover": [(62, 136, "circle", PALETTE["muted_blue"]), (982, 132, "diamond", PALETTE["butter"]), (62, 630, "dot", PALETTE["coral"]), (1000, 670, "bar", PALETTE["cobalt"])],
            "text_centered": [(62, 136, "circle", PALETTE["muted_blue"]), (988, 138, "diamond", PALETTE["butter"]), (72, 700, "bar", PALETTE["coral"]), (1004, 780, "dot", PALETTE["cobalt"])],
            "illustration_centered": [(62, 136, "circle", PALETTE["muted_blue"]), (988, 138, "diamond", PALETTE["butter"]), (64, 780, "bar", PALETTE["coral"]), (1004, 1060, "dot", PALETTE["cobalt"])],
        }[layout]
        for index, (x, y, shape, color) in enumerate(positions, start=1):
            layer = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
            draw = ImageDraw.Draw(layer)
            if shape == "circle":
                draw.ellipse((x - 18, y - 18, x + 18, y + 18), fill=color)
            elif shape == "dot":
                draw.ellipse((x - 9, y - 9, x + 9, y + 9), fill=color)
            elif shape == "bar":
                draw.rounded_rectangle((x - 10, y - 34, x + 10, y + 34), radius=9, fill=color)
            else:
                draw.polygon(((x, y - 24), (x + 24, y), (x, y + 24), (x - 24, y)), fill=color)
            self.add_layer(f"decoration-{index}", "decoration", layer)

    def add_illustration(self, motif: str, box: tuple[int, int, int, int], project_dir: Path) -> None:
        motif = motif.strip() or "folder"
        if motif in BUILTIN_MOTIFS:
            self.add_layer("illustration", "illustration", builtin_illustration(motif, box))
            return
        try:
            candidate = resolve_project_asset(motif, project_dir)
        except (OSError, RuntimeError, ValueError):
            self.errors.append("illustration asset path cannot be resolved")
            return
        if candidate.is_file():
            try:
                source = load_safe_alpha_png(candidate)
            except ValueError as exc:
                self.errors.append(f"{exc}: {candidate.name}")
                return
            source.thumbnail((box[2] - box[0], box[3] - box[1]), Image.Resampling.LANCZOS)
            layer = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
            x = box[0] + (box[2] - box[0] - source.width) // 2
            y = box[1] + (box[3] - box[1] - source.height) // 2
            layer.alpha_composite(source, (x, y))
            self.add_layer("illustration", "illustration", layer)
            return
        self.errors.append(f"illustration asset not found: {motif}")

    def analyze(self) -> dict[str, Any]:
        issues: list[dict[str, Any]] = []
        for element in self.elements:
            margin = NON_TEXT_MARGIN if element["kind"] != "text" or element["role"] == "corner_tag" else TEXT_MARGIN
            x1, y1, x2, y2 = element["bbox"]
            if x1 < margin or y1 < margin or x2 > WIDTH - margin or y2 > HEIGHT - margin:
                issues.append({"type": "boundary", "element": element["id"], "bbox": list(element["bbox"]), "required_margin": margin})

        expanded: dict[str, Image.Image] = {}
        for element in self.elements:
            if element["kind"] == "text":
                expanded[element["id"]] = dilate_mask(
                    element["mask"], element["bbox"], self.text_clearance
                )

        pair_results: list[dict[str, Any]] = []
        for first_index, first in enumerate(self.elements):
            for second in self.elements[first_index + 1 :]:
                actual = overlap_pixels(first["mask"], second["mask"])
                clearance_pixels = 0
                if first["kind"] == "text" and second["kind"] != "text":
                    clearance_pixels = overlap_pixels(expanded[first["id"]], second["mask"])
                elif second["kind"] == "text" and first["kind"] != "text":
                    clearance_pixels = overlap_pixels(expanded[second["id"]], first["mask"])
                elif first["kind"] == "text" and second["kind"] == "text":
                    small_first = dilate_mask(first["mask"], first["bbox"], 8)
                    clearance_pixels = overlap_pixels(small_first, second["mask"])
                pair = {
                    "first": first["id"],
                    "second": second["id"],
                    "overlap_pixels": actual,
                    "clearance_violation_pixels": clearance_pixels,
                    "bbox_clearance_px": bbox_clearance(first["bbox"], second["bbox"]),
                }
                pair_results.append(pair)
                if actual or clearance_pixels:
                    issues.append({"type": "collision", **pair})

        decoration_union = Image.new("L", (WIDTH, HEIGHT), 0)
        for element in self.elements:
            if element["kind"] == "decoration":
                decoration_union = ImageChops.lighter(decoration_union, element["mask"])
        decoration_ratio = mask_pixels(decoration_union) / (WIDTH * HEIGHT)
        if decoration_ratio > 0.20:
            issues.append({"type": "decoration_density", "ratio": decoration_ratio, "limit": 0.20})

        element_records = [
            {"id": item["id"], "kind": item["kind"], "role": item["role"], "bbox": list(item["bbox"])}
            for item in self.elements
        ]
        return {
            "page": self.number,
            "passed": not issues and not self.errors,
            "render_errors": self.errors,
            "issues": issues,
            "decoration_area_ratio": round(decoration_ratio, 6),
            "required_text_nontext_clearance_px": self.text_clearance,
            "elements": element_records,
            "pairs": pair_results,
        }


def add_shadowed_panel(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], fill: tuple[int, int, int, int], radius: int = 18) -> None:
    x1, y1, x2, y2 = box
    draw.rounded_rectangle((x1 + 8, y1 + 10, x2 + 8, y2 + 10), radius=radius, fill=(20, 24, 28, 30))
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=(255, 253, 246, 210), width=5)


def builtin_illustration(motif: str, box: tuple[int, int, int, int]) -> Image.Image:
    if motif not in BUILTIN_MOTIFS:
        raise ValueError(f"unknown built-in illustration motif: {motif}")
    layer = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    x1, y1, x2, y2 = box
    width = x2 - x1
    height = y2 - y1
    cx = (x1 + x2) // 2
    cy = (y1 + y2) // 2

    if motif in {"repeat", "workflow"}:
        node_y = cy
        colors = (PALETTE["cobalt"], PALETTE["butter"], PALETTE["coral"], PALETTE["deep_blue"])
        node_w = max(70, width // 7)
        gap = max(35, width // 24)
        total = node_w * 4 + gap * 3
        start = cx - total // 2
        for index, color in enumerate(colors):
            nx = start + index * (node_w + gap)
            add_shadowed_panel(draw, (nx, node_y - 48, nx + node_w, node_y + 48), color, radius=16)
            if index < 3:
                ax = nx + node_w + 8
                draw.line((ax, node_y, ax + gap - 16, node_y), fill=PALETTE["charcoal"], width=7)
                draw.polygon(((ax + gap - 16, node_y), (ax + gap - 28, node_y - 10), (ax + gap - 28, node_y + 10)), fill=PALETTE["charcoal"])
        if motif == "repeat":
            draw.arc((cx - total // 2, node_y - 115, cx + total // 2, node_y + 115), 205, 335, fill=PALETTE["muted_blue"], width=10)
        return layer

    if motif in {"sources", "magnifier"}:
        radius = min(width, height) // 4
        draw.ellipse((cx - radius, cy - radius, cx + radius, cy + radius), fill=(255, 253, 246, 210), outline=PALETTE["cobalt"], width=20)
        handle_start = (cx + int(radius * 0.67), cy + int(radius * 0.67))
        handle_end = (cx + int(radius * 1.55), cy + int(radius * 1.55))
        draw.line((*handle_start, *handle_end), fill=PALETTE["deep_blue"], width=28)
        draw.ellipse((cx - 38, cy - 38, cx + 38, cy + 38), fill=PALETTE["butter"])
        draw.polygon(((cx - 90, cy + 70), (cx - 20, cy + 35), (cx + 50, cy + 85), (cx - 18, cy + 120)), fill=PALETTE["coral"])
        return layer

    if motif in {"benefits", "blocks"}:
        size = min(width // 5, height // 2)
        positions = ((cx - size - 20, cy - size - 20), (cx + 20, cy - size - 20), (cx - size - 20, cy + 20), (cx + 20, cy + 20))
        colors = (PALETTE["cobalt"], PALETTE["butter"], PALETTE["coral"], PALETTE["muted_blue"])
        for (px, py), color in zip(positions, colors):
            add_shadowed_panel(draw, (px, py, px + size, py + size), color, radius=22)
        return layer

    folder_w = min(int(width * 0.62), 620)
    folder_h = min(int(height * 0.58), 330)
    fx1 = cx - folder_w // 2
    fy1 = y2 - folder_h - 18
    fx2 = fx1 + folder_w
    fy2 = fy1 + folder_h
    draw.rounded_rectangle((fx1 + 10, fy1 + 12, fx2 + 10, fy2 + 12), radius=28, fill=(20, 24, 28, 35))
    tab_y = fy1 + min(60, max(36, int(folder_h * 0.46)))
    tab_top = fy1 + min(20, max(12, int(folder_h * 0.15)))
    draw.polygon(
        (
            (fx1, tab_y),
            (fx1 + int(folder_w * 0.34), tab_y),
            (fx1 + int(folder_w * 0.40), tab_top),
            (fx1 + int(folder_w * 0.68), tab_top),
            (fx1 + int(folder_w * 0.73), tab_y),
            (fx2, tab_y),
            (fx2, fy2),
            (fx1, fy2),
        ),
        fill=PALETTE["cobalt"],
    )
    card_colors = (PALETTE["paper_light"], (237, 226, 198, 255), (230, 211, 180, 255))
    for index, color in enumerate(card_colors):
        card_w = folder_w // 4
        card_x = fx1 + 70 + index * (card_w - 12)
        card_y = fy1 - 35 - index * 12
        add_shadowed_panel(draw, (card_x, card_y, card_x + card_w, fy1 + folder_h // 2), color, radius=12)
        shape_color = (PALETTE["cobalt"], PALETTE["butter"], PALETTE["coral"])[index]
        dot_size = min(42, max(20, card_w // 3))
        dot_x = card_x + max(14, card_w // 8)
        dot_y = card_y + 30
        draw.ellipse(
            (dot_x, dot_y, dot_x + dot_size, dot_y + dot_size), fill=shape_color
        )
        bar_x1 = dot_x + dot_size + max(8, card_w // 16)
        bar_x2 = card_x + card_w - max(12, card_w // 10)
        if bar_x2 - bar_x1 >= 8:
            draw.rounded_rectangle(
                (bar_x1, card_y + 36, bar_x2, card_y + 64),
                radius=10,
                fill=shape_color,
            )
    if motif in {"anatomy", "folder"}:
        gear_cx = fx2 - 65
        gear_cy = fy2 - 72
        draw.ellipse((gear_cx - 46, gear_cy - 46, gear_cx + 46, gear_cy + 46), fill=PALETTE["butter"], outline=PALETTE["paper_light"], width=6)
        draw.ellipse((gear_cx - 17, gear_cy - 17, gear_cx + 17, gear_cy + 17), fill=PALETTE["paper"])
    return layer


def combined_body(page: dict[str, Any]) -> str:
    parts: list[str] = []
    body = str(page.get("body", "")).strip()
    if body:
        parts.append(body)
    for bullet in page.get("bullets", []) or []:
        parts.append(f"• {bullet}")
    return "\n".join(parts)


def measured_text_layout(
    text: str,
    box: tuple[int, int, int, int],
    font_path: Path,
    max_size: int,
    min_size: int,
) -> tuple[int, int]:
    """Return final wrapped line count and glyph height without drawing."""
    if not text.strip():
        return 0, 0
    face, lines, gap = fit_text(text, box, font_path, max_size, min_size)
    probe = Image.new("L", (8, 8), 0)
    draw = ImageDraw.Draw(probe)
    glyph_box = draw.textbbox((0, 0), "国Ag", font=face)
    line_height = glyph_box[3] - glyph_box[1]
    total_height = line_height * len(lines) + gap * max(0, len(lines) - 1)
    return len(lines), total_height


def adaptive_illustration_box(
    page: dict[str, Any],
    layout_config: dict[str, Any],
    font_path: Path,
) -> tuple[tuple[int, int, int, int], tuple[int, int, int, int], str]:
    """Let measured copy choose both the illustration and body slots."""
    baseline = tuple(layout_config["illustration_box"])
    base_w = baseline[2] - baseline[0]
    base_h = baseline[3] - baseline[1]
    title_bottom = int(layout_config["title_box"][3])
    clearance = int(layout_config.get("text_nontext_clearance_px", TEXT_CLEARANCE))

    top_box = tuple(layout_config["top_text_box"])
    top_lines, top_height = measured_text_layout(
        str(page.get("top_text", "")), top_box, font_path, 32, 24
    )
    body_text = combined_body(page)
    bottom_box = tuple(layout_config["bottom_text_box"])
    body_lines, body_height = measured_text_layout(
        body_text, bottom_box, font_path, 34, 25
    )
    title_gap = 56 if body_lines <= 3 else 44 if body_lines <= 5 else clearance
    body_gap = 56 if body_lines <= 3 else 44 if body_lines <= 5 else clearance

    visual_top = title_bottom + max(clearance, title_gap)
    if top_lines:
        visual_top = max(visual_top, top_box[1] + top_height + title_gap)

    available_h = bottom_box[3] - body_height - body_gap - visual_top
    desired_scale = 1.55 if body_lines <= 3 else 1.0 if body_lines <= 5 else 0.84
    min_w, min_h = 480, 320
    scale = min(desired_scale, available_h / base_h, 970 / base_w)
    if scale * base_w < min_w or scale * base_h < min_h:
        return baseline, bottom_box, (
            f"copy leaves only {available_h}px for the primary visual; "
            f"shorten or split copy before shrinking below {min_w}x{min_h}px"
        )

    visual_w = round(base_w * scale)
    visual_h = round(base_h * scale)
    chain_end = visual_top + visual_h + body_gap + body_height
    bottom_slack = max(0, bottom_box[3] - chain_end)
    shift_down = min(bottom_slack, max(0, 72 - title_gap))
    visual_top += shift_down
    body_top = visual_top + visual_h + body_gap
    center_x = WIDTH // 2
    box = (
        center_x - visual_w // 2,
        visual_top,
        center_x - visual_w // 2 + visual_w,
        visual_top + visual_h,
    )
    dynamic_body_box = (
        bottom_box[0],
        body_top,
        bottom_box[2],
        body_top + max(1, body_height),
    )
    return box, dynamic_body_box, ""


def render_page(
    page: dict[str, Any],
    font_path: Path,
    project_dir: Path,
    corner_tags: dict[str, str],
) -> tuple[PageBuilder, dict[str, Any]]:
    layout = page["layout"]
    layout_config = load_layout_config(layout)
    builder = PageBuilder(
        page["number"],
        font_path,
        text_clearance=int(layout_config.get("text_nontext_clearance_px", TEXT_CLEARANCE)),
    )
    builder.add_decorations(layout)
    title_stroke = int(layout_config.get("title_stroke_px", 2))
    eyebrow = str(page.get("eyebrow", "")).strip()
    if layout == "cover":
        keyword = str(page.get("keyword", "")).strip()
        if eyebrow:
            builder.add_text("eyebrow", eyebrow, (216, 115, 864, 160), 24, 20, PALETTE["deep_blue"], "center")
        if keyword:
            builder.add_text(
                "keyword",
                keyword,
                tuple(layout_config["keyword_box"]),
                142,
                90,
                PALETTE["charcoal"],
                "center",
                stroke_width=int(layout_config.get("keyword_stroke_px", title_stroke)),
            )
        builder.add_text(
            "title",
            page["title"],
            tuple(layout_config["title_box"]),
            72,
            46,
            PALETTE["deep_blue"],
            "center",
            stroke_width=title_stroke,
        )
        builder.add_text(
            "body",
            combined_body(page),
            tuple(layout_config["body_box"]),
            34,
            26,
            PALETTE["charcoal"],
            "center",
            vertical_align=str(layout_config.get("body_vertical_align", "top")),
        )
        builder.add_illustration(
            str(page.get("illustration", "folder")),
            tuple(layout_config["illustration_box"]),
            project_dir,
        )
    elif layout == "text_centered":
        if eyebrow:
            builder.add_text("eyebrow", eyebrow, (216, 120, 864, 165), 24, 20, PALETTE["deep_blue"])
        builder.add_text(
            "title",
            page["title"],
            tuple(layout_config["title_box"]),
            66,
            42,
            PALETTE["charcoal"],
            stroke_width=title_stroke,
        )
        builder.add_text(
            "body",
            combined_body(page),
            tuple(layout_config["body_box"]),
            40,
            28,
            PALETTE["charcoal"],
            vertical_align=str(layout_config.get("body_vertical_align", "top")),
        )
        builder.add_illustration(str(page.get("illustration", "folder")), tuple(layout_config["illustration_box"]), project_dir)
    else:
        if eyebrow:
            builder.add_text("eyebrow", eyebrow, (216, 115, 864, 160), 24, 20, PALETTE["deep_blue"])
        builder.add_text(
            "title",
            page["title"],
            tuple(layout_config["title_box"]),
            64,
            42,
            PALETTE["charcoal"],
            "center",
            stroke_width=title_stroke,
        )
        builder.add_text("top-text", str(page.get("top_text", "")), tuple(layout_config["top_text_box"]), 32, 24, PALETTE["deep_blue"], "center")
        illustration_box, dynamic_body_box, illustration_error = adaptive_illustration_box(
            page, layout_config, font_path
        )
        if illustration_error:
            builder.errors.append(illustration_error)
        builder.add_illustration(
            str(page.get("illustration", "workflow")), illustration_box, project_dir
        )
        builder.add_text(
            "body",
            combined_body(page),
            dynamic_body_box,
            34,
            25,
            PALETTE["charcoal"],
            "center",
            vertical_align="top",
        )
    builder.add_corner_tags(str(page["keyword_tag"]), corner_tags)
    report = builder.analyze()
    return builder, report


def save_debug_overlay(builder: PageBuilder, report: dict[str, Any], path: Path) -> None:
    overlay = builder.image.copy()
    draw = ImageDraw.Draw(overlay)
    implicated: set[str] = set()
    for issue in report["issues"]:
        if issue.get("element"):
            implicated.add(issue["element"])
        if issue.get("first"):
            implicated.add(issue["first"])
        if issue.get("second"):
            implicated.add(issue["second"])
    for element in builder.elements:
        color = (220, 40, 40, 255) if element["id"] in implicated else (40, 160, 80, 180)
        draw.rectangle(element["bbox"], outline=color, width=4)
    path.parent.mkdir(parents=True, exist_ok=True)
    overlay.convert("RGB").save(path, "PNG", optimize=True)


def source_ledger_for(spec: dict[str, Any], project_sha256: str) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "project_sha256": project_sha256,
        "pages": [
            {
                "number": page["number"],
                "image_file": f"pages/{page['number']:02d}.png",
                "claim_ids": page.get("claim_ids", []),
            }
            for page in spec["pages"]
        ],
        "claims": spec["claims"],
        "sources": spec["sources"],
    }


def manifest_for(
    spec: dict[str, Any],
    project_file: str,
    project_sha256: str,
    font_file: str,
    layout_passed: bool,
    asset_records: list[dict[str, str]],
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "project_file": project_file,
        "project_snapshot_file": "project.snapshot.json",
        "project_sha256": project_sha256,
        "concept": spec["concept"],
        "page_count": spec["page_count"],
        "page_files": [f"pages/{number:02d}.png" for number in range(1, spec["page_count"] + 1)],
        "asset_files": asset_records,
        "titles": spec["titles"],
        "caption": spec["caption"],
        "font_file": font_file,
        "layout_passed": layout_passed,
    }


def render_project(spec_path: Path, output: Path, font_path: Path) -> dict[str, Any]:
    spec = read_json(spec_path)
    errors = validate_spec(spec)
    if errors:
        raise ValueError("Project contract failed:\n- " + "\n- ".join(errors))
    if output.exists() and not output.is_dir():
        raise ValueError(f"output path is not a directory: {output}")
    if output.exists() and any(output.iterdir()):
        raise ValueError(f"output directory must be empty; choose a fresh path: {output}")
    output.mkdir(parents=True, exist_ok=True)
    project_sha256 = sha256_file(spec_path)
    snapshot_path = output / "project.snapshot.json"
    snapshot_path.write_bytes(spec_path.read_bytes())
    pages_dir = output / "pages"
    qa_dir = output / "qa"
    masks_dir = qa_dir / "masks"
    pages_dir.mkdir(parents=True, exist_ok=True)
    masks_dir.mkdir(parents=True, exist_ok=True)

    page_reports: list[dict[str, Any]] = []
    for page in spec["pages"]:
        builder, page_report = render_page(page, font_path, spec_path.parent, spec["corner_tags"])
        page_path = pages_dir / f"{page['number']:02d}.png"
        builder.image.convert("RGB").save(page_path, "PNG", optimize=True)
        page_report["image_file"] = page_path.relative_to(output).as_posix()
        page_report["image_sha256"] = sha256_file(page_path)
        page_mask_dir = masks_dir / f"{page['number']:02d}"
        page_mask_dir.mkdir(parents=True, exist_ok=True)
        for element, element_record in zip(builder.elements, page_report["elements"]):
            mask_path = page_mask_dir / f"{slug(element['id'])}.png"
            element["mask"].save(mask_path, "PNG", optimize=True)
            element_record["mask_file"] = mask_path.relative_to(output).as_posix()
            element_record["mask_sha256"] = sha256_file(mask_path)
        if not page_report["passed"]:
            save_debug_overlay(builder, page_report, qa_dir / "debug-overlays" / f"{page['number']:02d}.png")
        page_reports.append(page_report)

    layout_passed = all(page["passed"] for page in page_reports)
    asset_records: list[dict[str, str]] = []
    if layout_passed:
        for relative_path in custom_asset_paths(spec):
            source = resolve_project_asset(relative_path, spec_path.parent)
            target = output / Path(relative_path)
            save_sanitized_asset(source, target)
            asset_records.append({"path": relative_path, "sha256": sha256_file(target)})

    report = {
        "schema_version": 1,
        "passed": layout_passed,
        "canvas": [WIDTH, HEIGHT],
        "font_file": font_path.name,
        "project_file": snapshot_path.name,
        "project_sha256": project_sha256,
        "pages": page_reports,
    }
    qa_dir.mkdir(parents=True, exist_ok=True)
    with (qa_dir / "layout-report.json").open("w", encoding="utf-8") as handle:
        json.dump(report, handle, ensure_ascii=False, indent=2)
    with (output / "source-ledger.json").open("w", encoding="utf-8") as handle:
        json.dump(source_ledger_for(spec, project_sha256), handle, ensure_ascii=False, indent=2)
    with (output / "manifest.json").open("w", encoding="utf-8") as handle:
        json.dump(
            manifest_for(
                spec,
                snapshot_path.name,
                project_sha256,
                font_path.name,
                report["passed"],
                asset_records,
            ),
            handle,
            ensure_ascii=False,
            indent=2,
        )
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project", type=Path, help="Path to project.json")
    parser.add_argument("--output", type=Path, required=True, help="Output directory")
    parser.add_argument("--font", help="Path to a CJK font")
    args = parser.parse_args()
    try:
        font_path = resolve_font(args.font)
        report = render_project(args.project.resolve(), args.output.resolve(), font_path)
    except (FileNotFoundError, OSError, RuntimeError, ValueError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    print(json.dumps({"output": str(args.output.resolve()), "passed": report["passed"], "font": str(font_path)}, ensure_ascii=False))
    return 0 if report["passed"] else 3


if __name__ == "__main__":
    raise SystemExit(main())

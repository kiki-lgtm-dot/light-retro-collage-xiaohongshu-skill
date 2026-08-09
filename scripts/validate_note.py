#!/usr/bin/env python3
"""Validate the note contract and the renderer's layout evidence."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

try:
    from PIL import Image
except ImportError as exc:  # pragma: no cover
    raise SystemExit(
        "Pillow is required. Install scripts/requirements.txt in the active Python environment."
    ) from exc

from render_note import (
    HEIGHT,
    WIDTH,
    custom_asset_paths,
    manifest_for,
    read_json,
    sha256_file,
    slug,
    source_ledger_for,
    validate_spec,
)


def validate_output(project: Path, output: Path) -> list[str]:
    spec = read_json(project)
    errors = validate_spec(spec)
    if errors:
        return errors
    project_sha256 = sha256_file(project)
    report_path = output / "qa" / "layout-report.json"
    if not report_path.is_file():
        errors.append(f"missing layout report: {report_path}")
        return errors
    report = read_json(report_path)
    if report.get("project_file") != "project.snapshot.json":
        errors.append("layout report project_file must name the delivered project snapshot")
    if report.get("project_sha256") != project_sha256:
        errors.append("layout report project hash does not match the current project")
    font_file = report.get("font_file")
    if not isinstance(font_file, str) or not font_file or Path(font_file).name != font_file:
        errors.append("layout report font_file must be a sanitized filename")
        font_file = "unknown-font"
    if report.get("passed") is not True:
        errors.append("layout report is not clean")
    if report.get("canvas") != [WIDTH, HEIGHT]:
        errors.append(f"layout report canvas must be {WIDTH}x{HEIGHT}")
    report_pages = report.get("pages")
    if not isinstance(report_pages, list) or len(report_pages) != spec.get("page_count"):
        errors.append("layout report page count does not match project")
    else:
        for number, page_report in enumerate(report_pages, start=1):
            if not isinstance(page_report, dict):
                errors.append(f"layout report page {number} must be an object")
                continue
            if page_report.get("page") != number:
                errors.append(f"layout report page sequence is invalid at page {number}")
            if page_report.get("passed") is not True:
                errors.append(f"page {number} has layout failures")
            if page_report.get("render_errors"):
                errors.append(f"page {number} has render errors")
            if page_report.get("issues"):
                errors.append(f"page {number} has collision or boundary issues")

    pages_dir = output / "pages"
    expected_page_names = [f"{number:02d}.png" for number in range(1, spec.get("page_count", 0) + 1)]
    actual_page_names = sorted(path.name for path in pages_dir.iterdir()) if pages_dir.is_dir() else []
    if actual_page_names != expected_page_names:
        errors.append(
            f"page files must exactly match the current project: expected {expected_page_names}, got {actual_page_names}"
        )
    expected_mask_files: set[str] = set()
    for number, page_name in enumerate(expected_page_names, start=1):
        page_path = pages_dir / page_name
        if not page_path.is_file():
            errors.append(f"missing page image: {page_path}")
            continue
        with Image.open(page_path) as image:
            if image.size != (WIDTH, HEIGHT):
                errors.append(f"{page_path.name} is {image.size}, expected {(WIDTH, HEIGHT)}")
            if image.format != "PNG":
                errors.append(f"{page_path.name} is not PNG")
        if isinstance(report_pages, list) and len(report_pages) >= number:
            page_report = report_pages[number - 1]
            if not isinstance(page_report, dict):
                continue
            expected_image_file = f"pages/{page_name}"
            if page_report.get("image_file") != expected_image_file:
                errors.append(f"page {number} report image_file is not {expected_image_file}")
            if page_report.get("image_sha256") != sha256_file(page_path):
                errors.append(f"page {number} image hash does not match the report")
            elements = page_report.get("elements")
            if not isinstance(elements, list) or not elements:
                errors.append(f"page {number} has no element-mask records")
                continue
            for element in elements:
                if not isinstance(element, dict):
                    errors.append(f"page {number} element-mask record must be an object")
                    continue
                element_id = str(element.get("id", ""))
                expected_mask = f"qa/masks/{number:02d}/{slug(element_id)}.png"
                expected_mask_files.add(expected_mask)
                if element.get("mask_file") != expected_mask:
                    errors.append(f"page {number} element {element_id} has an invalid mask path")
                    continue
                mask_path = output / expected_mask
                if not mask_path.is_file():
                    errors.append(f"missing element mask: {expected_mask}")
                    continue
                if element.get("mask_sha256") != sha256_file(mask_path):
                    errors.append(f"element mask hash mismatch: {expected_mask}")
                with Image.open(mask_path) as mask:
                    if mask.size != (WIDTH, HEIGHT) or mask.format != "PNG":
                        errors.append(f"invalid element mask image: {expected_mask}")

    masks_root = output / "qa" / "masks"
    actual_mask_files = {
        path.relative_to(output).as_posix() for path in masks_root.rglob("*.png")
    } if masks_root.is_dir() else set()
    if actual_mask_files != expected_mask_files:
        errors.append("element mask files do not exactly match the current layout report")

    debug_dir = output / "qa" / "debug-overlays"
    if debug_dir.is_dir() and any(debug_dir.iterdir()):
        errors.append("a passing output must not contain stale debug overlays")

    snapshot_path = output / "project.snapshot.json"
    if not snapshot_path.is_file():
        errors.append(f"missing output file: {snapshot_path}")
    else:
        if sha256_file(snapshot_path) != project_sha256:
            errors.append("project snapshot hash does not match the current project")
        elif read_json(snapshot_path) != spec:
            errors.append("project snapshot content does not match the current project")

    expected_asset_paths = custom_asset_paths(spec)
    assets_root = output / "assets"
    actual_asset_paths = sorted(
        path.relative_to(output).as_posix() for path in assets_root.rglob("*") if path.is_file()
    ) if assets_root.is_dir() else []
    if actual_asset_paths != expected_asset_paths:
        errors.append(
            f"delivered custom assets must exactly match the project: expected {expected_asset_paths}, got {actual_asset_paths}"
        )
    asset_records: list[dict[str, str]] = []
    for relative_path in expected_asset_paths:
        asset_path = output / relative_path
        if not asset_path.is_file():
            continue
        asset_records.append({"path": relative_path, "sha256": sha256_file(asset_path)})

    manifest_path = output / "manifest.json"
    if not manifest_path.is_file():
        errors.append(f"missing output file: {manifest_path}")
    else:
        manifest = read_json(manifest_path)
        expected_manifest = manifest_for(
            spec,
            "project.snapshot.json",
            project_sha256,
            font_file,
            True,
            asset_records,
        )
        if manifest != expected_manifest:
            errors.append("manifest does not match the current project and layout report")

    ledger_path = output / "source-ledger.json"
    if not ledger_path.is_file():
        errors.append(f"missing output file: {ledger_path}")
    else:
        ledger = read_json(ledger_path)
        if ledger != source_ledger_for(spec, project_sha256):
            errors.append("source ledger does not match the current project claim mapping")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        errors = validate_output(args.project.resolve(), args.output.resolve())
    except (
        FileNotFoundError,
        OSError,
        RuntimeError,
        TypeError,
        ValueError,
        json.JSONDecodeError,
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
    ) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    if errors:
        print("VALIDATION FAILED", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 3
    print(json.dumps({"passed": True, "output": str(args.output.resolve())}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

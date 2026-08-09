from __future__ import annotations

import copy
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image


SKILL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL / "scripts"))

from render_note import (  # noqa: E402
    PageBuilder,
    adaptive_illustration_box,
    count_caption_chars,
    load_layout_config,
    render_page,
    render_project,
    resolve_font,
    save_sanitized_asset,
    validate_spec,
)
from validate_note import validate_output  # noqa: E402


class ContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.base = json.loads((SKILL / "assets" / "examples" / "agent-skill-demo.json").read_text(encoding="utf-8"))

    def errors_for(self, mutation) -> list[str]:
        spec = copy.deepcopy(self.base)
        mutation(spec)
        return validate_spec(spec)

    def test_example_contract_is_clean(self) -> None:
        self.assertEqual(validate_spec(copy.deepcopy(self.base)), [])

    def test_caption_unicode_boundary(self) -> None:
        self.assertEqual(count_caption_chars("字 " * 200), 200)
        self.assertFalse(self.errors_for(lambda spec: spec.update(caption="字" * 200)))
        self.assertTrue(any("exceeds 200" in error for error in self.errors_for(lambda spec: spec.update(caption="字" * 201))))

    def test_caption_cannot_be_empty(self) -> None:
        self.assertTrue(any("caption" in error for error in self.errors_for(lambda spec: spec.update(caption="  \n"))))

    def test_schema_rejects_malformed_fields_without_traceback(self) -> None:
        mutations = [
            lambda spec: spec["confirmation"].update(approved_page_count=None),
            lambda spec: spec["sources"][0].update(accessed_at="2026-99-99"),
            lambda spec: spec["claims"][0].update(source_ids=[]),
            lambda spec: spec["pages"][0].pop("illustration"),
            lambda spec: spec["pages"][0].update(keyword_tag=None),
            lambda spec: spec.update(unexpected=True),
        ]
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                self.assertTrue(self.errors_for(mutation))

    def test_confirmation_gate(self) -> None:
        errors = self.errors_for(lambda spec: spec["confirmation"].update(confirmed_by_user=False))
        self.assertTrue(any("confirmed_by_user" in error for error in errors))

    def test_page_count_has_a_resource_bound(self) -> None:
        errors = self.errors_for(lambda spec: spec.update(page_count=1000))
        self.assertTrue(any("page_count" in error for error in errors))

    def test_approved_page_count_must_match(self) -> None:
        errors = self.errors_for(
            lambda spec: spec["confirmation"].update(approved_page_count=5)
        )
        self.assertTrue(any("approved_page_count" in error for error in errors))

    def test_mixed_layout_requires_recorded_approval(self) -> None:
        errors = self.errors_for(
            lambda spec: spec["confirmation"].update(approved_layouts=["text_centered"])
        )
        self.assertTrue(any("without recorded user approval" in error for error in errors))

    def test_exactly_three_distinct_titles(self) -> None:
        errors = self.errors_for(lambda spec: spec["titles"].update(alternatives=["重复", "重复"]))
        self.assertTrue(any("titles.alternatives" in error for error in errors))

    def test_keyword_tag_limits(self) -> None:
        self.assertFalse(self.errors_for(lambda spec: spec["pages"][0].update(keyword_tag="SKILL")))
        self.assertTrue(any("keyword_tag" in error for error in self.errors_for(lambda spec: spec["pages"][0].update(keyword_tag="TOOLBOX"))))
        self.assertFalse(self.errors_for(lambda spec: spec["pages"][0].update(keyword_tag="智能体")))
        self.assertTrue(any("keyword_tag" in error for error in self.errors_for(lambda spec: spec["pages"][0].update(keyword_tag="知识小百科"))))

    def test_core_claim_needs_two_publishers(self) -> None:
        def mutate(spec):
            spec["claims"][0]["source_ids"] = ["S1"]

        self.assertTrue(any("two independent" in error for error in self.errors_for(mutate)))

    def test_single_publisher_can_record_explicit_limitation(self) -> None:
        def mutate(spec):
            spec["claims"][0]["source_ids"] = ["S1"]
            spec["claims"][0]["source_limitation"] = "Only the originating product documentation states this product-specific behavior."

        self.assertEqual(self.errors_for(mutate), [])

    def test_both_inner_layouts_are_exercised(self) -> None:
        layouts = {page["layout"] for page in self.base["pages"]}
        self.assertIn("text_centered", layouts)
        self.assertIn("illustration_centered", layouts)

    def test_layouts_preserve_copy_space_and_readable_titles(self) -> None:
        expected_visual_sizes = {
            "cover": (688, 464),
            "text_centered": (624, 220),
            "illustration_centered": (608, 392),
        }
        for layout, expected_size in expected_visual_sizes.items():
            with self.subTest(layout=layout):
                config = load_layout_config(layout)
                x1, y1, x2, y2 = config["illustration_box"]
                self.assertEqual((x2 - x1, y2 - y1), expected_size)
                self.assertGreaterEqual(config["text_nontext_clearance_px"], 36)
                self.assertLessEqual(config["title_stroke_px"], 1)
        self.assertEqual(
            load_layout_config("illustration_centered")["bottom_text_vertical_align"],
            "adaptive_bottom",
        )

    def test_short_bottom_copy_uses_the_lower_part_of_its_safe_zone(self) -> None:
        builder = PageBuilder(2, resolve_font(None))
        builder.add_text(
            "body",
            "短文案只占一行。",
            (216, 950, 864, 1275),
            34,
            25,
            vertical_align="adaptive_bottom",
        )
        self.assertGreater(builder.elements[-1]["bbox"][1], 1180)

    def test_short_copy_gets_a_larger_visual_than_dense_copy(self) -> None:
        config = load_layout_config("illustration_centered")
        short_page = copy.deepcopy(self.base["pages"][3])
        short_page["top_text"] = ""
        short_page["body"] = "一句结论。"
        dense_page = copy.deepcopy(short_page)
        dense_page["body"] = "\n".join(
            ["① 第一步", "② 第二步", "③ 第三步", "④ 第四步", "⑤ 第五步"]
        )
        short_box, short_body_box, short_error = adaptive_illustration_box(
            short_page, config, resolve_font(None)
        )
        dense_box, dense_body_box, dense_error = adaptive_illustration_box(
            dense_page, config, resolve_font(None)
        )
        self.assertEqual(short_error, "")
        self.assertEqual(dense_error, "")
        self.assertGreater(short_box[2] - short_box[0], dense_box[2] - dense_box[0])
        for visual_box, body_box in (
            (short_box, short_body_box),
            (dense_box, dense_body_box),
        ):
            self.assertGreaterEqual(visual_box[1] - config["title_box"][3], 36)
            self.assertLessEqual(visual_box[1] - config["title_box"][3], 72)
            self.assertGreaterEqual(body_box[1] - visual_box[3], 36)
            self.assertLessEqual(body_box[1] - visual_box[3], 72)

    def test_numbered_steps_cannot_share_one_line(self) -> None:
        errors = self.errors_for(
            lambda spec: spec["pages"][4].update(body="① 第一步　② 第二步")
        )
        self.assertTrue(any("one numbered item per line" in error for error in errors))

    def test_text_centered_rejects_unrendered_top_text(self) -> None:
        errors = self.errors_for(lambda spec: spec["pages"][1].update(top_text="不能静默丢失"))
        self.assertTrue(any("pages" in error for error in errors))

    def test_missing_illustration_does_not_silently_fall_back(self) -> None:
        page = copy.deepcopy(self.base["pages"][0])
        page["illustration"] = "assets/does-not-exist.png"
        _, report = render_page(
            page,
            resolve_font(None),
            SKILL / "assets" / "examples",
            self.base["corner_tags"],
        )
        self.assertFalse(report["passed"])
        self.assertTrue(any("not found" in error for error in report["render_errors"]))

    def test_decompression_bomb_illustration_has_no_traceback(self) -> None:
        with tempfile.TemporaryDirectory(prefix="retro-collage-xhs-bomb-") as directory:
            root = Path(directory)
            assets = root / "assets"
            assets.mkdir()
            image_path = assets / "large.png"
            Image.new("RGBA", (64, 64), (20, 40, 60, 0)).save(image_path, "PNG")
            builder = PageBuilder(1, resolve_font(None))
            previous_limit = Image.MAX_IMAGE_PIXELS
            Image.MAX_IMAGE_PIXELS = 1
            try:
                builder.add_illustration("assets/large.png", (110, 735, 970, 1315), root)
            finally:
                Image.MAX_IMAGE_PIXELS = previous_limit
            report = builder.analyze()
            self.assertFalse(report["passed"])
            self.assertTrue(any("unsafe or unreadable" in error for error in report["render_errors"]))

    def test_delivered_asset_strips_metadata_and_trailing_payload(self) -> None:
        with tempfile.TemporaryDirectory(prefix="retro-collage-xhs-sanitize-") as directory:
            root = Path(directory)
            source = root / "source.png"
            delivered = root / "delivered.png"
            marker = b"PRIVATE_PROMPT=user@example.com"
            Image.new("RGBA", (64, 64), (20, 40, 60, 128)).save(source, "PNG")
            with source.open("ab") as handle:
                handle.write(marker)
            save_sanitized_asset(source, delivered)
            self.assertNotIn(marker, delivered.read_bytes())
            with Image.open(delivered) as image:
                self.assertEqual(image.mode, "RGBA")
                self.assertEqual(image.info, {})

    def test_malformed_illustration_home_does_not_traceback(self) -> None:
        page = copy.deepcopy(self.base["pages"][0])
        page["illustration"] = "~this-user-does-not-exist/missing.png"
        _, report = render_page(
            page,
            resolve_font(None),
            SKILL / "assets" / "examples",
            self.base["corner_tags"],
        )
        self.assertFalse(report["passed"])
        self.assertTrue(report["render_errors"])

    def test_custom_illustration_cannot_escape_project_via_symlink(self) -> None:
        with tempfile.TemporaryDirectory(prefix="retro-collage-xhs-symlink-") as directory:
            root = Path(directory)
            project_root = root / "project"
            assets = project_root / "assets"
            assets.mkdir(parents=True)
            outside = root / "outside.png"
            Image.new("RGBA", (64, 64), (20, 40, 60, 255)).save(outside, "PNG")
            link = assets / "link.png"
            try:
                link.symlink_to(outside)
            except OSError as exc:
                self.skipTest(f"symlinks unavailable: {exc}")
            page = copy.deepcopy(self.base["pages"][0])
            page["illustration"] = "assets/link.png"
            _, report = render_page(page, resolve_font(None), project_root, self.base["corner_tags"])
            self.assertFalse(report["passed"])
            self.assertTrue(any("cannot be resolved" in error for error in report["render_errors"]))

    def test_integrity_validation_rejects_stale_or_substituted_artifacts(self) -> None:
        with tempfile.TemporaryDirectory(prefix="retro-collage-xhs-integrity-") as directory:
            root = Path(directory)
            project = root / "project.json"
            project.write_text(json.dumps(self.base, ensure_ascii=False), encoding="utf-8")
            output = root / "output"
            render_project(project, output, resolve_font(None))
            self.assertEqual(validate_output(project, output), [])
            self.assertEqual(validate_output(output / "project.snapshot.json", output), [])

            shutil.copyfile(output / "pages" / "06.png", output / "pages" / "07.png")
            self.assertTrue(any("exactly match" in error for error in validate_output(project, output)))
            (output / "pages" / "07.png").unlink()

            changed = copy.deepcopy(self.base)
            changed["caption"] += "更新"
            project.write_text(json.dumps(changed, ensure_ascii=False), encoding="utf-8")
            self.assertTrue(any("project hash" in error for error in validate_output(project, output)))

    def test_renderer_requires_a_fresh_output_directory(self) -> None:
        with tempfile.TemporaryDirectory(prefix="retro-collage-xhs-nonempty-") as directory:
            output = Path(directory) / "output"
            output.mkdir()
            (output / "stale.txt").write_text("stale", encoding="utf-8")
            project = SKILL / "assets" / "examples" / "agent-skill-demo.json"
            with self.assertRaisesRegex(ValueError, "must be empty"):
                render_project(project, output, resolve_font(None))

    def test_invalid_explicit_font_fails_instead_of_falling_back(self) -> None:
        with self.assertRaisesRegex(FileNotFoundError, "--font"):
            resolve_font("~this-user-does-not-exist/font.ttf")

    def test_source_url_requires_a_host(self) -> None:
        errors = self.errors_for(lambda spec: spec["sources"][0].update(url="https://"))
        self.assertTrue(any("with a host" in error for error in errors))

    def test_source_url_rejects_credentials_and_bad_ports(self) -> None:
        for url in ("https://user@example.com", "https://:80", "https://example.com:abc"):
            with self.subTest(url=url):
                errors = self.errors_for(lambda spec, value=url: spec["sources"][0].update(url=value))
                self.assertTrue(any("no credentials" in error for error in errors))

    def test_self_test_failure_is_concise(self) -> None:
        result = subprocess.run(
            [
                sys.executable,
                str(SKILL / "scripts" / "self_test.py"),
                "--font",
                "~this-user-does-not-exist/font.ttf",
            ],
            capture_output=True,
            text=True,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn("Traceback", result.stderr)
        self.assertIn("SELF TEST FAILED", result.stderr)

    def test_cli_symlink_loop_failures_have_no_traceback(self) -> None:
        with tempfile.TemporaryDirectory(prefix="retro-collage-xhs-loop-") as directory:
            loop = Path(directory) / "loop"
            try:
                loop.symlink_to(loop)
            except OSError as exc:
                self.skipTest(f"symlinks unavailable: {exc}")
            for script in ("render_note.py", "validate_note.py"):
                with self.subTest(script=script):
                    result = subprocess.run(
                        [
                            sys.executable,
                            str(SKILL / "scripts" / script),
                            str(loop),
                            "--output",
                            str(loop),
                        ],
                        capture_output=True,
                        text=True,
                    )
                    self.assertNotEqual(result.returncode, 0)
                    self.assertNotIn("Traceback", result.stderr)
                    self.assertIn("ERROR:", result.stderr)

    def test_contact_sheet_corrupt_png_has_no_traceback(self) -> None:
        with tempfile.TemporaryDirectory(prefix="retro-collage-xhs-contact-corrupt-") as directory:
            pages = Path(directory) / "pages"
            pages.mkdir()
            (pages / "01.png").write_bytes(b"not a png")
            result = subprocess.run(
                [
                    sys.executable,
                    str(SKILL / "scripts" / "make_contact_sheet.py"),
                    str(pages),
                    "--output",
                    str(Path(directory) / "sheet.png"),
                    "--columns",
                    "999999999",
                ],
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertNotIn("Traceback", result.stderr)
            self.assertIn("ERROR:", result.stderr)


if __name__ == "__main__":
    unittest.main()

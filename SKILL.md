---
name: generate-light-retro-collage-xhs-notes
description: Analyze topics, research and fact-check claims, write beginner-friendly Chinese copy, create light-retro collage artwork, render, and quality-check 3:4 Xiaohongshu knowledge carousels. Use when Codex must turn a keyword, article, document, screenshot, mixed source material, concept, or knowledge fragment into a sourced multi-page Xiaohongshu note; recommend the publishable angle before production; support text-centered or illustration-centered layouts; revise an existing note; or verify factual, editorial, layout, and image quality.
---

# Generate Light Retro Collage Xiaohongshu Notes

Create concise, sourced Chinese knowledge carousels with a youthful light-retro editorial collage style. Keep topic selection, research, image generation, local typography, and validation as separate stages.

## Workflow

1. Resolve the topic.
   - Identify the intended meaning, audience, and risk level.
   - Ask one concise clarification question when two plausible meanings would change the claims or story. Do not research or render past a material ambiguity.
   - Treat an explicit scope in the user's request as resolved.

2. Research before writing.
   - Browse current sources; do not rely on memory for time-sensitive or specialist claims.
   - Prefer original papers, standards, official documentation, and authoritative institutions.
   - Support each core claim with two independent publisher groups when available. When only one credible publisher group exists, record a specific `source_limitation` on that claim.
   - Read [references/research-protocol.md](references/research-protocol.md) for source selection, claim mapping, and semantic review.

3. Confirm the plan.
   - Recommend 4–12 pages and provide a one-line purpose for every page.
   - Wait for explicit page-count approval before generating assets or pages. An explicit page count in the user's original request already counts as approval.
   - Confirm `text_centered` or `illustration_centered`; allow a per-page mix only when the user accepts it.
   - Record only `confirmed_by_user`, `approved_page_count`, and `approved_layouts` in the project confirmation object. Do not copy the full request or unrelated private text into delivery artifacts.

4. Write the copy.
   - Produce exactly one recommended post title and two distinct alternatives.
   - Keep the Xiaohongshu post caption, including hashtags, at or below 200 non-whitespace Unicode characters.
   - Give every page one main idea. Map factual sentences to claim IDs and sources.
   - Prefer a clear conclusion, a compact explanation, and a concrete implication over academic jargon.
   - For beginner-facing technical topics, introduce an abstract idea through a familiar work or creator scenario. Carry one concrete example across at least two related pages when that makes the mechanism easier to follow.
   - Keep examples clearly labeled as examples, then state the accurate mechanism or boundary. Do not let an analogy replace the definition.
   - Use concrete subjects and verbs. Remove generic AI-marketing language such as “赋能”, “颠覆”, “解锁潜力”, “全面提升”, “智能升级”, and empty transitions such as “值得注意的是” unless the exact wording is itself the topic under analysis.
   - Render an ordered procedure as one numbered item per row, in strict top-to-bottom order. Never place two sequence numbers on the same visual line or scatter them around the illustration unless the user explicitly requests a non-linear diagram.
   - Read [references/content-contract.md](references/content-contract.md) before creating `project.json`.

5. Plan the visual system.
   - Use a 1080×1440 (3:4) canvas.
   - Use warm ivory paper, subtle grid or fiber texture, low-saturation Bauhaus colors, cobalt accents, and restrained cut-paper shadows.
   - Keep decorative density adaptive: sparse for dense copy, medium for light copy; decorations must remain subordinate to content.
   - Render page titles with a real medium, semibold, or bold face whose counters remain open. Do not simulate weight with a thick outline; use 0 px synthetic stroke by default and never exceed 1 px.
   - Measure the final wrapped copy before choosing its position. Derive a text card's height from the label, rendered line height, line count, and padding; never stretch a short paragraph to fill a fixed tall panel.
   - Keep short copy in a compact block within the approved top or bottom text zone. Expand the block for medium copy; shorten, split, or add a page when dense copy would require an undersized font.
   - Make copy control the composition. Finalize title wrapping, body wrapping, list rows, labels, CTA, and source height before assigning any illustration box.
   - Derive each page's title-to-visual and visual-to-body clearance from the measured copy. Measure actual visible bounds and use these bands: 48–72 px for short copy, 40–56 px for medium copy, and 36–48 px for dense copy. Do not force every page to use one fixed gap, but reject an unexplained gap above 72 px: consume it by enlarging or repositioning the visual-and-body chain instead of leaving a hollow strip.
   - Use the remaining safe area to size the primary visual: short copy may enlarge it to roughly 110%–125% of the base size; medium copy uses the base size; dense copy may reduce it, but never below the page's legible minimum visual box. If both text and the minimum visual cannot fit, shorten or split the copy.
   - Keep adaptive text-card height separate from exterior clearance. Copy length changes the card height first, then the available illustration zone and scale; the illustration never takes space already reserved for text.
   - When any continuous illustration, person, limb, or object crosses a canvas edge, apply a soft 72–120 px opacity fade into the paper background. Reject abrupt straight crops; keep faces, hands involved in the story, and required objects fully legible.
   - Reserve `2026`, `KIKI`, `AI`, and the current page's real topic keyword on every page. Use `2026` at top left, `KIKI` at top right, `AI` at bottom left, and `keyword_tag` at bottom right unless an approved composition swaps corners without omitting a tag.
   - Keep decoration at the outer edges. Never allow a title, body block, illustration, decoration, or corner label to overlap another element.
   - Apply the exact safe zones and mode rules in [references/layout-contract.md](references/layout-contract.md).

6. Generate text-free artwork only when needed.
   - Use ImageGen for original raster illustration or paper-collage assets, never for final Chinese typography.
   - Request no words, letters, numbers, logos, watermarks, or pseudo-text.
   - Prefer transparent cutouts. If transparency is unavailable, use a removable flat background and validate the extracted alpha edge.
   - Preserve one clean, immutable master asset for every page. When scale, composition, fading, or object placement changes, restart from that master or create a sibling variant; never use the last edited PNG as the next edit source.
   - Apply intentional paper or print grain once during final composition. Do not accumulate grain through repeated generation, feathering, sharpening, or resize cycles.
   - Read [references/image-asset-contract.md](references/image-asset-contract.md) before prompting or accepting an asset.

7. Render locally.
   - Install the Pillow and JSON Schema dependencies from `scripts/requirements.txt` in the active environment when missing.
   - Select a CJK font with `--font` or `XHS_FONT_PATH`; never redistribute an unlicensed system font.
   - Resolve the absolute directory containing this `SKILL.md` as `SKILL_DIR`; do not assume the user's current working directory is the Skill directory.
   - Use a new or empty output directory. The renderer rejects a non-empty directory so stale pages and QA artifacts cannot enter a delivery.
   - On macOS/Linux, run:

```bash
SKILL_DIR="/absolute/path/to/轻复古拼贴风格笔记自动生成skill"
python3 "$SKILL_DIR/scripts/render_note.py" project.json --output output/topic --font /path/to/cjk-font.ttf
python3 "$SKILL_DIR/scripts/validate_note.py" project.json --output output/topic
python3 "$SKILL_DIR/scripts/make_contact_sheet.py" output/topic/pages --output output/topic/qa/contact-sheet.png
```

   - On Windows PowerShell, run the equivalent commands with the Python launcher:

```powershell
$SkillDir = "C:\absolute\path\to\轻复古拼贴风格笔记自动生成skill"
py -3 "$SkillDir\scripts\render_note.py" project.json --output output\topic --font C:\path\to\cjk-font.ttf
py -3 "$SkillDir\scripts\validate_note.py" project.json --output output\topic
py -3 "$SkillDir\scripts\make_contact_sheet.py" output\topic\pages --output output\topic\qa\contact-sheet.png
```

   - If `python3` or `py -3` is unavailable, use the Python 3 executable from the active environment with the same absolute script paths.

8. Revise until validation is clean.
   - Treat any overflow, abrupt illustration-edge crop, clipping, unsupported claim, text/non-text clearance violation, missing file, unreadably heavy title, undersized primary visual, visibly empty oversized text panel, stray raster noise, repeated texture seams, edge halos, or cumulative edit artifacts as a failure.
   - Do not fix overflow by shrinking below the configured minimum font size; shorten or restructure the copy.
   - Inspect the contact sheet at full resolution. Check every character, number, unit, date, source marker, corner label, and decorative edge.
   - Re-extract the final page claims and perform the semantic review in `research-protocol.md`. Automated geometry checks cannot prove factual correctness.

9. Deliver the complete note.
   - Return all page PNGs, `project.snapshot.json`, one recommended title, two alternatives, the caption, a source ledger that maps claims back to page files, and the QA report.
   - State the confirmed page count, layout mode, font used, and any carefully bounded research caveat.

## Layout Modes

- `text_centered`: Use the horizontal center 60% as the main text column. Place the readable semibold title at the top, measure the explanation before positioning it in the upper/middle text zone, and size the bottom or outer-corner illustration from the remaining safe area. Enlarge it on short-copy pages and reduce it only when dense copy requires space.
- `illustration_centered`: Reserve the middle for one adaptive primary illustration. Place the readable semibold title above it. Measure bottom copy after wrapping: short copy sits as a compact lower block and gives the visual room to grow, while longer copy expands upward and reduces the visual no further than its legible minimum. Never place body copy over the illustration.
- `cover`: Use only on the first page. Center the large bold title and keyword, then place the primary visual below it. If the user supplies a person, keep that person centered and preserve their face and hairstyle.

## Validation Utilities

- `scripts/render_note.py`: Deterministically typeset and render 3:4 pages; emit element masks and a layout report.
- `scripts/validate_note.py`: Validate approval, title/caption contract, source traceability, dimensions, clipping, and overlap results.
- `scripts/make_contact_sheet.py`: Create a visual-review sheet from rendered pages.
- `scripts/self_test.py`: Render and validate the bundled six-page example in a temporary directory.

Use `assets/examples/light-retro-collage-case-contact-sheet.png` only as a style, hierarchy, and density reference. Do not copy its subject or treat its existing objects as mandatory.

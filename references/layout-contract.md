# Layout Contract

Read this file before storyboarding or rendering.

## Canvas and hierarchy

- Render every page at exactly 1080×1440 pixels.
- Keep primary text at least 72 px from page edges.
- Keep illustrations and decorations at least 24 px from page edges.
- Reserve the four corner-label zones before placing any decoration.
- Keep a visible hierarchy: keyword/title, page title, body, annotation, corner label.
- Render every page title with a real medium, semibold, or bold font face. Keep counters and joins clearly distinguishable at phone size.
- Do not create title weight with a heavy synthetic outline. Use 0 px stroke by default; allow at most 1 px only when a specific font needs edge compensation.
- In mixed Chinese/Latin titles, typeset Chinese, digits, and Latin runs separately when their cap heights differ. Align them to one optical center or baseline and use fixed run spacing.
- Finalize and measure every text block before assigning the primary illustration box. Text height determines the remaining visual zone, not the reverse.
- Compute title-to-visual and visual-to-body clearance from actual visible pixel bounds. Use 48–72 px for short copy, 40–56 px for medium copy, and 36–48 px for dense copy. Page-specific clearances may differ when copy density differs, but 36 px is the hard floor and 72 px is the default ceiling.
- Reject any unexplained title-to-visual or visual-to-body gap above 72 px. Use surplus space to enlarge the primary visual, then reposition the visual-and-body chain as a unit; do not strand the surplus as a blank band between adjacent content blocks. Exceed 72 px only when the approved composition explicitly calls for intentional whitespace.
- Use low-saturation ivory, cobalt, butter yellow, coral, muted blue, and charcoal; do not simulate dirty, torn, or distressed “retro” damage.

## Cover

- Center the large headline in the upper half.
- Emphasize the concept keyword by size or weight.
- Place the primary illustration below the headline.
- Use the 688×464 primary-illustration box in `assets/layouts/cover.json` as the cover baseline. Adapt it only after the final headline and subtitle are measured.
- Do not allow decoration inside the title mask or corner-label zones.

## `text_centered`

- Use x=216…864 as the default horizontal text-safe column.
- Place the bold title in x=216…864, y=185…340 and the body in x=216…864, y=380…1005.
- Put the main illustration below the body or in a noncompeting outer corner.
- Treat the 624×220 box x=228…852, y=1070…1290 as the medium-copy baseline. Short copy may enlarge the illustration into newly available safe space; dense copy may reduce it, but never by invading text or below the approved legible minimum.
- Limit small stickers, stars, labels, dots, and similar decoration to at most 20% of visible page area.

## `illustration_centered`

- Place the bold title inside x=170…910, y=175…320.
- Treat the 608×392 box x=236…844, y=500…892 as the medium-copy baseline, not a fixed box. After measuring copy, allow a short-copy page to grow the visual to about 110%–125% of baseline. Dense copy may reduce it, but keep at least a 480×320 legible visual box.
- Put explanatory text above and/or below that illustration, never over it.
- Measure the final wrapped text before placing the lower block. Use the actual glyph height and line gap, not the nominal font size.
- Compute a compact block or card height as `label + rendered lines + internal padding`. Do not extend the card merely to reach a fixed bottom coordinate.
- Place the measured lower text block inside its safe zone first. Fit the visual into the remaining area between the title and body while preserving at least 36 px clearance on both sides. If the baseline visual does not fit, reduce it only to the minimum box; after that, shorten or split the copy.
- For 1–3 visual lines, use a compact lower block and place it in the lower portion of the approved text zone. For 4–6 lines, expand upward while preserving the illustration clearance. For more than 6 lines, shorten, restructure, or add a page instead of shrinking below the minimum font size.
- When no card is used, bottom-align short copy inside the bottom text-safe box. When a card is used, keep unused breathing room outside the card rather than as a large empty area inside it.
- Keep speech bubbles only for an actual speaking action, with short text and the same clearance rules as other copy.

## Collision and density rules

- Keep actual text pixels at least 36 px from illustrations and decorations.
- Check both adjacency pairs independently: title-to-visible-visual and visible-visual-to-body. Their values must follow the page's measured copy density rather than a fixed series token, and both must remain inside the applicable 36–72 px band unless an intentional exception was approved.
- Never let a primary visual disappear or become a decorative thumbnail. For a centered 1080×1440 inner page, reject any main visual smaller than 480×320 unless the approved layout defines a different explicit minimum.
- Apply a 72–120 px feathered alpha fade when a continuous illustration crosses a canvas edge. Reject a high-contrast straight cutoff at the boundary; keep the central subject and story-critical hands or faces opaque.
- Keep distinct text blocks visibly separated; do not use overlap as a decorative effect.
- Keep decoration near the outer edges. Never solve an empty area by moving decoration into the title or body column.
- If copy and artwork cannot both fit, shorten or restructure the copy, or change the approved inner-page mode. Never overlap, stack, or hide elements to force a fit.
- Decide text position only after line wrapping. A fixed y-position or fixed-height panel is invalid when it produces a visibly empty lower half for short copy.
- Do not bake unknown decorations into an opaque full-page background when collision checking matters.
- Use alpha masks for every illustration and decoration. Reject the page when a dilated text mask intersects a non-text mask.
- Reject clipping, overflow, unreadably small text, and elements that invade the wrong mode's safe zone.

Always inspect the final contact sheet and the full-resolution pages. Passing masks is necessary but not sufficient for good composition.

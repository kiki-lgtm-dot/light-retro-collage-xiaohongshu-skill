# Text-free Image Asset Contract

Read this file before generating or accepting raster artwork.

## Prompt requirements

State the page role, layout mode, exact safe zone, palette, paper medium, and maximum decoration density. Require:

- no readable text, pseudo-text, letters, digits, logos, signatures, or watermarks;
- one original subject that supports the page's core idea;
- clean separation from reserved text and corner-label regions;
- restrained paper grain, cut-paper edges, gentle shadows, and low-saturation Bauhaus colors;
- no copied person, logo, wording, or exact layout from a reference.
- a visual scale matched to measured copy density: enlarged for confirmed short copy, baseline for medium copy, or compact-but-legible for dense copy;
- a 72–120 px soft opacity fade into the paper background wherever a continuous subject, person, limb, or object crosses the canvas edge.

For reusable cutouts, request a flat removable chroma background or a true alpha PNG when the selected image workflow supports it.

## Clean-master and revision policy

- Keep one immutable clean master for every generated page asset.
- Start each revision from that master or create a named sibling variant. Never feed an already revised delivery PNG into another revision pass.
- Perform cropping and scale changes from the highest-quality master without repeated downscale-upscale cycles.
- Add the approved paper or print grain once at final composition. Do not reapply grain after every edit.
- After any local edit, inspect the image at 100% for stray speckles, duplicate texture patches, edge halos, broken gradients, and over-sharpening. Reject the asset when these artifacts are visible.

## Acceptance checks

Reject an asset when it contains pseudo-writing, illegible charts, accidental branding, a full-page baked layout, abrupt high-contrast edge crops, excessive distressing, cumulative edit noise, repeated texture seams, edge halos, or decorative density that competes with copy.

Reject an illustration that can fit only by invading a measured text zone. Also reject a primary visual that has been reduced below the page's legible minimum; shorten or split the copy instead. When short copy leaves a large unused lower region, request or create a larger sibling asset variant rather than scaling the entire paper background or grid.

Also reject any raster asset wider or taller than 4096 px, or larger than 16,777,216 total pixels. These are renderer safety limits, not resize targets. The delivered copy is decoded to RGBA and re-encoded without source metadata or trailing payloads; its manifest hash therefore covers the sanitized PNG rather than the input bytes.

Before rendering, crop transparent padding, preserve a small breathing margin, and save the alpha PNG under the project's `assets/` directory. Record its portable `assets/.../*.png` path in `project.json`; do not use an absolute path, `..`, credentials, or a symlink that escapes the project. The renderer fits it inside the assigned illustration box without stretching, copies it into the delivery, and records its hash.

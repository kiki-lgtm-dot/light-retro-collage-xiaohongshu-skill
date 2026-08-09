# Content and Project Contract

Read this file when planning copy or creating `project.json`.

## Required decisions

Record:

- the concept and resolved meaning;
- the intended audience;
- the approved page count in `confirmation.approved_page_count`;
- the approved inner-page layout mode or modes in `confirmation.approved_layouts`;
- one recommended post title and exactly two distinct alternatives;
- a post caption of at most 200 non-whitespace Unicode characters;
- three project-level corner labels plus one page-level keyword label;
- the chosen layout mode for every page;
- a claim ledger and a source ledger.

Do not render when `confirmation.confirmed_by_user` is false, the approved count differs from `page_count`, or `page_count` is outside 4–12. Keep only this structured approval record in `project.json`; never copy the full user request or unrelated private context into it.

## Character counting

Count the post caption after removing Unicode whitespace. Count Chinese characters, punctuation, Latin letters, digits, emoji, and hashtag characters individually. Do not include the three post titles, page copy, or the source appendix in this 200-character limit.

## Page copy

Use one core idea per page. Keep the title decisive and the body short enough to remain readable at the minimum font size. Prefer:

1. the conclusion;
2. the simplest accurate explanation;
3. one implication, example, boundary, or correction.

Avoid absolute terms such as “always,” “completely,” and “guaranteed” unless a cited source establishes them.

## Beginner examples and voice

When the intended audience is new to the topic:

- open an abstract definition with a familiar situation, such as making a weekly report, organizing research, planning content, or repeating a review checklist;
- use the smallest example that reveals the mechanism, not a decorative story unrelated to the claim;
- when useful, carry the same example across two or more pages so readers do not have to relearn the setting;
- mark the example or analogy as an example, then state the accurate definition, mechanism, or boundary;
- prefer “谁在什么情况下做什么，结果怎样” over noun-heavy slogans and generic summaries;
- keep one sentence to one job. Delete throat-clearing and transitions that do not add meaning.

Reject generic AI-marketing phrasing such as “赋能”, “颠覆”, “解锁潜力”, “全面提升”, “智能升级”, “一站式”, “开启新篇章”, “值得注意的是”, and “让我们一起探索” unless the wording itself is quoted for analysis. Replace it with the specific actor, action, condition, or result.

For a 5-page inner sequence about an abstract technical concept, include at least two concrete example beats across the sequence. Not every page needs a new example; one running example is usually clearer than five unrelated analogies.

## Ordered procedures

When the content is a numbered sequence:

- keep one number and one action on each row or stacked block;
- preserve strict top-to-bottom reading order and consecutive numbering;
- use one shared left edge, hanging indent, line spacing, and emphasis rule;
- never combine two numbered actions on one line merely to save space;
- never use a two-column, radial, or scattered arrangement unless the user explicitly asks for a non-linear diagram;
- if the ordered list no longer fits at readable size, shorten the actions, reduce decorative copy, or add a page before reducing the illustration below its minimum legible size.

## Project fields

Use `assets/project-schema.json` as the machine-readable baseline. Each page contains:

- `number`: one-based page number;
- `kind`: `cover` or `inner`;
- `layout`: `cover`, `text_centered`, or `illustration_centered`;
- `eyebrow`, `title`, `body`, and optional `bullets`;
- `claim_ids`: facts shown on that page;
- `illustration`: a built-in motif name or a portable `assets/.../*.png` path without `..` traversal; the renderer copies each custom alpha PNG into the delivery and hashes it in the manifest. Apply the alpha, path, and pixel limits in the [image asset contract](image-asset-contract.md);
- `keyword_tag`: 1–4 Unicode characters, or 1–6 ASCII letters for short English terms such as `Agent` and `SKILL`.

Set the series corner system explicitly on every project: `corner_tags.top_left` is `2026`, `corner_tags.top_right` is `KIKI`, `corner_tags.bottom_left` is `AI`, and each page's bottom-right `keyword_tag` is the real topic keyword for that page, never the literal placeholder “关键词”. Keep non-ASCII keywords to at most four Unicode characters and short English terms to at most six letters. If the approved composition swaps corners, preserve all four required labels and their hierarchy.

The first page must be a cover. Every later page must use one of the two inner-page modes.

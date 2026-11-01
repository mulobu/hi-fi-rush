# 0007 — Holes are each overlay's design; the pipeline's rules are shared

- **Date:** 2026-11-01
- **Status:** Accepted

## Context

The question: can video windows sit in different places in different
overlays? In OBS terms, the sources have no fixed position. The overlay page
measures each hole with `getBoundingClientRect()` and pushes the result with
`SetSceneItemTransform` (§2). And each collection has its own scene items, so
no overlay inherits another's positions.

## Decision

- **Hole placement belongs to the overlay.** Position, size, aspect and how many
  holes each scene has are authored in the overlay's own page, the way
  `PANELS` is today.
- **Any aspect fills exactly.** A source is cropped to its hole's aspect and then
  stretched (`fillTransform`), so it never distorts.
- **The horizontal and vertical pages place their holes independently.**

Every overlay inherits these rules from the shared pipeline:

- **One source, one hole at a time.** There is one OBS item per source, so
  when two visible holes want it, the panel on air wins (`chooseWinners`) and
  the other hole keeps its drawn placeholder.
- **Holes may nest, but must not partly overlap.** A hole fully inside another
  is merged away (`mergeCuts`). A partial overlap flips back to solid art under
  `fill-rule: evenodd`, and `?debug=1` warns about it.
- **The page is exactly the canvas size**, 1920 × 1080 (or 1080 × 1920 for
  vertical), so on-screen positions are canvas pixels with no conversion.
- **Holes show only shared sources**
  ([0004](0004-one-contract-for-every-overlay.md)).
- **Cut-outs are rectangles**, rotated ones included. Another shape is a
  change to the cut-out code in `core/`. The OBS source behind it stays a
  rectangle either way.

## Consequences

A new overlay is free to lay out every scene from scratch. What it cannot do
is break the rules above silently, because they live in shared code rather
than in each overlay.

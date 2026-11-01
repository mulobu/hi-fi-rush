# 0015 — The `Chat` source is sized per overlay

- **Date:** 2026-11-02
- **Status:** Accepted, built

## Context

`tools/obs-setup.py` made `Chat` 800 × 938 in every collection: the aspect
of the comic's chat hole. A source is cropped to its hole's aspect before it
is stretched, so for a browser source a hole of any other shape cuts chat
text off at the sides or the top.

Money Talks Monday's CHAT has a 16:9 cam beside the chat
([0014](0014-cam-is-the-iphone-camera.md)), which leaves a tall, narrow
column of 603 × 962. At 800 × 938 the crop would take about a quarter of the
chat's width.

The collection is per overlay ([0003](0003-one-scene-collection-per-overlay.md)),
and so is its `Chat` input. Nothing stops each overlay rendering chat at its
own hole's size.

## Decision

- **`overlay.json` may say `"chat": {"width": W, "height": H}`**, and setup
  makes `Chat` exactly that size. It asserts the size on every run, as it
  already did for 800 × 938.
- **Without the key it is 800 × 938**, so the comic is unchanged.
- **The overlay draws its chat hole at that size**, so the source fills it
  with nothing cropped.

## Consequences

- **The chat page lays itself out at the hole's own size**: narrower lines,
  more of them. It is not a crop.
- **The size lives in two places**, `overlay.json` and the page's chat hole,
  and they must agree. A mismatch crops rather than breaking, which is how
  every overlay behaved before this.

# 0011 — New overlays start from `overlays/_template/`

- **Date:** 2026-11-01
- **Status:** Accepted, built 2026-11-01. Not yet built as a collection in
  OBS; see Consequences

## Context

The second and third shows will each need an overlay. The comic page is the
only example, and it is a poor thing to copy: 1,200 lines of art, tilted
panels, a skirt sized by simulation. A new overlay should start from what
actually has to be there.

The vertical page also still held ~180 lines that belong to *being on the
vertical canvas*, not to the comic:

- the platform safe zones and the pass that lifts tags clear of them;
- finding the canvas and its scene by uuid;
- the vertical page hooks.

Every overlay's vertical page would have copied them.

## Decision

- **`overlays/_template/` is a working overlay**, built only from what
  `core/` requires:
  - six 16:9 panels in a 3 × 2 grid, and six 9:16 ones for vertical, all
    `fill`, so every scene lands square on its frame;
  - every kind of hole: a bare full-panel game with an inset cam, chat beside
    cam, a full cam, and a BRB with none;
  - minimal CSS that meets `core/README.md`'s two rules (a 15px panel
    border, and a hidden placeholder in a punched hole);
  - its own `chat.css`, an `overlay.json` with no mascot, a README with the
    steps, and a CLAUDE.md skeleton.
- **`core/vertical.js`** holds what any vertical page needs: `SAFE_*` (the
  strictest platform margins, since Restream sends one encode to all of
  them), `fitTagsToSafeArea`, `resolveVerticalScene`, and `verticalPage()`.
  `obs-link.js` gains its twin, `mainPage()`.
- **Each page's boot script creates `PAGE`**, with one of those factories.
  Neither page writes its hooks out by hand any more.
- **`_` marks a folder that is not a show.** `--export` without `--overlay`
  skips it, though it builds and runs like any other overlay.

## Consequences

- **A new overlay is:** copy the folder, change two names in `overlay.json`,
  design, then `obs-setup.py --overlay <name> --vertical --no-profiles`.
- **`vertical.html` went 1,476 → 1,307 lines**, and `overlay.html` lost its
  hooks block.
- **Verified 2026-11-01:**
  - both comic pages re-read in OBS after the move: all twelve punch sets
    unchanged;
  - both template pages in a browser: punch sets exactly as designed
    (`START` Cam, `CHAT` Cam+Chat, `GAME` Cam+Game with the inner cut merged,
    `CAM` Cam, `BRB` none, `END` Cam);
  - the vertical template lifts its tags, and no page logs a console error;
  - at a punched CHAT hole, every painting layer is masked or transparent
    (§2's structural check).
- **Not yet verified in OBS.** The template has not been built as its own
  collection, which is also [0003](0003-one-scene-collection-per-overlay.md)'s
  open measurement: whether the vertical plugin gives a fresh collection a
  canvas, and which audio devices a new collection starts with. Both wait
  on the user's go-ahead, since they switch the running OBS's collection.
- **The second show's overlay waits for its design.**

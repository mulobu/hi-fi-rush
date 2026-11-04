# 0024 — Tech Talks Tuesday: the vertical page shares the fusion engine

- **Date:** 2026-11-04
- **Status:** Built; in OBS on VCOMIC, read back off OBS. Not yet seen on a stream.
  Its hand-made filters are superseded by [0025](0025-setup-owns-the-transition-filters.md):
  setup now creates both.

## Context

The user: "can you now complete the vertical one as well please". On the
`Tech Talks Tuesday` collection, `vertical.html` was still the template's.
The vertical canvas held an empty `Vertical Scene`, so setup had never run
with `--vertical`.

The horizontal page kept everything in `fusion.js`, layout and engine
alike. That included `CANVAS_W = 1920`, the windows, the gardens and the
`GridFX` transition, which named `COMIC`. A second page could load none of
it.

## Decision

- **One engine, two layouts.**
  - `fusion.js` is now shared, and holds:
    - the scene copy;
    - `setDesign`, whose surface cuts now come from the panel's own holes,
      skipping any window inside another;
    - `GridFX`;
    - the flower loop, started by `startFusion()`;
    - the panel helpers, sized from `CANVAS_W` and `CANVAS_H`.
  - Each page defines its canvas size before `fusion.js`. After it, each
    page defines `PANELS`, `GARDENS` (scene → garden and cell region) and
    `GRID_TARGET()`.
  - The palette moved to `palette.css`, which both pages load.
  - `tech.css` stays the horizontal page's stylesheet; `vertical.css` is
    the vertical page's.
- **The portrait layout,** 1080 × 1920:
  - **Safe area.** Type stays inside `SAFE_*` (x up to 916, y 140 to 1596).
    The header's row sits at 140–212. The footer starts at 1440, with
    socials at phone size on the first row and the brand and scene name on
    the second, ending at 1596.
  - **Bands.** Both bands run on to the canvas edge behind the platform
    chrome.
  - **Face on top,** every cam window 16:9 ([0014](0014-cam-is-the-iphone-camera.md)),
    and Chat at 624:936 ([0015](0015-chat-source-sized-per-overlay.md)).
  - **GAME** stacks the cam (768 × 432) over a label strip and the full-width
    game (1080 × 608).
  - **CHAT** has the cam over the copy and a small garden, beside a
    468 × 702 chat.
  - **CAM** has the show's title over the full-width cam, with a flower bed
    under it.
  - **START and BRB** put the words top left, with a tall sunflower in the
    specimen disc beside them. A bed of tulips, daisies and grass runs
    along the footer.
  - **END** is the title over an 832 × 468 cam, with a bed at the right.
  - **No flower on video.** Each scene's flower region stops short of every
    window.
- **Its own transition filter.** `Botanical Grid` also sits on VCOMIC at
  index 0, disabled at rest:
  - It uses the same `grid-bend.shader` and COMIC's settings, except
    `Grid_Columns` 54. 1080 / 54 gives the 20 px cells that 1920 / 96 gives
    the horizontal.
  - The vertical page drives it like the horizontal's, from the main
    canvas's program scene.
  - `GRID_TARGET()` is VCOMIC's `sourceUuid`, and `GridFX.attach` waits
    until `core/vertical.js` has found it.
- **`?scene=` already names the OBS scene on the vertical page**
  (`core/vertical.js`). The standalone preview is therefore
  `vertical.html?preview=GAME`.

## Consequences

- **Verified in OBS** with live camera, game and chat, on 2026-11-04:
  - **Vertical holes,** read back off OBS:

    | Scene | Holes |
    | --- | --- |
    | GAME | Game 0,762 1080 × 608 + Cam 48,282 768 × 432 |
    | CAM | Cam 0,588 1080 × 608 |
    | CHAT | Cam 48,236 768 × 432 + Chat 448,700 468 × 702 |
    | START, BRB | None |
    | END | Cam 48,642 832 × 468 |

  - **The transition** ran on VCOMIC from 0.08 to 1.94 s on every switch.
  - **Fixed-progress captures** show the mesh, the edge-on green line and
    the rise in portrait.
  - **Both canvases transitioning together:** six switches skipped
    **0 of 866** frames.
- **The horizontal page is unchanged.**
  - In the browser, before and after the split, every element's box,
    style and text matched on all six scenes, along with the surface path,
    page transform and `PANELS`. Only the countdown's ticking differed.
  - In OBS, its holes read back as in the overlay's table, and its
    transition still fires.
- **Checked in the browser for every scene:**
  - No flower cell lands in a window at 40 instants across two gusts.
  - No text box leaves the safe area.
- **Cost.** Converting the flowers costs 8.8 ms a frame on vertical
  START, at 30 fps, against about 2.2–2.8 ms on the other scenes. On
  START, BRB and END both pages convert at once.
- **A shader edit now means recreating two filters.**
  - COMIC's is addressed by name.
  - VCOMIC's is addressed by `sourceUuid`. Like every vertical scene,
    VCOMIC is "not found within the canvas Main" by name.
  - Then refresh both `Overlay` and `OverlayV`.
- **Setup does not create either filter.** Both were made over the
  websocket by hand, so a fresh machine has the pages but no transition.
  `GridFX` then falls back to an instant cut, and the HUD says so.
- **Setup flagged an unrelated setting.** The vertical output's stored
  encoder is `ffmpeg_svt_av1`, which is inert unless Advanced is ticked in
  the plugin's output settings.

## Rejected

- **A copy of `fusion.js` for the vertical:** two transitions and two
  gardens to keep in step.
- **`vertical.css` as overrides on `tech.css`:** the horizontal's
  `body[data-scene=…]` rules outrank plain overrides, and every horizontal
  edit would leak into the vertical.
- **Reusing COMIC's 96 columns:** on a 1080-wide frame they make 11 px
  cells, finer than the horizontal mesh.

# 0027 — Fitness Friday: a blueprint sheet, and the word sting replaces the pan

- **Date:** 2026-11-04
- **Status:** Built. The user approved the horizontal page in the browser
  on 2026-11-04. Both pages went into OBS as the `Fitness Friday` collection
  on 2026-11-05, and all twelve punch sets were read back there (see the
  overlay's `CLAUDE.md`). Not yet streamed

## Context

The user's brief for the Friday show:

- **Reference:** the intro of Cleo Abram's YouTube show, for its HUGE
  wording.
- **Palette:** a royal blue base with bright yellow highlights.
- **Art:** human anatomy blueprints, a different one on each scene:
  heart, brain, full body and so on. Nothing about fitness itself.
- **Fallback, named up front:** if yellow on royal blue does not look
  good, real blueprint colours.

Taking the reference's type and pace is fine. Copying her name, logo or
title cards is not.

## Decision

- **The page is a drafting sheet.** It is royal blue, `#1c41d4` at the
  centre and `#0f2690` at the edges, with a 24 px grid and a 120 px grid.
  - It has a zone border (1–8 across, A–E down) and a title block.
  - Each scene's windows are cut out of it with evenodd, as on Tuesday's
    surface, and the video shows through them.
  - The page of panels paints nothing.
- **Type:**
  - **HUGE lines** are set in Anton. Each line is fitted to its box's
    width at boot, so a short word sets bigger than a long one, a
    justified stack.
  - **Annotations** are set in JetBrains Mono.
  - **Colour:** yellow `#ffd60a` is for the drawings and the highlighted
    word. White is for the rest.
- **One plate per scene**, drawn in code in `anatomy.js` with no image
  files. The outlines are hand-placed points through Catmull-Rom curves.
  The detail is seeded, so every load draws the same plate:
  - the brain's folds are an activator–inhibitor labyrinth, traced with
    marching squares, with the major sulci forced as valleys;
  - the lungs carry a bronchial tree grown inside them;
  - the heart carries coronary twigs, and its vessels are tubes with cut
    ends;
  - the hand's carpals are pebbles.

  | Scene | Plate |
  | --- | --- |
  | START | Full body, front view, eight heads tall |
  | CHAT | Brain, lateral view |
  | GAME | ECG strip and a small beating heart, in the footer |
  | CAM | Heart, front view, with a parts list |
  | BRB | Lungs, with a breathing cue |
  | END | Hand skeleton, waving |

- **The sting replaces the pan** (`sheet.js`, loaded in place of
  `core/camera-pan.js`):
  1. A yellow slab and a blue one sweep in from the left.
  2. The next scene's words slam in one at a time, filling the frame. Each
     is at most 90% of the width and 66% of the height, with the word
     before it zooming through as an outline. The last word is blue on a
     yellow flash.
  3. The slabs sweep off to the right, onto the new sheet.

  The layout, the holes and the OBS sources change only while the frame
  is covered. A switch takes about 1.3 s with two words.
- **Words per scene:** START "FITNESS FRIDAY", CHAT "LET'S TALK", GAME
  "GAME ON", CAM "UP CLOSE", BRB "BE RIGHT BACK", END "THAT'S A WRAP".
- **The clock times the sting, not the animation.** Web Animations draw the
  slabs, but each step lands on a `setTimeout` and commits its end state.
  This was measured: with the browser pane hidden, the frames stalled,
  `Animation.finished` never resolved, and the first build stayed
  covered for good.
- **Idle motion is a transform on its own layer, so it never repaints.**
  - the heart beats at 72 bpm;
  - the lungs breathe on an 8 s cycle, in step with the cue bar;
  - the hand waves;
  - the ECG scrolls.
- **No sound.** Monday's sting has sound effects; this one has none yet.

## Consequences

- **Punch sets, read in a browser** (OBS is not built yet):

  | Scene | Holes |
  | --- | --- |
  | START, BRB | None |
  | CHAT | Cam 48,64 1216 × 684 + Chat 1312,64 560 × 952 |
  | GAME | Game 0,0 1920 × 1080 + Cam 0,710 544 × 306 |
  | CAM | Cam 40,40 1472 × 828 |
  | END | Cam 1032,96 816 × 459 |

  Every cam window is 16:9 ([0014](0014-cam-is-the-iphone-camera.md)), and
  Chat is `overlay.json`'s 560 × 952
  ([0015](0015-chat-source-sized-per-overlay.md)).
- **A press during the sting:** the newest press wins, and presses never
  queue. While the frame is covered the words restart for the new scene;
  while it is uncovering, the slabs come back from wherever they are.
  Checked in the browser: BRB then CHAT pressed during one sting landed
  on CHAT, with Cam and Chat punched.
- **Boot cost:** the brain's folds take about 90 ms, once, in the browser
  pane. The other plates are cheap.
- **Not measured:** the render cost in OBS, the sting's frame rate there,
  and how the 1.3 s switch feels across a real stream.
- **The palette is easy to change.** It lives in tokens at the top of
  `blueprint.css` and in the gradient stops in `overlay.html`, so the
  user's fallback (real blueprint colours) is a change of tokens.

## Rejected

- **Traced or downloaded anatomy images.** They would need downloads and
  licences, a raster cannot animate one part (the beat, the breath, the
  wave), and a trace is no cleaner than drawing it.
- **A pan across one huge blueprint sheet.** The reference's point is
  words that fill the frame. A pan also needs the comic's skirt and
  overshoot handling, which a covered cut does not.
- **Lines that draw themselves** (`stroke-dashoffset` on every path). The
  brain alone has hundreds of paths. Instead, a clip reveals each plate
  top to bottom behind a moving scan line.

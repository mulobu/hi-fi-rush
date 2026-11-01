# 0013 — Money Talks Monday: the smash replaces the pan

- **Date:** 2026-11-02
- **Status:** Accepted; built 2026-11-02 (`overlays/money-talks-monday/smash.js`, run by both pages), in OBS the same day: punch sets read back on both canvases, sting frames on time

## Context

The comic overlay's transition is the pan: one oversized page, and the camera
moves across it to the next panel (`core/camera-pan.js`). Money Talks Monday
is not a page of panels. Its frame is the two halves of one banknote, and the
user designed its transition on 2026-11-02:

- the white borders rewind like a scrubbed YouTube progress bar;
- the halves slam together into the whole note and shake;
- a Gandhi coin spins in the note's empty centre;
- the halves open into the next scene's frame.

[core/README.md](../../core/README.md)'s "Another transition" already allows
this. A page loads its own file in place of `camera-pan.js`. That file defines
`current`, `transformFor(t)` and `goTo(t, {instant})`, and `goTo` calls
`applyPunch` and `startTracking`.

## Decision

- **`overlays/money-talks-monday/smash.js` takes the place of
  `camera-pan.js`.** Nothing in `core/` changes.
- **The closed note covers the whole frame**, and every change to the holes
  happens behind it. While the note is closed, `goTo` jumps the page to the
  new panel instantly, calls `applyPunch`, and lets the OBS sources move once.
  Then it opens.
- **The video never moves during a switch.** Only opaque art moves, over
  still video. There is no per-frame tracking, and nothing mid-switch can show
  a source in the wrong hole.
- **The frame's slants and the cam notch are `over` art over rectangular
  holes.** [0007](0007-holes-are-each-overlays-design.md)'s rule that cut-outs
  are rectangles holds.
- **OBS's own transition stays Cut, 0 ms.** The smash is the transition, as
  the pan is for the comic.
- **The full sting, about 1.9 s, plays on every switch.** That's the user's
  choice. START, BRB and END are the note held closed, so a switch out of one
  plays only the opening half.
- **A press during a sting retargets it; presses never queue.**
  - While the note is closing or closed, it opens to the newest scene.
  - While it is opening, it closes again from where it is.
  - An unknown scene is ignored, as with the pan.

## Consequences

- **The comic's skirt is not needed.** That was the oversized backing sized
  so a mid-pan view never showed bare canvas. Here the page is exactly the
  canvas, 1920 × 1080, with no 7680 × 4320 transform, so it is much lighter
  for OBS's browser.
- **A switch takes about 1.9 s, against the pan's 0.98 s.** Whether that
  wears thin over a real stream is not measured.
- **Everything depends on the closed note covering the frame.** The first
  1500 × 750 art cannot cover it without an upscale and cropping. The
  re-export at 3840 × 2160 (16:9) is what makes the decision hold.
- **The transition sounds go through `Overlay`'s audio** and so reach the
  stream mix, like alert sounds.
- **The shake happens only while the note is closed.** The video behind
  doesn't shake, and at that moment none of it is visible.

## Rejected

- **A pan across a page of panels, the comic's way.** The frame here is not a
  page, and the user's transition is a collision, not a camera move.
- **A wipe that animates the masks.** It would rebuild two mask images every
  frame, where the pan rebuilds them once per scene change.
- **Moving the video with the halves.** It needs the same every-frame
  position pushes as a pan, for something the closed note hides anyway.

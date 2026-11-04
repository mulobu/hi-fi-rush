# 0016 — Tech Talks Tuesday: a text-mode screen, and the glitch replaces the pan

- **Date:** 2026-11-02
- **Status:** Superseded by 0017 (2026-11-03)

## Context

The user asked on 2026-11-02 for a third overlay, Tech Talks Tuesday:
everything ASCII, a sunflower as the hero (a turning 3D one was their
suggestion), tulips behind the scenes, and a glitch for the transition, kept
old-tech.

Two things follow from "everything ASCII":

- **The frame is characters, not pictures.** Money Talks Monday's frame is a
  bitmap note in DOM layers. Here every visible thing — windows, words, the
  flower, the noise — is a character in a cell, and the cells have to tile
  the canvas exactly or the text-mode look breaks.
- **A 3D flower in characters is a renderer, not a drawing.** donut.c's
  method — sample a surface, project, keep the nearest point per cell, pick
  the character by brightness — has to run every frame.

[core/README.md](../../core/README.md)'s "Another transition" allows a page
its own transition file, as [0013](0013-money-talks-monday-smash-replaces-the-pan.md)
did for the smash.

## Decision

- **Every visible pixel is one canvas of character cells**
  (`overlays/tech-talks-tuesday/ascii.js`): 12 × 24 px cells, 160 × 45 on the
  horizontal canvas. A cell is a character, a foreground and a background
  from the CGA's sixteen colours. **A cell with no background is
  transparent: that is a window onto an OBS source.**
- **The canvas draws only the cells that changed**, each copied from an atlas
  where every distinct cell is painted once. Boxes and blocks are drawn as
  shapes, so they join whatever font loaded.
- **`glitch.js` takes the place of `camera-pan.js`.** Nothing in `core/`
  changes. The page of panels paints nothing; its panels carry holes.
- **A switch:** every cell turns to noise over 300 ms, row by ragged row; at
  320 ms, with every cell noise, the page jumps, `applyPunch` runs and the
  OBS sources move once; from 400 ms the next scene prints back in, top row
  first, by 920 ms. Rows slip sideways throughout. About 1 s, on every
  switch.
- **The video never moves.** Only opaque cells cover and uncover it, as the
  note's halves do on Money Talks Monday.
- **A press before the cut changes where it goes; a press while printing
  corrupts again from where it is.** Presses never queue. An unknown scene is
  ignored.
- **30 frames a second**, a cap in `glitch.js`'s loop.
- **OBS's own transition stays Cut, 0 ms.**

## Consequences

- **Light at rest.** No 7680 × 4320 transform and no masks rebuilt: GAME's
  frame costs 0.01 ms to compose and draws nothing when nothing changed;
  START with the turning sunflower about 1 ms (measured in the app's
  browser).
- **The glitch is the expensive part.** A frame where every cell changes is
  12 ms to draw (same browser); the noise re-rolls 30% of cells a frame to
  keep it near a third of that. In OBS, six switches back to back skipped
  0 of 542 frames at 60 fps, with a game running.
- **The look depends on VT323 from Google Fonts.** Without it the cells draw
  in Consolas, wider and rounder.
- **Holes have to suit the grid.** 16:9 lands exactly on 12 × 24 cells only at
  multiples of 384 × 216. A cam window of any other size gets a 16:9 source
  running a few px under its border.
- **Nothing on the screen is DOM.** The countdown is read from a hidden
  element core already ticks; the socials are drawn into cells, their icons
  tinted from one-colour SVGs.
- **Faster than the smash.** ~1 s against its ~1.9; the comic's pan is 0.98.

## Rejected

- **Text in the DOM, one span per cell.** 7200 elements restyled every frame,
  and no cheap way to draw only what changed.
- **A WebGL ASCII shader** (Acerola's approach) **or three.js's AsciiEffect.**
  Both turn a rendered image into characters; the only image here is the
  flower, which is cheaper rendered straight to cells. A shader over the
  video would need the video in the browser, rejected in the root
  `CLAUDE.md` §3.
- **Pre-rendered frames**, as ghostty.org's ghost is. A fixed loop at a fixed
  size; the live model is one size on START and another on CHAT, and can turn
  at any speed.
- **A glitch on the video itself** (an OBS shader filter). It would distort
  the game, and it is a plugin to install and keep working.
- **A CRT shader over the whole canvas.** Scanlines and bloom are painted
  into each cell instead, so none ever lands on the video.

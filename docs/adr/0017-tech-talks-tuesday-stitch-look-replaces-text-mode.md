# 0017 — Tech Talks Tuesday: the stitch look replaces text mode

- **Date:** 2026-11-03
- **Status:** Superseded by 0018 (2026-11-03)

## Context

[0016](0016-tech-talks-tuesday-glitch-replaces-the-pan.md) built the
overlay as a text-mode screen: 12 × 24 character cells, the CGA's sixteen
colours, VT323, DOS windows, and a sunflower drawn in donut.c's ramp from
scattered points. It was in OBS on 2026-11-02.

The user found it "very low quality" and sent a screen recording of
Rischa's Uniqode branding as the look to aim for, "but not the colours".
Frames pulled from the recording showed what makes it read as high
quality:

- a square grid;
- every cell inside a shape filled, with clean silhouettes;
- three or four tones only, each a glyph and a colour: pale `+` where lit,
  bold `×` in shadow, dots for texture;
- nothing random, so it reads as cross-stitch.

The text-mode build was the opposite on each point: tall cells, a
12-character ramp, gaps where the scattered points missed cells, and a
palette at full saturation.

`study.html` drew the new look in three palettes (night, paper, amber). The
user picked night on 2026-11-03.

## Decision

- **Square 12 px cells, 160 × 90 on the horizontal canvas**
  (`screen.js`), in place of 12 × 24 text cells. A cell is still a glyph,
  a foreground and a background, and a cell with no background is still
  transparent: a window onto an OBS source.
- **The garden is 3D meshes rasterised once per cell centre** (`stitch.js`)
  with a depth buffer, so a silhouette is solid. Each covered cell is lit
  and quantised to four tones; a tone is a stitch and a colour.
- **The palette is night**: a near-black ground, the garden's own hues in
  ramps of four. Paper and amber stay in `STITCH_PALETTES`.
- **Type is IBM Plex Mono** across 1 × 2 or 2 × 4 cells; **big words are
  stitched letters**, a 5 × 7 bitmap with a cross per pixel.
- **Windows are bordered in stitches.** The DOS menu bar, double-line boxes,
  scanlines and bloom are gone.
- **The tulips are 3D too**, a field of three rows, in place of
  hand-drawn character sprites.
- **0016's transition stands as it was**, apart from what it is made of:
  the cells scramble over 300 ms, the holes move at 320 while every cell is
  scrambled, and the next scene comes back from 400 ms, top row first. A
  press before the cut changes the target; a press while stitching in
  scrambles again. Presses never queue. The noise is now loose stitches in
  the palette's colours rather than random characters in the CGA's.

## Consequences

- **Every cam window is exactly 16:9.** On 12 px cells any multiple of
  16 × 9 cells is, so no source runs under a border, as GAME's and END's did
  in text mode.
- **`Chat` is 720 × 996**, up from 984, to fill the new window.
- **Composing a frame costs more:** START 2.8 ms against 0.95 in text mode
  (both in the app's browser), because a field of tulips is rasterised
  every frame as well as the sunflower. In OBS, six switches back to back
  skipped no frames.
- **The look depends on IBM Plex Mono from Google Fonts** for its small
  type. The stitches and stitched letters are drawn as shapes and depend on
  no font.
- **0016's measurements describe the text-mode build.** They are kept there
  as history; the overlay's `CLAUDE.md` carries the current ones.

## Rejected

- **Keeping text mode and only toning down its colours.** The noise was in
  the method — scattered points and a long ramp — not just the palette.
- **The reference's own blue.** The user ruled it out.
- **Paper, the reference's light ground**, and **amber, one phosphor.**
  Shown side by side with night; the user picked night.

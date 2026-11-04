# 0018 — Tech Talks Tuesday: the terminal garden, and a CRT for the switch

- **Date:** 2026-11-03
- **Status:** Palette and garden composition superseded by [0019](0019-tech-talks-tuesday-botanical-palette.md) (2026-11-03); CRT transition and layout remain accepted and built. Supersedes [0017](0017-tech-talks-tuesday-stitch-look-replaces-text-mode.md).

## Context

[0017](0017-tech-talks-tuesday-stitch-look-replaces-text-mode.md) drew the
overlay in stitches: × and + as vector shapes on 12 px cells, a 3D sunflower
and tulips rasterised per cell, a glitch for the switch. The user rejected
it: "doesn't look as beautiful", "use actual ascii characters", and every
screen should have a base, like Money Talks Monday's note.

They then sent a second reference, "AIR" (Llama's spot for Amazon Prime),
and five asks:

1. the switch should be an old CRT TV turning off;
2. header and footer bands, as on Money Talks Monday, with straight edges;
3. a dark olive green terminal ground, or the light pink of a very old
   monitor;
4. artwork and animation like the reference, but with flowers and colours,
   and flowers swaying in a breeze every few seconds rather than rotating;
5. pretty and aesthetic, vintage digital, not boring.

Frames pulled from the recording show the reference's technique: each
shape is filled with a running word and edged in line characters, in one
glowing phosphor colour on dark grey-green glass.

## Decision

- **Real printable ASCII only**, one character to an 8 × 12 px cell
  (`screen.js`), in VT323, drawn bold with a little glow, scanlines on every
  opaque cell, and a blurred `screen`-blended copy for bloom.
- **Shapes are filled with running text and edged in line characters**
  (`ascii.js`): inside, the next letter of `TECH@TALKS@TUESDAY@`; on an edge,
  the line character chosen by Alex Harri's shape matching.
- **The garden is 2D and sways** (`flowers.js`): sunflowers, tulips and
  grass drawn as shapes every frame and converted. A breeze always, and a
  gust every 6–10 s that travels across the garden. The 3D meshes are gone.
- **A base on every screen:** a 72 px header band and a 72 px footer band,
  straight `=` rules on their inner edges; on GAME the cam sits in a notch
  bottom-left, as on Money Talks Monday.
- **Two themes:** dark olive by default, light pink with `?bg=pink`.
- **The switch is a CRT turning off and on** (`crt.js`, in place of
  `camera-pan.js`; nothing in `core/` changes). The overlay's canvas is
  squashed about the middle while glass closes over the video from top and
  bottom; the line shrinks to a dot and fades; the holes and the OBS sources
  move in the dark; then a dot, a line, and the next scene opens. About 1 s.
  A press before the dark retargets; after it, the tube goes off again from
  where it is. Presses never queue. OBS's own transition stays Cut.

## Consequences

- **Every cam window is 16:9 on the grid:** any multiple of 64 × 36 px.
  `Chat` is 624 × 936.
- **Composing a frame costs more on the garden scenes:** about 5.5 ms in the
  app's browser, since the whole garden is converted every frame. In OBS,
  six switches back to back skipped no frames at 60 fps.
- **The video is never squashed**, only covered: a switch shows the glass
  closing over it while the overlay's own art squashes. At the dark moment
  everything is covered, which is what lets the holes move unseen.
- **Two fonts from Google Fonts**, VT323 and Anton, until step 9.
- **Socials are text, not icons**, so the screen stays all ASCII; the icon
  files from the earlier builds are unused.

## Rejected

- **Keeping the stitches with a new palette.** The user asked for real ASCII
  characters.
- **Rotating 3D flowers.** The user asked for flowers in the wind instead.
- **Squashing the video too.** It would mean pushing a transform to every
  source every frame of the switch, for a moment the glass covers anyway.
- **A shader on the whole canvas for the CRT.** Glow and scanlines are drawn
  into the cells, so none lands on the game or the camera.

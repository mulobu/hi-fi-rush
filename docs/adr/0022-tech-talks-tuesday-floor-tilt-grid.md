# 0022 — Tech Talks Tuesday: the grid tilts back into a floor and cuts on a line

- **Date:** 2026-11-03
- **Status:** Built; browser and OBS verified. Supersedes [0021](0021-tech-talks-tuesday-shared-grid-surface.md)'s surface, timing and colouring; its shared-body build stays.

## Context

The user, having merged the old and new styles into the pink fusion page
([0020](0020-tech-talks-tuesday-pink-fusion.md)), asked to fix the
transition "or do it like this video": a recording of a "3D grid
transitions" pack. Frames pulled from it at 10 fps show what 0021's surface
lacked:

- the picture becomes a wire mesh lifted by its own brightness, with dark
  gaps between the wires and black around it;
- the mesh tilts back into a floor in about 0.2 s, drifts, then goes edge-on
  as a glowing line;
- the next picture rises out of that line already tilted, with the same
  relief, drifts, and snaps flat.

0021's surface was a sine fold with a −0.16 rad roll that squashed to a
ribbon: no perspective, no relief from the picture, and the picture kept
showing between the wires.

## Decision

`grid-surface.shader` is rewritten as a ray-marched heightfield:

- **Geometry.** The frame is a plane seen from a camera 5 units back, which
  fills the screen when flat. It rotates about its horizontal axis (top
  away) and is pushed back by 0.85 × sin(tilt), so its near edge stays about
  full width. Tilt runs 0 → about 35° fast, a slow drift, then to 88.8°
  edge-on; holds through the cut; back to about 33°, drifts, and settles
  flat. It never reaches 90°, so the camera stays above the floor.
- **Relief.** One vertex per grid intersection, raised by the luminance
  under it (`Relief` × luma^1.4, 0.18 by default), bilinear in between: a
  displaced mesh, as in 3D software. The sheet has no thickness, so a ray
  only hits it by crossing from above, and a raised edge floats instead of
  standing on a wall.
- **Waves.** Two travelling ripples across the sheet on top of the relief
  (`Wave`, 0.16 by default), fading in and out with it. Added the same
  evening: the first build, relief alone, tipped back as one flat
  rectangle on the pink pages, which have almost no light and dark to
  raise. The user's words: "we need wave and flip … but on OBS it looks
  just square". The waves also ripple the edge-on line.
- **Look.** 96 columns. Wires a third of a cell wide in the picture's own
  colour, a little brightened; gaps at 12% of it; dark plum around the
  plane. A pink-white glow line at the edge-on moment.
- **Timing.** 1.8 s (was 1.6). The overlay switches layout at 47%, inside
  the line, which leaves about 130 ms before the next scene rises. `CUT` is
  set in both `fusion.js` and `tools/build-tuesday-grid.py`.
- **Hosts.** `sampleScene` is now a single-level sample in both hosts
  (`SampleLevel` / `textureLod`), because the march samples inside a loop
  where gradients are not allowed. The browser study uses OBS's convention:
  y = 0 at the top for both screen and texture.

## Consequences

- **The plugin reads the shader file only when the filter is created.**
  Changing `shader_file_name` over the websocket does not recompile, and the
  filter's Reload button is out of reach (`PressInputPropertiesButton` takes
  inputs only). After editing, the filter is recreated with the same
  settings, at index 0, then disabled: `CreateSourceFilter` makes it enabled.
- **OBS samples past the picture as transparent black;** the browser clamps.
  Mesh vertices are clamped a pixel inside, or the rim drops to the floor
  and stands up as a wall in OBS only.
- **Light scenes read as a pale grid.** START, BRB and END are mostly light
  pink, so they rise as one plane with the text carved into it, much as the
  reference's sky does. Colour shows where the picture has it: the flowers
  and the game.
- **Cost.** Up to 42 height lookups of 4 samples per pixel, only while the
  filter is on. Six switches back to back: **0 of 865 render frames
  skipped** at 60 fps without waves, **0 of 866** with them and Valorant
  running in `Game`.
- **Verified in OBS 33.0.1 / obs-shaderfilter 2.6.1:** compiled with no
  error in the log; a GAME → START switch captured off program (line at
  0.84–1.0 s, START up by 1.1 s, flat by 1.85 s); punch sets read back
  unchanged on all six scenes; nothing was live.
- **Seen with a running game:** with waves, GAME → START captured off
  program with Valorant in `Game`; the game's picture ripples on the mesh,
  the line ripples, START comes up waving. Not yet seen on a stream.

## Rejected

- **Keeping 0021's fold and ribbon with more tilt.** The reference's depth
  comes from the picture's own brightness and from perspective, and neither
  can be added to a 2D warp.
- **A real bloom pass.** It needs neighbouring pixels of the result, which
  a single-pass filter does not have; the glow line is drawn analytically.
- **Walls under raised edges.** Treating everything below the surface as
  solid stood every bright edge up on a white wall; the reference's mesh has
  no skirt.

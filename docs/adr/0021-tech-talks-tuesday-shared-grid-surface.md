# 0021 — Tech Talks Tuesday: a shared, more expressive grid surface

- **Date:** 2026-11-03
- **Status:** Surface, timing and colouring superseded by [0022](0022-tech-talks-tuesday-floor-tilt-grid.md) (2026-11-03); the shared body and its build remain. Refines 0020's transition.

## Context

The user requested a transition closer to their screen recording. The first
working shader became a pale regular grid too quickly, hid much of the
picture, and nearly disappeared at the midpoint. Browser GLSL and OBS HLSL
were maintained separately, making visual drift possible.

## Decision

Use `grid-surface.shader` as the shared rendering body. Run
`python tools/build-tuesday-grid.py` to produce `grid-bend.shader` for OBS and
`grid-preview.frag` for the browser. Edit the shared body rather than the
generated files. The preview loads the GLSL shader over the local web server.

Increase the mesh from 96 to 144 columns. Add a travelling raised fold,
secondary ripples and a slight diagonal tilt. Retain a dim surface image
between the wires, preserve its colours, and soften the wire edges. At the
midpoint keep a narrow coloured ribbon rather than a nearly empty black
screen. Neutralise the image contribution in that ribbon to conceal the
layout switch. Keep the existing 1.6-second timing and source-settling hold.

This is a reference-inspired procedural surface, not a reconstruction of the
recording's geometry or depth.

## Verification

- Browser shader compiled without console errors; inspected the bent image
  at 22% with retained game imagery and fine coloured mesh.
- Native shader compiled successfully in OBS 33.0.1 with obs-shaderfilter 2.6.1.
- Captured START → GAME through the bend, ribbon, reveal and completed frame.
- Filter readbacks enabled during the transition and disabled by 1.9 s.
- Six-scene test, including captures: **0 skipped render frames out of 967**.
  Original scene restored; streaming and recording checked inactive first.
- JS syntax and whitespace checks passed. No commits.

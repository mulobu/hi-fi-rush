# 0020 — Tech Talks Tuesday: pink fusion and video grid deformation

- **Date:** 2026-11-03
- **Status:** Built; WebGL and native OBS transitions verified on 2026-11-03. Pink palette superseded by [0023](0023-tech-talks-tuesday-phosphor-palette.md) (2026-11-03); layout, type and flowers stand.

## Context

The user rejected the muted botanical revision and clarified that only the
flowers should be ASCII. The surrounding design should be sleek and modern,
on pink. Their recording shows actual video bending into a coloured grid,
which a decorative browser overlay cannot reproduce over OBS video.

## Decision

Use modern DOM typography and pink/plum framing, with the existing ASCII
flower engine on a transparent canvas. Retain the six source rectangles.
Use vivid gold sunflowers, saturated pink tulips and brighter teal foliage.

Prepare a GPU shader on the COMIC composite, so the actual live image can
deform. Collapse to a thin ribbon, change layouts while collapsed, then
expand. The browser driver toggles a native shader filter, rather than
streaming pixels or shader progress over the websocket. GPU timing returns
to an unmodified image even if the browser driver stops.

Official plugin: [obs-shaderfilter](https://github.com/exeldro/obs-shaderfilter),
version 2.6.1. Downloaded Windows ZIP SHA256:
`bdb5af0c8d6afb9b488a0dd4235a26786c221fb01d9082786e51aceb0deae37d`.
Installed to ProgramData. `Botanical Grid` is attached to COMIC and compiled
successfully after replacing the HLSL-reserved identifier `line`.

Provide a no-library WebGL2 browser study, with captured scene textures,
playback, manual progress, and optional local video. The study makes no OBS
connection. It does not substitute for native shader verification.

## Verification

- Six fusion layouts captured in inactive OBS: 0 skipped render frames of 761.
- Flower brightening saved after those captures; latest colours still need OBS refresh.
- Browser GLSL shader compiled, paused deformation inspected at 22%, full
  1.6-second playback reached 100%, no console errors.
- Native filter now compiled and verified: enabled at 0.22–1.15 s during
  START → GAME and disabled by 1.9 s. Captured the deformed composite.
- Added an early projected-footprint rejection to avoid tracing empty pixels.
  Final six-scene no-capture run: **0 skipped render frames out of 957**.
  Original scene restored. Latest brightened flowers captured in OBS.
- Restarted the stopped localhost server and added automatic replay to the
  browser demo so it no longer opens as a motionless image awaiting Play.

## Consequences

Browser playback demonstrates the real textured deformation with captured
images or local video. The OBS transition now bends the actual live composite;
without the filter the page intentionally cuts instead of pretending to bend video.
The retired CRT code remains on disk but is no longer loaded. No commits.

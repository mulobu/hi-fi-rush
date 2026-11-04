# Tech Talks Tuesday overlay

The Tuesday show's overlay: a garden on an old terminal. Real ASCII on a
dark olive CRT (or light pink, `?bg=pink`), with header and footer bands on
every screen. Flowers and titles are filled with running text and edged in
line characters, and the flowers sway in a breeze that gusts every few
seconds. A scene switch is a CRT turning off and on. The horizontal page is
built and in OBS as the `Tech Talks Tuesday` collection, and the vertical
page on its vertical canvas (VCOMIC).

| File | What it is |
| --- | --- |
| [CLAUDE.md](CLAUDE.md) | Concept, references, art direction, layout, the switch — this overlay's own |
| [overlay.html](overlay.html) | The live overlay, 1920×1080. `Overlay` points here |
| [vertical.html](vertical.html) | The vertical overlay, 1080×1920. `OverlayV` points here |
| [fusion.js](fusion.js) | The design both pages share: copy, surface, the 3D grid transition, the flower loop |
| [palette.css](palette.css) | The colours, for both pages |
| [vertical.css](vertical.css) | The vertical page's layout; `tech.css` is the horizontal's |
| [screen.js](screen.js) | The terminal screen: 8 × 12 cells, VT323, glow, scanlines |
| [ascii.js](ascii.js) | Pictures into ASCII: text fill inside, line characters on edges |
| [flowers.js](flowers.js) | The themes, the wind, the sunflower, tulips and grass |
| [crt.js](crt.js) | The switch, loaded in place of `core/camera-pan.js` |
| [tech.css](tech.css) | The holes, the bloom, the vignette, the CRT glass, the HUD |
| [chat.css](chat.css) | Styles the chat embed. `obs-setup.py` puts it on `Chat` |
| [overlay.json](overlay.json) | Name and scene collection, `Tech Talks Tuesday`. Chat 624 × 936. No mascot |

The latest palette uses sage foliage, parchment type, honey sunflowers and
dusty rose tulips, with reduced glow. The garden has varied heights, buds,
veined leaves, daisies and drifting pollen. Research and verification are in
[ADR 0019](../../docs/adr/0019-tech-talks-tuesday-botanical-palette.md).

Preview without OBS: serve the repo root (`python -m http.server 8765`) and
open `/overlays/tech-talks-tuesday/overlay.html?preview=start&sfx=0`.
Use `preview=brb`, `end`, `game`, `cam` or `chat` for the other scenes;
append `&bg=pink` for the pink monitor or `&debug=1` for keys 1–6.
The vertical page is `vertical.html?preview=start` (there `?scene=` names
the OBS scene).
Standalone preview does not connect to OBS or reposition its sources.

2026-11-03: all six olive scenes and pink START captured directly from OBS;
0 skipped render frames out of 766 during the olive sweep. Camera and game
devices supplied no frames, so live video inside their cutouts remains unverified.

Setting up a machine, starting a stream, chat TTS and every tool are shared by
all overlays and documented in the [root README](../../README.md).

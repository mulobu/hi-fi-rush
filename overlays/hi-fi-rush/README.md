# Hi-Fi Rush overlay

Hi-Fi Rush inspired. The whole stream is one comic page; each OBS scene is one
panel, and switching scenes pans the camera across the page.

| File | What it is |
| --- | --- |
| [CLAUDE.md](CLAUDE.md) | Concept, art direction, panel layout — this overlay's own |
| [overlay.html](overlay.html) | The live overlay, 1920×1080. `Overlay` points here |
| [vertical.html](vertical.html) | Its own 4320×7680 page for the vertical canvas. `OverlayV` points here |
| [chat.css](chat.css) | Styles the chat embed to sit on the chat panel's art. `obs-setup.py` puts it on `Chat` |
| [mascot/placement.json](mascot/placement.json) | Where the deer sits, per scene, in canvas pixels |
| [mascot/placement-vertical.json](mascot/placement-vertical.json) | The same, in the vertical canvas's pixels |
| [obs/scenes.json](obs/scenes.json) | This overlay's scene collection, exported with credentials stripped |
| [assets/socials/](assets/socials/) | The paper cut-out platform icons |
| [mockup.html](mockup.html) | Standalone layout mockup |

The mascot is the shared deer set, `mascot/sets/deer/` at the repo root.

Setting up a machine, starting a stream, chat TTS, the mascot and every tool
are shared by all overlays and documented in the [root README](../../README.md).

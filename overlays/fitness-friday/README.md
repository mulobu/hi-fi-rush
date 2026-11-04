# Fitness Friday overlay

The Friday show's overlay is a royal blue drafting sheet with HUGE type and
yellow anatomy blueprints, one per scene. A scene switch is a word sting:
slabs sweep across, and the next scene's words slam in one at a time,
filling the frame. Both pages are in OBS as the `Fitness Friday`
collection. The design is in [CLAUDE.md](CLAUDE.md), and the decisions in
[ADR 0027](../../docs/adr/0027-fitness-friday-blueprint-sheet-and-word-sting.md)
and [ADR 0028](../../docs/adr/0028-heart-rate-from-our-own-watch-app.md)
(the live heart rate).

| File | What it is |
| --- | --- |
| [overlay.html](overlay.html) | The overlay, 1920×1080. `Overlay` points here |
| [vertical.html](vertical.html) | The vertical overlay, 1080×1920. `OverlayV` points here |
| [anatomy.js](anatomy.js) | The body, brain, heart, lungs and hand, drawn in code; `renderPlate()` |
| [sheet.js](sheet.js) | The sheet, its builders, the sting and the live heart rate, loaded in place of `core/camera-pan.js` |
| [blueprint.css](blueprint.css) | The palette and every shared style |
| [overlay.json](overlay.json) | Name and scene collection, `Fitness Friday`. Chat 560 × 952. No mascot. `"heart": true` starts the heart bridge |
| [chat.css](chat.css) | Styles the chat embed; still the template's |

Run the show:

```bash
py -3 start.py --overlay fitness-friday
```

This starts the heart bridge with the chat bridge. On its first run,
Windows asks whether Python may use the network: allow it on Private
networks, or the watch cannot reach it.

Preview without OBS: serve the repo root (`python -m http.server 8765`) and
open `/overlays/fitness-friday/overlay.html?scene=START`, or
`vertical.html?preview=START`. Click the scene buttons, or press 1–6, to
play the sting. To see a live heart rate without the watch, run
`py -3 heart/heart-bridge.py --host 127.0.0.1 --fake`.

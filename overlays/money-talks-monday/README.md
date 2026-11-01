# Money Talks Monday overlay

The Monday show's overlay, themed on an Indian ₹2000 note. The frame is the
two halves of one banknote. A scene switch slams them together into one whole
note and spins a Gandhi coin in its centre. Both pages are built and in OBS.

| File | What it is |
| --- | --- |
| [CLAUDE.md](CLAUDE.md) | Concept, art direction, layout, the transition — this overlay's own |
| [overlay.html](overlay.html) | The live overlay, 1920×1080. `Overlay` points here |
| [vertical.html](vertical.html) | The vertical canvas's page, 1080×1920. `OverlayV` points here |
| [smash.js](smash.js) | The transition, for both pages, loaded in place of `core/camera-pan.js` |
| [money.css](money.css) | What both pages draw alike: the frame, the coin, plates, socials |
| [art.js](art.js) | Plates, socials, the coin's face and where the rosette lands, for both pages |
| [chat.css](chat.css) | Styles the chat embed. `obs-setup.py` puts it on `Chat` |
| [overlay.json](overlay.json) | Name and scene collection, `Money Talks Monday`. No mascot |
| `assets/` | The note, its portrait version, the Gandhi coin face, and the socials icons |

Setting up a machine, starting a stream, chat TTS and every tool are shared by
all overlays and documented in the [root README](../../README.md).

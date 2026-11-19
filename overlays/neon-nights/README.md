# Neon Nights overlay

1984 Miami at sunset, for the GTA VI stream — a slatted sun over a neon
grid, palms in silhouette, art deco towers, chrome italic type and an 80s
crime-game HUD. A scene switch is the cruise: the sunset rises over the
frame, the next scene's name slams in as chrome a word at a time, and the
new scene lands under a tape tear. The look is the only thing borrowed:
nothing on screen names a game, a studio, a city or a show. The design is
in [CLAUDE.md](CLAUDE.md) and the decisions in
[ADR 0033](../../docs/adr/0033-neon-nights-sunset-page-and-the-cruise.md).

| File | What it is |
| --- | --- |
| [overlay.html](overlay.html) | The overlay, 1920×1080. `Overlay` points here |
| [vertical.html](vertical.html) | The vertical overlay, 1080×1920. `OverlayV` points here |
| [art.js](art.js) | The sun, palms, skyline, car, radar, stars and grid, drawn in code |
| [cruise.js](cruise.js) | The page, its builders, the cruise and the clock, loaded in place of `core/camera-pan.js` |
| [neon.css](neon.css) | The palette and every shared style |
| [overlay.json](overlay.json) | Name and scene collection, `Neon Nights`. Chat 440 × 930. No mascot |
| [chat.css](chat.css) | Styles the chat embed |

Run the show:

```bash
python3 start.py --overlay neon-nights
```

Preview without OBS: serve the repo root and open the pages.

```bash
python3 -m http.server 8765
```

Then `/overlays/neon-nights/overlay.html?scene=START`, or
`vertical.html?preview=START`. Click the scene buttons, or press 1–6, to
play the cruise; add `&clean` to hide the button bar, `&debug=1` for the
HUD.

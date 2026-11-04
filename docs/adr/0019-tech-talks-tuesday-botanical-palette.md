# 0019 — Tech Talks Tuesday: a restrained botanical palette

- **Date:** 2026-11-03
- **Status:** Built, awaiting user visual review. Supersedes 0018's palette and garden composition only; its CRT transition and layout remain in force.

## Context

The user rejected the terminal garden's colour combinations and generic
flowers and asked for research before another redraw. The interrupted session
had saved botanical drawing functions and clustered arrangements, but had not
completed verification or updated its documentation.

## References and interpretation

- [Nostalgia, WildLeoKnight](https://lospec.com/palette-list/nostalgia): a four-colour olive ramp.
- [Ice Cream GB, Kerrie Lake](https://lospec.com/palette-list/ice-cream-gb): cream, peach, coral and plum in four colours.
- [Rustic GB, Kerrie Lake](https://lospec.com/palette-list/rustic-gb) and [Mist GB, Kerrie Lake](https://lospec.com/palette-list/mist-gb): references for the alternate pink/plum and teal direction.
- [Alex Harri, ASCII characters are not pixels](https://alexharri.com/blog/ascii-rendering): glyph shape and edge contrast matter to the drawing's silhouette.
- [Philadelphia Museum of Art, Sunflowers](https://www.philamuseum.org/objects/59202): varied arrangements and individual flower character, rather than identical repeated heads.

These sources inform the design; they do not prescribe our exact colours,
composition or a universal colour percentage. Our palette is an adaptation,
not an exact reproduction of any named Lospec palette.

## Decision

Use an olive glass `#1c251d`, darker bands `#141c16`, parchment text
`#e5dfc6`, sage foliage, honey sunflower petals and dusty rose tulips.
Give sunflowers their own petal ramp, so they stay recognisable rather than
sharing pink tulip colours. Reduce olive glow from 3 px to 1.2 px, bloom
from 0.55 to 0.18, and scanline darkness from 0.28 to 0.13.

Keep the saved asymmetric botanical arrangement: two sunflowers of different
sizes, tulips in clustered heights and opening stages, leaf veins, grass,
daisies and pollen. Use 17 front sunflower petals with wider cuts, so their
separation survives the ASCII grid. Daisies tilt with the wind; they do not
rotate over time. Fill letters stay dimmer than contour characters.

Keep straight bands, video cutouts, text-filled ASCII and the CRT switch.
Add `?preview=SCENE` for an isolated browser review that never connects to OBS.

## Verification and limits

On 2026-11-03, confirmed OBS streaming and recording inactive, refreshed
Overlay, captured START, BRB, END, GAME, CAM and CHAT at 1920 × 1080, and
restored START. No skipped render frames out of 766 during the sweep.
Observed source positions agree with the authored layouts; Chat is 624 × 936
at (1296,72) on CHAT. Cam and Game reported zero source dimensions and
rendered black, so actual video crop and live device behaviour were not verified.
This run does not replace the earlier CRT timing measurement.

Temporarily applied pink, captured START in OBS, and restored the complete
original Overlay settings. Pink has plum text, bronze sunflowers and teal
foliage. Only pink START was checked in this pass.

Local captures and raw transform report: gitignored `assets/ttt-review/`.
The in-app browser's pre-existing port 8766 served an older copy; its images
were excluded from final verification. OBS screenshots show the current files.

Still open: user art review, microphone, Restream chat styling, profile,
vertical page, and live camera/game verification. Nothing committed.

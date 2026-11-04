# CLAUDE.md — Tech Talks Tuesday

## Vertical page, 2026-11-04

[ADR 0024](../../docs/adr/0024-tech-talks-tuesday-vertical-page.md).
`vertical.html` is the fusion design at 1080 × 1920 on VCOMIC.

**The engine is shared.**
- **`fusion.js`** holds the copy, the surface, `GridFX` and the flower loop
  for both pages.
- **Each page** sets `CANVAS_W` and `CANVAS_H` before it, then `PANELS`,
  `GARDENS` and `GRID_TARGET()` after it.
- **Styles.** `palette.css` holds the colours for both pages; `tech.css`
  is the horizontal layout and `vertical.css` the vertical one.

**The layout.**
- **Safe area.** Type stays inside SAFE_* (x up to 916, y 140 to 1596).
- **Bands.** The header row is at 140–212. The footer starts at 1440:
  socials, then brand and scene name.
- **Windows.** Face on top, every cam 16:9, and Chat 468 × 702 (624:936).
- **Flowers** never reach a window.

| Scene | Vertical holes, read back off OBS |
| --- | --- |
| GAME | Game 0,762 1080 × 608 + Cam 48,282 768 × 432 |
| CAM | Cam 0,588 1080 × 608 |
| CHAT | Cam 48,236 768 × 432 + Chat 448,700 468 × 702 |
| START, BRB | None |
| END | Cam 48,642 832 × 468 |

**Two transition filters now.**
- **VCOMIC** has its own `Botanical Grid`, index 0, disabled at rest, with
  `Grid_Columns` 54 (20 px cells, as 96 gives on 1920).
- **It answers only by `sourceUuid`.** A name lookup fails, as for every
  vertical scene.
- **Setup owns both** ([ADR 0025](../../docs/adr/0025-setup-owns-the-transition-filters.md)),
  from `overlay.json`'s `transition`: it creates missing ones off at index 0,
  and recreates one that points at another file.
- **After a shader edit:** `python tools/build-tuesday-grid.py`, then
  `python tools/obs-setup.py --vertical --recompile`. No page refresh: a page
  without its filter cuts and looks again every 5 s.

**Preview:** `vertical.html?preview=GAME`. `?scene=` is the OBS scene name
there (`core/vertical.js`).

**Verified 2026-11-04** with live camera, game and chat:
- All six vertical punch sets were read back.
- The vertical transition was captured at fixed points.
- Both canvases transitioning together: six switches, **0 of 866** frames
  skipped.
- The horizontal page was unchanged by the split, element for element in
  the browser and hole for hole in OBS.

Not yet seen on a stream.

## Current handoff — fusion page in phosphor, 2026-11-03

**Palette:** [ADR 0023](../../docs/adr/0023-tech-talks-tuesday-phosphor-palette.md).
Phosphor replaced pink at the user's pick from three rendered options:
green-black ground, terminal green `#4ade80`, amber sunflowers, cyan tulips.
`palette.css` (in `tech.css` until ADR 0024) holds the colours as `:root` variables (phosphor by default);
`flowers.js` `THEMES` holds each palette's flower ramps and, under `css`, its
page colours, which `fusion.js` applies. `?bg=pink|lime|midnight` previews
the others. The transition's glow and ground are `GLOW`, `GLOW_CORE` and
`GROUND` in `grid-surface.shader`.

**Current transition:** [ADR 0022](../../docs/adr/0022-tech-talks-tuesday-floor-tilt-grid.md),
after the user's "3D grid transitions" reference. The frame becomes a 96-column
wire mesh lifted by its own brightness and rippled by travelling waves
(`Wave`), tilts back into a floor, goes edge-on
as a glowing line (the layout switches there, at 47% of 1.8 s), and the next
scene rises out of the line and settles flat. One shared body in
`grid-surface.shader`; regenerate with `python tools/build-tuesday-grid.py`.

**After editing the shader, run setup with `--recompile`** (ADR 0025).
obs-shaderfilter reads the file only when `Botanical Grid` is created;
setting `shader_file_name` again does not recompile. `--recompile` recreates
the filter on COMIC and VCOMIC with its settings. A compile error shows in
the OBS log as `[obs-shaderfilter] Unable to create effect`.

Verified 2026-11-03: compiled in OBS, GAME → START captured off program
with Valorant running, punch sets unchanged on all six scenes, six switches
**0 of 866 frames skipped**. Not yet seen on a stream. The notes below on 0020 and
0021 describe the earlier surface.

This section supersedes the terminal-only design described below. The user
requested a fusion of old and new: pink framing, sleek modern typography,
ASCII flowers only, and an actual video-bending grid transition.
`overlay.html`, `tech.css` and `fusion.js` implement that design. Pink was the
default until ADR 0023. Flowers now use vivid gold, saturated pink and brighter teal greens.
`crt.js` is retained but is no longer loaded.

`grid-bend.shader` is the proposed COMIC composite filter, controlled by
`GridFX` in `fusion.js`. It requires obs-shaderfilter; the official 2.6.1
Windows release was installed under `C:/ProgramData/obs-studio/plugins/obs-shaderfilter`.
**Activation completed:** `Botanical Grid` is now attached to COMIC. Fixed
the HLSL-reserved identifier `line`, compiled in OBS, and refreshed Overlay.
Readbacks show the filter enabled at 0.22–1.15 s and disabled at 1.9 s.
Captured the actual deformed composite during START → GAME. An early screen
footprint rejection avoids tracing empty pixels; the final no-screenshot
six-scene run skipped **0 of 957 render frames**. Original scene restored.

`transition-preview.html` and `transition-preview.js` are a standalone WebGL2
study using the equivalent projection and timing. Verified in the browser:
shader compiled, bent captured image inspected at 22%, full playback reached
100%, no console errors. This initially proved only the browser study; native
verification is now recorded above. It uses captured scene images; local
video can be selected without upload. Auto replay now starts on load. The
localhost server on 8766 was restarted after it stopped, bound to loopback.

Earlier fusion renders: all six scenes captured in OBS, 0 skipped render
frames out of 761. Brightened flowers now captured in `bright-start.png`.
Transition captures and final metrics: `assets/ttt-review/grid-*.png` and
`grid-report.json` (gitignored).
Before-fusion backup: gitignored `assets/ttt-review/before-fusion.zip`.
See [ADR 0020](../../docs/adr/0020-tech-talks-tuesday-pink-fusion.md).

---

The Tuesday show's overlay: a garden on an old terminal. One grid of 8 × 12
px ASCII cells on a dark olive glass (or light pink, `?bg=pink`), with a
header and a footer band on every screen as on Money Talks Monday. Flowers
and titles are filled with running text and edged in line characters, in
phosphor colours that glow; the flowers sway in a breeze that gusts every
few seconds. A scene switch is an old CRT turning off and on.

This file is what is this overlay's own: its concept, art direction and
layout. How it reaches OBS — scenes, sources, the punch pipeline, audio, the
deck, the vertical canvas, reliability — is shared by every overlay and
lives in the [root `CLAUDE.md`](../../CLAUDE.md), with the working agreement.
The page contract is [core/README.md](../../core/README.md). Decisions go in
[docs/adr/](../../docs/adr/README.md).

**Status, 2026-11-03:** the horizontal page is in OBS as the `Tech Talks
Tuesday` collection. The first terminal garden was rejected for its colours
and generic flowers. The botanical revision is now built and awaiting user
review: sage, parchment, honey and dusty rose, reduced glow, clustered tulips,
two sunflowers, veined leaves, daisies and pollen. See
[ADR 0019](../../docs/adr/0019-tech-talks-tuesday-botanical-palette.md).

Latest checks: six olive scenes captured directly from OBS, 0 skipped render
frames out of 766; pink START captured in OBS, original olive settings and
START restored. Cam and Game currently report zero source dimensions and
show black, so this pass verifies source positions and drawn borders, not
live video crop. Captures and report are in gitignored `assets/ttt-review/`.
Earlier checks below describe the previous revision unless stated otherwise.

- **Punch sets read back off OBS:** all six as authored (§3).
- **The CRT switch, off OBS's program during GAME → START:** squashing at
  90–200 ms, the line at 290, the dot at 400, dark at 480–600 (the cut),
  the line growing at 700–820, START open by 1000.
- **Six switches back to back: 0 of 541 frames skipped**, OBS at 60 fps.
- **Not built:** the profile, the Tuesday entry in `shows.json`. (The
  vertical page was built on 2026-11-04; see the top.)
- **Not measured:** the sounds' level in the mix, the browser process's CPU,
  pink scenes other than START, and live video in the current revision.

**Mic, 2026-11-04:** copied from Hi-Fi Rush, so it is the same device and
the same `NV DENOISE`, `EQ`, `COMPRESS` and `LIMIT`. Setup then added `DUCK` on
`Game` and `Browser`, matching Hi-Fi Rush's. As copied, `NV DENOISE` is at 1.0
with VAD on, not the 0.7 / VAD off the root CLAUDE.md records.

**Open in the collection:** `chat.css` does not reach the Restream embed,
as on Money Talks Monday; OBS's default `Scene` is still in it, empty.

**How it got here.** Three looks in two days, each rejected for a reason
worth keeping:

1. **Text mode** (2026-11-02, [ADR 0016](../../docs/adr/0016-tech-talks-tuesday-glitch-replaces-the-pan.md)):
   CGA colours, DOS windows, a 3D sunflower from scattered points. "Very low
   quality."
2. **Stitches** (2026-11-03 morning, [ADR 0017](../../docs/adr/0017-tech-talks-tuesday-stitch-look-replaces-text-mode.md)):
   × and + drawn as shapes, after Rischa's Uniqode branding. "Doesn't look
   as beautiful", "use actual ascii characters", and every screen should
   have a base, like Monday's note.
3. **This one** (2026-11-03, [ADR 0018](../../docs/adr/0018-tech-talks-tuesday-terminal-garden.md)),
   from the user's second reference, "AIR" (Llama's spot for Amazon Prime),
   and five asks: a CRT turning off for the switch; straight header and
   footer bands; a dark olive terminal ground, or a very old monitor's
   light pink; artwork like the reference but with flowers and colours,
   swaying in a breeze rather than rotating; pretty, vintage digital.

**How the collection was built.** Setup created it
(`--overlay tech-talks-tuesday --no-profiles`); the settings of `Game`,
`Cam`, `Browser` and `Chat`'s url were copied from Money Talks Monday's
over the websocket. Setup sets `Chat`'s size from `overlay.json` on every
run; the `Overlay` source is reloaded with its own refresh button
(`PressInputPropertiesButton`, `refreshnocache`) after the files change.

**Files.**

| File | What |
| --- | --- |
| `screen.js` | The terminal screen: 8 × 12 cells, VT323 drawn bold with a little glow and scanlines, 2 × 2 labels, the atlas renderer |
| `ascii.js` | Pictures into ASCII: text fill inside, line characters on edges (Alex Harri's shape matching), and stamps for titles |
| `flowers.js` | The themes, the wind, and the sunflower, tulips and grass |
| `crt.js` | The switch, in place of `core/camera-pan.js` |
| `overlay.html` | The bands, the windows, `PANELS`, and what each scene draws (`SCENES`) |
| `tech.css` | The page of holes, the bloom, the vignette, the CRT glass and beam, the HUD |
| `chat.css` | Chat on the olive ground |

---

## 1. Core concept

**One terminal screen.** The overlay is a canvas of 8 × 12 px cells, 240 ×
90 of them, exactly the 1920 × 1080 canvas. A cell is one printable ASCII
character with a foreground and a background colour; a cell with no
background is transparent, and that is where an OBS source shows.

**A base on every screen**, as Money Talks Monday's note is: a header band
and a footer band, 72 px each, their inner edges straight rules of `=`.
On GAME, CAM and CHAT the video sits between them; on START, BRB and END the
garden fills the space between.

**The garden** is drawn in 2D and converted to ASCII every frame: two
sunflowers of different sizes on closed scenes, clusters of tulips in varied
heights and opening stages, veined leaves, daisies, grass and drifting pollen.
A quiet meadow replaces the repeated footer tulips. CHAT has a low botanical
strip. Nothing rotates: everything sways, with a travelling gust every few seconds.

## 2. Art direction

### References

| Reference | What it gives this overlay |
| --- | --- |
| "AIR", Llama, for Amazon Prime (Pinterest; the user's recording of 2026-11-03) | **The look.** Shapes filled with a running word (`@PRIME@PRIME`) and edged in `/ \ | - _ +`; one glowing phosphor colour on dark grey-green glass; the shapes move |
| [Alex Harri, "ASCII characters are not pixels"](https://alexharri.com/blog/ascii-rendering) (2026) | The edge characters: six staggered sampling circles per cell matched against each character's own, sharpened against ten circles outside the cell |
| [Joan Stark (jgs)](https://en.wikipedia.org/wiki/Joan_Stark), [asciiart.eu](https://www.asciiart.eu/plants/flowers) | The edge vocabulary: punctuation, almost no letters |
| [Xu, Zhang, Wong, Structure-based ASCII Art](https://history.siggraph.org/?p=105594) (SIGGRAPH 2010) | Good ASCII follows structure, not tone; hence line characters on every edge |
| Money Talks Monday | The base on every screen; the GAME cam in a notch bottom-left |
| An old CRT switching off | The switch |

### Themes

`THEMES` in `flowers.js`; `?bg=pink` picks the second.

| | Olive (default) | Pink |
| --- | --- | --- |
| Ground / bands | `#1c251d` / `#141c16` | `#f4d2c6` / `#ebbcad` |
| Rules, text | `#83947a`, `#e5dfc6`, dim `#93a087` | `#764462`, `#2c2137`, dim `#a96868` |
| Accent | `#e8c985` | `#764462` |
| Sunflower petals | honey: `#f0dca0` to `#74594a` | bronze: `#a97039` to `#573344` |
| Seed detail | `#b99a69` | `#2c2137` |
| Greens | sage: `#bdc6a4` to `#40553e` | teal: `#5ab9a8` to `#163f48` |
| Tulips | cream, dusty rose, muted plum | peach, coral, muted plum |
| Glow, scanlines, bloom | 1.2 px, 13%, 0.18 | none, 4%, none |

These custom ramps adapt Lospec's Nostalgia, Ice Cream GB, Rustic GB and
Mist GB references; they are not copies. Each ramp has four tones, with
depth darkening back flowers. Fill characters are dimmed to 80% before
colour quantisation so the edges read first. Research links are in ADR 0019.

### Type

- **VT323**, the DEC VT320's face, one character a cell, drawn bold (a hair
  of stroke) with a little phosphor glow. Labels that must read at a glance
  are set across 2 × 2 cells.
- **Titles in Anton**, drawn large and converted to text-filled ASCII once
  (`stamp()`). Their cap tops sit at the middle of a cell row, so each
  letter's top is an edge of `_` and `.`: on a row boundary the flat tops
  filled a whole row with letters and read as a stray line.
- Both from Google Fonts until step 9 self-hosts them.

### The ASCII

`ascii.js`, on a source canvas at 2 × 2 px samples:

- **A cell wholly inside a shape** (all six circles at least 0.8 covered)
  takes the next letter of the running wall `TECH@TALKS@TUESDAY@`, offset 7
  a row so the words do not stack. As a flower sways it moves over the wall,
  as in the reference.
- **A cell on an edge** takes the line character from ` .,'`-_~^/\|()<>[]+=:;!`
  whose six ink fractions are nearest the cell's, after the article's
  directional (exponent 2.2) and global (1.4) contrast.
- **Colour** is the covered samples' average, in 16 steps a channel.

### The CRT

- **Glow:** baked into each character, plus a half-size copy of the screen
  blurred 5 px and laid over with `screen` (`#bloom`).
- **Scanlines** on every opaque cell, so none ever lands on video.
- **A vignette** darkens the corners on START, BRB and END only, never over
  the game or the camera.

### The wind

`wind(t, x)` in `flowers.js`: a light breeze always, and a gust every 6–10 s
(7.5 s apart, jittered) that rises in 0.7 s, dies over about 2 s, and runs
left to right at 900 px/s, so it visibly travels through the garden. Stems
bend with it (tulips more than the sunflower), heads tilt with the stem's
tip, leaves lift, and sunflower petals flutter while a gust lasts.

### Socials, words, sound

- **Socials** in the header, each platform's name small and dim, the handle
  in 2 × 2 type. Text, not icons: the overlay is all ASCII.
- **No "SEE YOU NEXT TUESDAY"**: its initials spell an insult. END says
  "SAME TIME / NEXT TUESDAY". No LIVE badge.
- **Sound** (Web Audio, through `Overlay`): a falling bloop and static as the
  tube goes off; a thump, a rising hum and static as it comes on. `?sfx=0`
  silences it; its level in the mix is not yet heard.

## 3. Layout

240 × 90 cells; px = 8 × column, 12 × row. **Header rows 0–5 (rule on 5);
footer rule on row 84, band rows 85–89.** They cover 72 px at the top and
72 at the bottom of the video.

**Every cam window is 16:9**
([ADR 0014](../../docs/adr/0014-cam-is-the-iphone-camera.md)); on 8 × 12
cells that is any multiple of 64 × 36 px.

| Scene | What it draws |
| --- | --- |
| START | Typed boot lines; "STARTING" / "SOON" in 200 px titles; "T-MINUS" and the countdown beside SOON; the sunflower right (stem at x 1480, head 600 px up, radius 205); a bed of tulips along the footer's rule |
| BRB | The same with `brb` lines, "BE RIGHT" / "BACK", "PRESS ANY KEY" |
| END | "SAME TIME" / "NEXT TUESDAY"; a CAM window; "It's now safe to turn off your stream."; the sunflower; a shorter bed, so the caption stays clear |
| GAME | The bands over the whole game; the cam in a notch bottom-left, the footer's rule running along its top and down its right side, as on Monday |
| CAM | The bands over the whole camera; "THE DEEP EFFECT" in the footer |
| CHAT | The cam top-left, the chat right of a double rule; under the cam a strip of tulips and a small sunflower |

### Punch sets, as built

Read back off OBS on 2026-11-03:

| Scene | Holes |
| --- | --- |
| GAME | Game 0,0 1920 × 1080 + Cam 0,756 576 × 324 |
| CAM | Cam 0,0 1920 × 1080 |
| CHAT | Cam 0,72 1280 × 720 + Chat 1296,72 624 × 936 |
| START | None |
| BRB | None |
| END | Cam 64,336 768 × 432 |

`Chat` is 624 × 936, `overlay.json`'s `chat`
([ADR 0015](../../docs/adr/0015-chat-source-sized-per-overlay.md)).

### The switch

About 1 s, the same between any two scenes (`crt.js`):

| Time (ms) | What happens |
| --- | --- |
| 0–230 | **Off.** The picture squashes to the middle and brightens; the glass closes over the video from top and bottom. A falling bloop. |
| 230–360 | The bright line shrinks to a dot. |
| 360–480 | The dot fades. |
| 480–570 | **Dark.** The holes and the OBS sources move now; a faint afterglow. |
| 570–650 | **On.** A dot. A thump and a rising hum. |
| 650–770 | The dot stretches into a line. |
| 770–1030 | The line opens into the next scene, with a little overshoot, and dims to normal. |

A press before the dark only changes where it goes; a press after it turns
the tube off again from wherever it is. Presses never queue.

### Cost

Composing a frame in the app's browser: START, BRB and END about 5.5 ms
(the whole garden converted every frame), CHAT 2.1, GAME and CAM 0.6. In
OBS, six switches back to back skipped no frames (Status). If it ever
matters, the closed scenes can convert only the sunflower's box and the
bed's strip.

## 4. Build order

1. ✅ This folder, from the template.
2. ✅ Text mode, then stitches; both rejected (ADR 0016, 0017).
3. ✅ The terminal garden: `screen.js`, `ascii.js`, `flowers.js`, `crt.js`,
   six scenes, in OBS 2026-11-03.
4. ⬜ The user's review, olive against pink.
5. 🟨 OBS: ✅ collection, punch sets, switch frames · ✅ a mic · ⬜ chat
   styling against the Restream embed · ⬜ the profile (the user's clicks:
   Profile → Duplicate, then Disconnect Account → Use Stream Key) · ⬜
   `shows.json`.
6. ✅ The vertical page, and setup with `--vertical` (2026-11-04, ADR 0024).

## 5. Open

- **Olive or pink.** Both are built; olive is the default.
- **Is the footer band's strip of little tulips too busy** under the game?
  It is one line in `overlay.html` to drop.
- **Photosensitivity:** the switch has one bright line and dot on dark,
  under a second, once per switch.

# CLAUDE.md — Fitness Friday

The Friday show's overlay is a royal blue drafting sheet with HUGE type and
yellow anatomy blueprints: the body, the brain, the heart, the lungs and the
hand. Each scene is the sheet with its windows cut out. A scene switch is
the word sting: slabs sweep across, and the next scene's words slam in one
at a time, filling the frame.

This file is what is this overlay's own: its concept, art direction and
layout. How it reaches OBS — scenes, sources, the punch pipeline, audio, the
deck, the vertical canvas, reliability — is shared by every overlay and
lives in the [root `CLAUDE.md`](../../CLAUDE.md), with the working agreement.
The page contract is [core/README.md](../../core/README.md). Decisions go in
[docs/adr/](../../docs/adr/README.md).

**Status, 2026-11-05:** both pages are built and in OBS as the `Fitness
Friday` scene collection
([ADR 0027](../../docs/adr/0027-fitness-friday-blueprint-sheet-and-word-sting.md)).
Not yet streamed.

- **The user approved** the horizontal page in the browser on 2026-11-04.
- **All twelve punch sets** were read back off OBS on both canvases (§3).
- **Seven back-to-back switches**, both canvases stinging: **0 of 758**
  render frames skipped, 60 fps, 0.49 ms average render.
- **Not seen with live video:** no game was running and the iPhone camera
  was not sending, so every window rendered black.

**Live heart rate** ([ADR 0028](../../docs/adr/0028-heart-rate-from-our-own-watch-app.md),
[0030](../../docs/adr/0030-the-watch-app-is-standalone-and-drops-rather-than-queues.md)):

- **Built:** the PC side, `heart/heart-bridge.py` and `HEART` in `sheet.js`.
  It was tested in OBS with the bridge's `--fake` feed: GAME showed 64 BPM
  with the beating dot.
- **Built:** the Apple Watch app, `watch/` (2026-11-07). The whole chain
  was driven on the watchOS simulator, which feeds real HealthKit samples
  during a workout session: GAME went live at 61 BPM off the watch, and
  `lost` 15 s after Stop.
- **Never run on the real watch.** Whether it reaches the PC without the
  iPhone is the open question; the simulator shares the Mac's network
  stack and cannot answer it.

**How the collection was built.**

1. Setup created it: `obs-setup.py --overlay fitness-friday --vertical
   --no-profiles`.
2. The mic was copied from Money Talks Monday (ADR 0026), with `NV
   DENOISE`, `EQ`, `COMPRESS` and `LIMIT`, and setup added the ducks.
3. Then `Game`, `Cam` and `Browser`'s settings and `Chat`'s url were copied
   from Money Talks Monday's saved collection over the websocket. That was
   by hand; since 2026-11-05 setup does it itself
   ([ADR 0029](../../docs/adr/0029-setup-copies-the-hardware-sources.md)).
   - `Chat` keeps setup's 560 × 952 and `chat.css`.
   - The token in its url was never printed.

**Open in the collection:**
- **`scenes.json`** is not exported yet. OBS writes a collection to disk
  only when it quits cleanly, so export after that.
- **The vertical canvas's stored stream encoder** is `ffmpeg_svt_av1`,
  which setup flagged. It is inert unless Advanced is ticked in that
  output's settings.
- **`chat.css`** is still the template's. As on Monday and Tuesday, it
  does not reach the Restream embed.

**Files.**

| File | What |
| --- | --- |
| `overlay.html` | The 1920 × 1080 page: the windows, `PANELS`, and per scene its words and layout (`SCENES`) |
| `vertical.html` | The 1080 × 1920 page on VCOMIC: its windows, `STING_BOX`, `SCENES` |
| `anatomy.js` | The plates, drawn in code, and `renderPlate()` / `partsList()` |
| `sheet.js` | The sheet, the builders (`huge`, `fig`, `win`, `titleBlock`, `ecgStrip`, `bpmReadout`…), the sting, `HEART`, and the preview fit. Loaded in place of `core/camera-pan.js` |
| `blueprint.css` | Every style both pages share; the palette tokens are at the top |
| `assets/socials/*.svg` | The socials as yellow line icons |
| `chat.css` | The template's, untouched |
| `overlay.json` | `Fitness Friday`; Chat 560 × 952; `"heart": true` |

---

## 1. Core concept

**One sheet, and the words are the transition.** The reference is the
intro of Cleo Abram's YouTube show: words so big they fill the frame,
cut hard to a beat. We take the type and the pace, never her name, logo or
title cards.

- **At rest,** every scene is one drawing on the sheet. It has a figure
  number, a HUGE headline, and a title block like an engineering drawing's.
  The cam and chat sit in yellow-framed windows cut out of the sheet.
- **On a switch,** the sheet is covered, the words play, and the new sheet
  is uncovered. The plates scan in from top to bottom and the headline
  rises into place.

**Nothing on it is about fitness.** The anatomy is the theme, as the user
asked.

## 2. Art direction

**Palette** (`blueprint.css` tokens):

| Token | Value | Use |
| --- | --- | --- |
| `--royal` | `#1c41d4` | The sheet at its centre; the gradient runs to `#2552e4` at the hot spot |
| `--royal-deep` | `#0f2690` | The sheet's edges, and type on yellow |
| `--plate` | `#2149dc` | Fill inside a drawing: it lifts the part off the grid and hides the lines behind it |
| `--ink` | `#ffd60a` | The yellow: every drawing line, the highlighted word, window frames |
| `--paper` | `#f4f7ff` | HUGE type |
| `--line`, `--faint` | white at 64% and 28% | Rules, captions, dimension lines, the zone border |

**The user's fallback** is real blueprint colours, if yellow on royal blue
does not look good. That is a change of tokens and of the three gradient
stops in each page.

**Type:**
- **Anton** for HUGE lines. Each line is fitted to its box's width at boot
  (`fitAll`), so "SOON" sets bigger than "STARTING". `same: true` sets a
  stack at one size instead (END, vertical CAM and CHAT).
- **JetBrains Mono** for everything technical.
- Both load from Google Fonts, like the other overlays, until step 9.

**Line weights** stay the same at any plate size (`vector-effect:
non-scaling-stroke`): outline 2.4 px, detail 1.5, fine 1, hair 0.8.
Construction lines are white: centre lines dash-dot, hidden parts dashed,
the heart's wireframe at 24%.

### The plates

Each one is drawn in code by `anatomy.js` and seeded, so every load draws
the same plate. Balloons (A, B, C…) point into a parts list wherever the
horizontal scene has room for one. The vertical page shows no balloons.

| Plate | Scene | What it is |
| --- | --- | --- |
| Body | START | Front view, eight heads tall, mirrored about its centre line. Muscle contours, joint markers, a head-unit ruler, a 1 800 MM height dimension |
| Brain | CHAT | Lateral view. Folds from an activator–inhibitor labyrinth, traced with marching squares and clipped to the cerebrum. The lateral and central sulci are forced as valleys, so gyri run along them. Cerebellum folia and the brainstem |
| Heart | CAM, and small on GAME | Front view. The great vessels are tubes with cut ends, with coronaries and seeded twigs, and a light wireframe for volume. Beats at the live rate, or 72 |
| Lungs | BRB | Front view: trachea with rings, main bronchi, fissures, the left lung's cardiac notch, a bronchial tree grown inside each lung with alveoli at the tips, ribs and the heart behind. Breathes on an 8 s cycle |
| Hand | END | Palm view, fingers spread: phalanges, metacarpals, eight carpals, radius and ulna. The hand waves about the wrist |

**Motion is a transform on its own layer**, so the compositor does it and
nothing repaints. The plate's moving parts sit in a second SVG inside
`.plate-move`. The ECG strip scrolls the same way.

### The live heart rate

`HEART` in `sheet.js` reads `heart/heart-bridge.py`'s `/events` and keeps
one of three states on `body[data-hr]`:

| State | When | What shows |
| --- | --- | --- |
| `design` | No reading yet this session | The drawn 72, as the user approved it |
| `live` | The last reading is under 15 s old | The number, a dot beating beside BPM, and both hearts beating at that rate (`--beat`) |
| `lost` | There were readings, and none for 15 s | `--`, dimmed. A number that is not live never shows |

- **The ECG follows the rate by spacing its beats**, not by scrolling
  faster ([ADR 0032](../../docs/adr/0032-the-ecg-follows-the-rate-at-a-constant-paper-speed.md)).
  Paper speed is constant on a real trace, and retiming a running
  animation makes it jump — so the scroll is written once and never
  touched, and `ECG.tune` only rewrites how many beats the loop holds.
  The complex itself is drawn in seconds (P 90 ms, QRS 90 ms, QT by
  Bazett), because a QRS is 90 ms at 50 bpm and at 160; diastole is the
  only part the rate moves. Beats per loop must be whole, so the drawn
  rate is within 3.2% between 60 and 180 bpm.
- **When the bridge is down**, the page retries after 3 s, doubling to once
  a minute, so a day without it costs one log line a minute, not one every
  3 s.
- **`start.py` starts the bridge before OBS**, so the first try connects. A
  bridge started later is found within a minute.

### The sting

| Time (ms, 2 words) | What happens |
| --- | --- |
| 0–240 | A yellow slab sweeps in from the left. The blue slab follows 70 ms behind, a parallelogram with 260 px of slant |
| ~320 | **Covered.** The layout, the holes and the OBS sources change now |
| 320–920 | The words, 300 ms each (230 ms each with three words). Each is fitted to at most 90% of the width and 66% of the height of `STING_BOX`, which is the canvas on the horizontal page and the safe zone on the vertical. The word before it zooms through as a yellow outline, and a dimension line under it reads its width in px. Words alternate white and yellow; **the last is blue on a yellow flash** |
| 920–1290 | The blue slab sweeps off to the right, and the yellow one 90 ms behind it. The new sheet's headline rises, its plates scan in, and its window frames snap in |

- **Words:** START "FITNESS / FRIDAY", CHAT "LET'S / TALK", GAME "GAME /
  ON", CAM "UP / CLOSE", BRB "BE / RIGHT / BACK", END "THAT'S / A / WRAP".
  They live in `SCENES[key].words`.
- **The clock times it.** Each step lands on a `setTimeout` and commits
  its end state. Web Animations only draw it: in a hidden pane their
  `finished` never resolved.
- **The newest press wins.** While the frame is covered the words restart
  for the new scene; while it is uncovering, the slabs return from where
  they are.
- **At boot**, before OBS names a scene, the frame is covered with
  "FITNESS FRIDAY" on it. The first scene OBS reports lands with no sting.
- **No sound yet.**

## 3. Layout

Windows are in `WIN` in each page. Every cam window is 16:9; Chat is
`overlay.json`'s 560 × 952, or that shape scaled.

### Horizontal, 1920 × 1080

| Scene | On the sheet |
| --- | --- |
| START | FIG. 01; "STARTING / SOON" on the left, 1040 wide; the title block and a 150 px countdown under it; the body on the right, full height |
| CHAT | Cam and chat windows; the brain under the cam, with "LET'S TALK" and the socials beside it |
| GAME | Only two bands: a 44 px header (FIG. 03, socials) and a 64 px footer ("FITNESS FRIDAY", the ECG, the beating heart, the BPM), each with a yellow rule. The cam window sits on the footer at the bottom left. No zone border |
| CAM | The cam window; "THE DEEP EFFECT" under it; the right column holds the heart, its parts list, the BPM with an ECG, and the socials |
| BRB | The lungs and their parts list on the left; "BE RIGHT / BACK", the breathing cue and the title block on the right |
| END | "SEE YOU / NEXT / FRIDAY" on the left over the title block; the cam window top right; the waving hand and its parts list under it |

### Vertical, 1080 × 1920

Face on top. Type stays inside `SAFE_*` (x under 916, y 140 to 1596).
Windows and plates may cross the right rail and sit under the caption zone.
Text never does.

| Scene | On the sheet |
| --- | --- |
| START | "STARTING / SOON" across the top; the countdown and a narrow title block on the left; the body on the right, its feet under the caption zone |
| CHAT | Cam on top; "LET'S / TALK", the brain and the socials stacked on the left, beside the chat column |
| GAME | A centred stack: cam, "FITNESS FRIDAY", the game at full width, then the ECG, the beating heart, the BPM and the socials. The sheet is full, so the zone border shows |
| CAM | Cam at full width; "THE DEEP / EFFECT" under it; the BPM, ECG and socials on the left, the heart on the right |
| BRB | "BE RIGHT / BACK" across the top; the lungs; the breathing cue and the socials |
| END | Cam on top; "SEE YOU / NEXT / FRIDAY"; the socials on the left; the waving hand at the bottom right |

### Punch sets, read back off OBS on 2026-11-05

| Scene | Horizontal | Vertical |
| --- | --- | --- |
| START, BRB | None | None |
| CHAT | Cam 48,64 1216 × 684 + Chat 1312,64 560 × 952 | Cam 48,196 768 × 432 + Chat 448,660 468 × 796 |
| GAME | Game 0,0 1920 × 1080 + Cam 0,710 544 × 306 | Cam 156,206 768 × 432 + Game 0,790 1080 × 608 |
| CAM | Cam 40,40 1472 × 828 | Cam 0,196 1080 × 608 |
| END | Cam 1032,96 816 × 459 | Cam 48,190 832 × 468 |

**Previewing outside OBS:** serve the repo root and open
`/overlays/fitness-friday/overlay.html?scene=START`, or
`vertical.html?preview=START`. On the vertical page `?scene=` names the OBS
scene (`core/vertical.js`).

- **Scaling:** outside OBS the canvas scales to fit the window.
- **Switching:** a bar of scene buttons plays the sting, and so do keys 1–6.
  `&clean` hides the bar.
- **Live heart rate:** run `py -3 heart/heart-bridge.py --host 127.0.0.1
  --fake` to see it without the watch or a firewall prompt.

## 4. Build order

One step at a time, each checked before the next:

1. ✅ This folder, the plates, the sheet, the sting and all six horizontal
   scenes, checked in a browser (2026-11-04).
2. ✅ The user's review of the horizontal page in the browser:
   "looks good" (2026-11-04).
3. ✅ The live heart rate's PC side: `heart/heart-bridge.py`, `HEART`,
   `start.py` (ADR 0028, 2026-11-05).
4. ✅ The vertical page, sharing `anatomy.js`, `sheet.js` and
   `blueprint.css` (2026-11-05).
5. 🟨 OBS:
   - ✅ The collection, with a mic, and the punch sets on both canvases
     (2026-11-05).
   - ⬜ The user's look at it in OBS, with live video.
   - ⬜ The chat styling.
   - ⬜ The profile.
   - ⬜ `shows.json`.
   - ⬜ Export `scenes.json`.
6. 🟨 The Apple Watch app, `watch/` (ADR 0028, 0030).
   - ✅ Built on the MacBook and driven end to end on the watchOS
     simulator (2026-11-07).
   - ⬜ Run on the real watch: does it reach the PC without the iPhone,
     does it hold up with the wrist down, what does it cost the battery.

## 5. Open

- **Sound.** Monday's sting has sound effects; would a hit on each word
  suit this one? It would ride `Overlay`'s audio, like alerts.
- **Is 1.3 s right for every switch?** The comic's pan is 0.98 s and
  Monday's smash 1.9 s.
- **The eye is not drawn.** It was planned for CAM, and CAM took the heart
  because the user named it.
- **Before the first reading, the BPM shows the drawn 72**, which a viewer
  could take for live. If that matters, `design` can show `--` as well.

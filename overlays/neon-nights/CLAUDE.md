# CLAUDE.md — Neon Nights

1984 Miami at sunset, built for the GTA VI stream. A slatted sun sinking
behind an art deco skyline, palms in silhouette, a neon grid running to the
horizon, chrome italic headlines and a HUD lifted off an 80s crime game.
A scene switch is **the cruise**: the sunset rises over the frame, the
destination's name slams in as chrome a word at a time, the sky leaves out
of the top and the new scene lands under 170 ms of tape tear.

**The look is the only thing borrowed.** No game, studio, city or show name
appears anywhere on screen or in the art — the only brand on the page is the
channel's own ([ADR 0033](../../docs/adr/0033-neon-nights-sunset-page-and-the-cruise.md)).
`neon-nights` is the folder and the OBS collection; it is never drawn.

This file is what is this overlay's own: its concept, art direction and
layout. How it reaches OBS — scenes, sources, the punch pipeline, audio, the
deck, the vertical canvas, reliability — is shared by every overlay and
lives in the [root `CLAUDE.md`](../../CLAUDE.md), with the working agreement.
The page contract is [core/README.md](../../core/README.md). Decisions go in
[docs/adr/](../../docs/adr/README.md).

---

## 1. Core concept

Six scenes, each exactly the canvas. The camera never moves; the frame is
recomposed behind a cover. Every scene is the same world at a different
hour — START at dusk, CHAT indoors under the deco wall, GAME at night
behind the HUD, CAM at the sun's height, BRB deep night on the strip, END
back at dusk.

Each scene is **two layers**, and the split is load-bearing:

| Layer | Holds | Clipped? |
| --- | --- | --- |
| `.cut` | the sky, the sun, the skyline, the grid floor, the palms, the car, the scanlines, the vignette | **yes** — `clip-path: path(evenodd, canvas minus this scene's windows)` |
| `.over` | window frames and their tabs, headlines, slates, the socials, the clock, the radar, the stars | no |

So the video shows through a window because the art is *clipped away*
there, and the animated art inside `.cut` is clipped for free. A cut
contained in another is dropped first, or `evenodd` would flip it back to
opaque — which is exactly what makes GAME's cam window work inside its
full-frame game window.

A scene drawn as bands over the game (horizontal GAME) names its own
`solid` rects instead of using its holes, and takes the `sky-bar`
background: a **horizontal** ramp, so the top and bottom bands match. A
vertical sky would give one band its dark end and the other its lit end.

## 2. Art direction

### Palette

| Token | Value | What |
| --- | --- | --- |
| `--night` | `#0d0320` | the sky at the top; type on a flash |
| `--deep` / `--dusk` | `#1b0536` / `#3b0a53` | the ramp under it |
| `--magenta` | `#ff2d95` | the hot tube: signs, rims, the sun's base |
| `--cyan` | `#16e0ff` | the other tube: windows, the grid, accents |
| `--gold` | `#ffd93d` | the sun's crown, lit windows, the clock |
| `--paper` | `#f4f2ff` | type |

`--chrome` is the ramp the headlines are filled with: sky → white → pink →
`#8e1158`, with a **hard specular band at 51%**. The band is what makes it
read as metal rather than as a gradient. `--chrome-cy` is its cyan twin,
used for `<em>`.

Four skies, picked per scene by class: `sky-dusk`, `sky-night`, `sky-noon`,
`sky-deco`, plus `sky-bar` for a bands scene.

### Type

| Face | Where |
| --- | --- |
| **Anton**, skewed −9°, chrome-filled | headlines, the clock, the cruise's words |
| **Monoton**, two tubes | the neon signs |
| **Share Tech Mono** | slates, notes, window tabs, the socials |

Headlines are fitted to their box at boot (`fitAll`), so a short line sets
bigger than a long one. `same: true` sets a block at its smallest line's
size — used wherever something has to sit under it. **Headline heights are
the thing that breaks this layout:** `BACK` and `WRAP` set at ~320 px
against their long first line's ~186, so a block is 425–504 px tall, not
300. Everything under one is placed from that.

### The art is computed (`art.js`)

No image file but the four social icons. Both canvases call the same
builders at different sizes.

| Builder | Notes |
| --- | --- |
| `sun` | the slatted disc. **The slats are a mask**, so the real sky shows through them — a sky-coloured bar is right at exactly one height |
| `palm` | trunk, rings, 9 fronds, coconuts; dark fill with a magenta rim. **Drawn 400 × 1000 at `preserveAspectRatio="none"`, so every caller keeps `h = 2.5w`** or the fronds squash flat. The crown is at 26% of the height |
| `skyline` | stepped deco blocks, spires, windows on a shared 13 × 15 grid, neon cornice bands. Seeded, so a reconnect redraws the same city |
| `car` | an 80s wedge, tail lights pulsing; `drive` cruises it |
| `radar` | the HUD dial: conic sweep, grid, blips, player arrow. HTML, four elements |
| `stars` | five points, `lit` of them on, the last pulsing |
| `burst`, `stardust`, `floor` | the deco fan, the star field, the perspective grid |

### Motion at rest

Palms sway on 7 s, the floor scrolls on 1.8 s, the radar sweeps on 2.8 s,
neon buzzes and the skyline's cornices flicker on long step cycles, the
car's tail lights breathe, the END/GAME blips pulse. All of it is inside
`.cut` or over the bands, so **none of it ever plays over live video** —
the root `CLAUDE.md`'s rule for the comic's speed lines, kept here.

### One real number

The clock is the machine's own, every 10 s, in every `.clock-val`. Nothing
else on this page has a feed, so nothing else is drawn as a readout. The
radar and the stars are ornament and look like ornament.

## 3. The cruise (`cruise.js`)

Loaded in place of `core/camera-pan.js`. It defines `current`,
`transformFor(t)` and `goTo(t, {instant})`, which is the whole contract
core asks of a transition.

| Beat | ms | What |
| --- | --- | --- |
| in | ~300 | the sunset rises from the bottom, a lit cyan rule at its leading edge, speed streaks ahead of it |
| covered | — | `switchTo()`: the layout, the windows and the OBS sources change, only here |
| words | 235–310 each | the name slams in as chrome, a word at a time; the word before zooms out as a magenta outline; the last is dark on a sunset flash |
| out | ~320 | the sky keeps going and leaves out of the top |
| tear | 170, at +190 | eight bands shear on their own steps over `feTurbulence` static and an RGB split, on the new scene |

**Nothing moves that the video shows through.** The motion is all in the
cover — which is why the streaks live on the cover's leading edge and not
on a transform of the scene. A transform there slides the art out from
under its own window frames while the video stays put.

Newest press wins and presses never queue. The clock decides when a slide
has landed, not the animation, so a page whose frames stall still switches.
The first scene OBS reports settles with no cruise.

Two measured details about the slam: the skew's compensation is taken at
the **caps' mid-height**, not the baseline (at the baseline the word is
centred where no ink is), and `0.1585 × cap` is added to the width it is
fitted against, or a two-letter word runs off both edges.

## 4. Layout

Windows are canvas px. Every cam window is 16:9 ([ADR 0014](../../docs/adr/0014-cam-is-the-iphone-camera.md));
`Chat` is `overlay.json`'s **440 × 930** ([ADR 0015](../../docs/adr/0015-chat-source-sized-per-overlay.md)) —
440, not 540, because the vertical window sits at x 476 and 440 puts its
right edge on 916, exactly `CANVAS_W - SAFE_RIGHT`.

### Horizontal, 1920 × 1080

| Scene | Windows | Composition |
| --- | --- | --- |
| START | `Cam` 1096,110 760×428 | sign and headline left, countdown under them, cam top right, sun and palm bottom right |
| CHAT | `Cam` 48,150 1180×664 · `Chat` 1400,110 440×930 | cam left, chat right under its bulb strip, headline and socials bottom left over the skyline |
| GAME | `Game` full · `Cam` 40,672 512×288 | two bands: slate and socials on top, title, clock, stars and radar below; cam bottom left |
| CAM | `Cam` 40,60 1240×698 | cam top left, headline under it, sign/clock/socials in the right column over the sun |
| BRB | — | headline left, sign and clock right, the car cruising the grid under a low sun |
| END | `Cam` 1040,548 800×450 | headline and stars left over the deco burst, cam bottom right |

### Vertical, 1080 × 1920

Face on top. Type stays inside `SAFE_*` (x under 916, y 140 to 1596); the
sun, the palms and the windows may cross the right rail and sit under the
caption zone, text never does.

| Scene | Windows |
| --- | --- |
| START | `Cam` 48,240 768×432 |
| CHAT | `Cam` 48,196 768×432 · `Chat` 476,660 440×930 (right edge exactly 916) |
| GAME | `Cam` 156,206 768×432 · `Game` 0,790 1080×608 |
| CAM | `Cam` 0,196 1080×608 |
| BRB | — |
| END | `Cam` 48,190 832×468 |

`CRUISE_BOX` keeps the cruise's words inside the safe box.

### Punch sets

Read off the pages, not off OBS — this overlay is not in OBS yet. Every
hole reported its authored rect to the pixel, and every one was punched:

```
START  Cam                 CHAT  Cam + Chat
GAME   Game + Cam          CAM   Cam
BRB    (none)              END   Cam
```

They must be read back off OBS once the collection is built, the way every
other overlay's were.

## 5. Status

- Both pages render all six scenes, horizontal and vertical, with no
  console output. The cruise was driven end to end in the browser.
- **Not in OBS**, and never streamed. `tools/obs-setup.py --overlay
  neon-nights` builds the collection.
- The chat embed styling (`chat.css`) is written but, like every other
  overlay's, does not yet reach the Restream embed.
- No mascot, no transition filter, no heart bridge.
- Still to do, as for the other shows: its OBS profile, and its line in
  `shows.json` when the schedule exists.

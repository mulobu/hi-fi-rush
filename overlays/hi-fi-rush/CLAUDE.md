# CLAUDE.md — Hi-Fi Rush overlay

Hi-Fi Rush inspired stream overlay. The entire stream is **one comic book page**.
Each OBS scene is **one panel** on that page. Switching scenes **pans the camera
across the page** to that panel, the way Hi-Fi Rush moves between panels during
Peppermint's mission report sequences.

This file is what is this overlay's own: its concept, art direction and panel
layout. How it reaches OBS — scenes, sources, the punch pipeline, audio, the
deck, the vertical canvas, reliability — is shared by every overlay and lives
in the [root `CLAUDE.md`](../../CLAUDE.md), along with the working agreement.
Sections keep their original numbers so cross-references still resolve: §1, §4
and §5 are here; §2, §3 and §6–§9 are there.

---

## 1. Core concept

- One oversized comic page (7680 × 4320) lives inside a 1920 × 1080 browser source.
- The browser source viewport is the **camera**. The page is the **world**.
- Panels are positioned on the page. Some are transparent **holes** with OBS video
  sources behind them; some are pure drawn art.
- "Switching scenes" = animating one CSS transform on the page. Nothing in OBS
  actually swaps.

---

## 4. Art direction

Reference: Hi-Fi Rush mission report / briefing sequences.

- **Gutters are light blue-grey** (`#aebcc9`), not paper cream.
- **Panels are flat saturated colour** with a **halftone dot grid over the top**,
  never smooth gradients.
- **Borders are hand-inked and wobbly** — irregular `border-radius`, corners
  overshoot. Hard offset drop shadows, no blur.
- Red marker annotation layer: hand-drawn circles, scrawled notes, dashed
  connectors, taped-on inset "photos".
- Figures are **black silhouettes**, no interior detail.
- Speed lines, circuit patterns, radiating rays as panel fills.

### Palette

```
--ink      #16161d    --gutter  #aebcc9
--yellow   #f5d030    --marker  #d93028
--peri     #b9c3d6    --navy    #3b4a9e
--cyan     #35d6e8    --paper   #f4f1e8
--mint     #3fb98a    --plum    #6b3f8f
```

### Type

The game's actual typefaces are **not publicly available**. Closest matches:

| Role                          | Font             |
| ----------------------------- | ---------------- |
| Display / panel tags / stamps | Bangers          |
| Hand annotation caps          | Permanent Marker |
| Scrawled notes                | Caveat           |
| Body / caption bar            | Baloo 2          |

**Must self-host as local `.woff2` before going live.** A Google Fonts fetch
failing at OBS launch blanks the overlay.

### Motion

- Everything on **120 BPM** (`--beat-ms: 500ms`) from a shared wall-clock epoch.
- Pan: `980ms` (≈2 beats), `cubic-bezier(.32,1.38,.48,1)` — overshoot and snap back.
- Landing punch on the target panel; **screen shake fires on landing, not departure**.
- Snappy easing throughout: near-instant in, slight overshoot, hold. Never soft fades.

### Signature element

The **panel tag** — inked slab, bottom-left of every panel, hard offset shadow,
pulsing on the beat. The live panel's shadow flips from marker red to cyan.

**The caption bar was removed**, along with every character name. It was a
speaker-name-over-subtitle strip fixed to the frame, and it put words in the
mouths of characters this overlay does not own. Nothing replaced it — the panel
tag already names the scene, and the bottom 140px of frame is back.

Panel config no longer carries `who` / `line`. Franchise references are gone from
the rendered overlay: the intel board reads `INTEL`, and the end credits now
credit the mascot rather than a cat. The design reference above still stands —
it's the look being aimed at, not text that ships.

### Mascot

A cursor-following character, its own browser source, **above** the overlay in
COMIC. Shares no code with the overlay; the only fact both read is the scene
name. `mascot/placement.json` (in this folder) maps a scene to a camera-space spot, and a scene
with no entry hides it — which is how it appears on GAME, BRB and CHAT and
nowhere else without a line of conditional logic.

It replaced the cat silhouette on the brb panel and the cat in the end credits,
which were placeholders for exactly this.

| Scene | Where | Why |
| --- | --- | --- |
| GAME | bottom left, over the capture | clear of the tag, out of most HUDs |
| BRB | in the taped photo frame | the panel's webcam hole, redrawn |
| CHAT | bottom right, in the gutter | the portrait panel leaves 555px of empty page |

It walks between spots on the pan's own duration and easing, so it travels with
the page rather than teleporting on the scene name.

**The vertical mascot needed no code.** `MascotV` is a second browser source at
1080 × 1920, top of `VCOMIC`, pointed at the same bridge with
`&place=placement-vertical.json`. `mascot.html` already took a `place` parameter
and already derived every bound from `innerWidth`/`innerHeight` rather than
assuming 16:9 — including the edit sliders, which reset their own ranges at
runtime. So the vertical twin is one JSON file and one source.

It names the same three scenes, so the two pages stay consistent. Spots were
measured off the built page in canvas pixels rather than eyeballed:

| Scene | Where | Measured against |
| --- | --- | --- |
| GAME | right side, below the webcam window | Cam window bottoms out at 1214, scrawl at 1367, tag starts at 1851 — cell sits 1370–1750 |
| BRB | inside `.mascot-frame` | frame is 171,773,636,622; a 460 cell centres in it |
| CHAT | right gutter, small | the portrait panel leaves only 218px — the tightest, and first to drop if it reads badly |

`MascotV` is last in the stack for the same reason `Mascot` is last in COMIC: above
the overlay, because a punched hole is a transparent rectangle and would put live
video behind the mascot's own alpha instead of comic art.

### Socials

Paper cut-outs, one per platform, in `assets/socials/*.svg` at the repo root — scissor-faceted paper,
inked edge, taped, logo glued on with a hard shadow. Kick is `thedeepeffect`,
Twitch and YouTube share `thedeepeffect_`, Instagram is `@thedeepeffect__` —
three labels. The handles live once, in `core/contract.js`, and both pages
read them through `core/socials.js` — a handle change is one edit.

Each scene panel carries a `socials` entry. They are sized in **canvas px** via
`--u = 1 / scaleFor(p)`, because panels rest at 0.33× to 1.17× and page-px sizes
would make the handle 3.5× bigger on one scene than another. Always lifted `over`,
since the game panel is all hole. `chat` places its stickers in the **gutter**
(`page: {x, y}`), not the panel — at 0.33× there is no strip wide enough. Placed
against the mascot spots in `placement.json`; move one, re-check the other.
Layouts: `stack` (three lines), `row` (one), `pair` (Kick + Twitch/YT, then IG).

Vertical: every block measured inside the safe box (text under x 904, above
y 1584) and clear of `placement-vertical.json`. Two costs, both deliberate:
`chat` sits over the **top of the chat window** — the portrait panel fills the
frame and has no free page — and `game`'s cyan scrawl was removed so the
socials could take its slot in the info band.

### Alert layer

Alerts (follow, sub, raid, cheer) live in **camera space**, not on the page —
sibling of the caption bar, `z-index: 60`, fixed to the frame. They slam in as a
comic **inset** over whatever panel the camera is on. Taped-on photo / burst,
hard offset shadow, no blur.

- **Beat-quantized.** An arriving alert waits for the next beat boundary, then
  lands on the downbeat with everything else. Same wall-clock epoch, no new state.
- **Queued, not stacked.** One at a time, ~6 beats each. A raid must not open
  eight insets. Above a threshold the queue collapses into a single `×N` burst.
- **Audio rides the browser source.** Check "Control audio via OBS" on `Overlay`
  and the alert sound needs no OBS-side wiring, no extra media source.
- Producer is Streamer.bot / Twitch EventSub over websocket into the overlay.

---

## 5. Panel layout (7680 × 4320)

| #   | Key   | Type  | x, y       | w × h       | rot   | fit     | Holes     |
| --- | ----- | ----- | ---------- | ----------- | ----- | ------- | --------- |
| 1   | start | video | 64, 64     | 2360 × 1180 | −1.0° | **fit** | Cam       |
| 2   | chat  | video | 5200, 64   | 2416 × 3188 | 0.8°  | **fit** | Chat      |
| 3   | game  | video | 64, 1292   | 3400 × 1960 | 0.5°  | fill    | Game, Cam |
| 4   | cam   | video | 3512, 1292 | 1640 × 956  | −1.4° | fill    | Cam       |
| 5   | brb   | video | 64, 3300   | 2360 × 956  | 1.1°  | **fit** | — (mascot)|
| 6   | end   | video | 2472, 3300 | 2680 × 956  | −0.6° | **fit** | Cam       |
| 7   | board | art   | 2472, 64   | 2680 × 1180 | 0.7°  | fit     | —         |
| 8   | np    | art   | 5200, 3300 | 2416 × 956  | 1.3°  | fit     | —         |
| 9   | latest| art   | 3512, 2296 | 1640 × 956  | 1.6°  | fit     | —         |

Margin 64, gutter 48.

**Panel 9 is not the alert.** The alert is a camera-space inset (§4). Panel 9 is
the **LATEST** board — most recent follower / sub / top cheer, scrawled in marker.
The slot stays because it sits directly under `cam`; deleting it punches a hole in
the grid. The alert layer updates its text in passing.

**Panel 1 shows the webcam, and `Standby` is gone.** The start panel's window
was a `Standby` media source at 60%,14%,35%,70% — a square opening, so a 16:9
webcam would have lost a third of its width to the fill crop. It is now `Cam` at
58%,28%,38%,42.8%, which is 897 × 505 page px: 16:9 to within a pixel. A
starting-soon screen wants a face in it, and `Standby` existed to fill this one
hole and nothing else, so it was dropped from `COMIC` the way `Brb` was (§8) —
a source no hole maps to shows through whichever hole it overlaps. The `STAND
BY` art and the countdown stay; they are the panel, not the source.

**Panel 5 has no holes.** The webcam window it used to carry at 70%,16%,26%,62%
is now `.p-brb .mascot-frame` — the same box, drawn rather than punched, as the
taped-on photo inset §4 already calls for. The mascot lands inside it. A hole
there would have been wrong twice over: a punched hole is transparent, so the
mascot's own alpha would have had live video behind it instead of comic art, and
the hole would have claimed the single `Cam` item away from the game panel
bleeding into frame above.

**Panel tilt is counter-rotated on landing** — the page rotates the opposite way
so the focused panel sits square to the frame.

**`fit` is per-panel.** `fill` crops to 16:9; `fit` shows comic bleed around the
panel. Chat is portrait, so it uses `fit` — filling it would crop brutally.

**A panel may only use `fill` if its aspect is within ~5% of 16:9.** Only `game`
(1.735, −2%, loses 27px) and `cam` (1.715, −4%, loses 39px) qualify. Everything
else is `fit`.

Measured crops that forced this: `brb` 2.469 (+39%) lost 746px and `end` 2.803
(+58%) lost 1108px, clipping their `Cam` holes by 251px and 417px. A clipped hole
is not cosmetic — step 6 pushes that rect to OBS, so the webcam ends up partly
off-canvas. `start` 2.0 (+13%) lost 240px, which spared its hole but cut 83px off
the `STREAM START` tag and shaved the `STANDBY` type.

**Check the art, not just the holes.** `start` was left on `fill` on the strength
of its hole surviving; the tag was clipped the whole time. Decorations (`rays`,
`speedlines`) are deliberately oversized and are expected to overrun.

Fit scale is `min(sx, sy) * 0.97`. The halftone on `.page::before` is inset
`-3990px` (133 whole 30px tiles) so it extends past the page edge — otherwise
fitted bottom-row panels reveal a dotless band where the viewport background
takes over. Riding the page's own transform keeps the dots in scale and phase at
every zoom level.

**`Cam` appears in four panels.** In OBS that's one source referenced four times;
only the visible instance gets transformed.

### Vertical page (4320 × 7680)

9:16, four times the vertical canvas — the multiple the horizontal page uses.
Margin 64, gutter 48, unchanged. Six panels that are scenes, three art filler.

| #   | Key   | Type  | x, y       | w × h       | rot   | fit      | Holes     |
| --- | ----- | ----- | ---------- | ----------- | ----- | -------- | --------- |
| 1   | start | video | 64, 64     | 2072 × 2200 | 0.9°  | fit      | Cam       |
| 2   | chat  | video | 1912, 2312 | 1104 × 3200 | −1.1° | fit      | Chat      |
| 3   | game  | video | 64, 2312   | 1800 × 3200 | 0.5°  | **fill** | Cam, Game |
| 4   | cam   | video | 3064, 2312 | 1192 × 1576 | 1.3°  | fit      | Cam       |
| 5   | brb   | video | 64, 5560   | 1365 × 2056 | 1.1°  | fit      | — (mascot)|
| 6   | end   | video | 1477, 5560 | 1365 × 2056 | −0.6° | fit      | Cam       |
| 7   | board | art   | 2184, 64   | 2072 × 2200 | −0.7° | fit      | —         |
| 8   | np    | art   | 2890, 5560 | 1366 × 2056 | 1.5°  | fit      | —         |
| 9   | latest| art   | 3064, 3936 | 1192 × 1576 | −0.8° | fit      | —         |

**`game` is 1800 × 3200 — exactly 9:16 to six decimal places**, so `fill` renders
1080 × 1920 with zero crop *and* zero bleed. It is the only panel that clears the
~5% rule above, which the frame aspect now measures against 0.5625 rather than
1.778. Everything else is `fit`, and on a vertical page that is the look rather
than a compromise: comic bleed is the point.

Its two windows stack, **cam above game**, both at 4%, 92% and 16:9 against the
1770 × 3170 content box — 1628 × 916 page px, 977 × 550 on canvas. `Cam` at
y 10.04%, `Game` at y 40.43%: canvas 200–750 and 778–1328, leaving 1352–1596 for
the band below. Neither is `bare`, so unlike the horizontal page no cut nests
inside another and `mergeCuts` has nothing to do.

**Cam is first, and that is the whole composition.** The windows originally ran
game-then-cam with the cam narrower at 68%, which put gameplay alone at 26% of
frame — under the 40–50% every source gives the primary zone — and put the face
in the dead centre, where mobile eyes do not go. Face top, game middle,
engagement bottom is what the vertical-streaming material converges on, and
equal-width stacked windows also read as two comic panels rather than a window
with an inset. Coverage went 40% → **52%**.

**`.p-game` is navy on the vertical page and `--ink` on the horizontal one, and
that is not an inconsistency.** On the horizontal page the `Game` hole is `bare`
at 100% × 100%, so the panel background never renders a pixel and its colour is
arbitrary — ink was as good as anything. Vertically the two windows cover 40% of
the frame and the other 60% *is* the page, so ink rendered a 1080 × 1920 black
slab with one scrawl in it: the panel that looked most broken was the one whose
CSS was copied unchanged. §4 already says what a panel is — flat saturated colour
under a halftone grid — and the fix is to obey it. Navy, plus a static `.burst`
(the shared `.rays` conic with the spin removed and its origin at 50% 34%, so the
vanishing point lands between the two windows instead of inside the cam), the
`.chevrons` beat strip closing the band under the cam window, and the `LIVE` strip
promoted to an inked slab with a marker pip on the beat.

The scrawl on that panel is **cyan, not marker red**. §4's annotation layer assumes
a light ground — plum, yellow, peri — and every other scrawl has one; red on navy
is mud at 1080 wide. Cyan is already the panel's accent, on the `LIVE` slab and on
the live tag's shadow.

### Platform safe zones — the vertical page's real constraint

The vertical output goes to TikTok Live, YouTube vertical and Twitch through
**Restream**, which fans one 1080 × 1920 encode out unchanged. So the layout
cannot be tuned per platform and the strictest margins govern everywhere:
TikTok's **140 top / 324 bottom / 164 right**, against Shorts' 120 / 300 / 96.
`SAFE_TOP`, `SAFE_BOTTOM`, `SAFE_RIGHT` and a 12px `SAFE_PAD` sit next to the
canvas constants in `vertical.html`.

**A picture may cross the right rail; type may not.** Holding every window
inside 916px would cost 15% of the frame width to protect footage whose action
is centred — a covered corner of game capture costs nothing. So the windows keep
their full 977px and only text is held inside `SAFE_RIGHT`.

Measured before any of this was fixed, by stepping each panel to its resting
transform and reading the rendered boxes: **the panel tag — §4's signature
element — sat below the caption bar on five of six scenes.** `game` +297 canvas
px, `chat` +269, `end` +119, `brb` +118, `cam` +17. On `game` the `LIVE` slab was
also 109px *above* the top line, so both ends of the flagship panel were in
chrome. Nothing about this is visible in OBS, which renders the full 1080 × 1920
with no UI over it; it only appears on a phone.

**The tag is fixed by measurement, not by a number.** It is authored once, in
panel coordinates, at `bottom: 32px` — but each panel lands at its own fit scale,
so no single value clears the line on all six and six hand-tuned values rot the
first time a panel moves. `fitTagsToSafeArea()` applies each panel's resting
transform, measures that panel's own tag, and raises it by exactly the overflow
converted back to page px. The scale comes from `scaleFor()`, never from the
measured rect: every panel is tilted and a rotated AABB is taller than the box it
encloses, so dividing by it would under-raise by ~11% and still leave `game`
short. It runs on `document.fonts.ready` — a Bangers tag measured against the
fallback stack is the wrong height — and touches nothing the pan or the punch
reads, so landing late is safe.

The rest were art-local and moved by hand: `start`'s scrawl `right` 6% → 14%,
`end`'s rank stamp 8% → 15% and its credits `bottom` 8% → 9.5%, `chat`'s header
`top` 26px → 188px, and the `Chat` hole 82% → 72.6% tall at y 11.6% — the chat
log ran 139px into the caption bar, which matters more than most because chat is
the one source on the page whose *job* is to be read.

Resting coverage and clearance, read back off the built page: `start` 20% ·
`chat` 36% · `game` 52% · `cam` 22% · `brb` 0% · `end` 20%, all six clear on
every margin.

**High-frequency radial art aliases on a vertical stream, and reads as a broken
panel.** `.speedlines` is 1° of ink every 3.4° *and* it spins; the static
`.burst` is 3° of white every 10°. Both on the vertical `game` panel, the two
conic gradients beat against each other, and since every phone views this canvas
downscaled the moiré resolves into a flat grey wash — it looks exactly like the
panel background failing to paint, which sends you to the mask code. It is not
the mask: with `mask-image: none` the panel is uniform navy. The vertical `game`
panel therefore carries no `speedlines`. The horizontal page never hits this
because its game hole is the whole panel, so no speedline there is ever visible.

**Skirt is 1500**, not 3000. Derived the same way — every ordered pair stepped
through the real easing — peaking at `end` → `start`, **1061 page px at 549 ms**.
It is less than half the horizontal figure because the vertical panel scales are
uniform; there is no 0.33-scale `chat` outlier to pan through. 1500 is 41%
headroom and 50 whole halftone tiles; the page is 144 × 256.

The simulator that produced both numbers reproduces the horizontal page's
documented `cam → chat` peak to the decimal, which is why the vertical figure is
trusted rather than guessed.

Punch sets, read back off the built page rather than reasoned about: `start` →
Cam + Chat · `chat` → Cam + Chat + Game · `game` → Cam + Game · `cam` → Cam ·
`end` → Cam · `brb` → **nothing**. `brb` punching nothing is the point — the
mascot frame is drawn art with comic behind it, and no source is close enough to
claim a hole there, so the whole view is ink. `start` dropped `Game` when the
game panel's windows moved down the panel for the safe-zone pass below: they no
longer reach far enough up to bleed into the start view.

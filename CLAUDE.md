# CLAUDE.md — Comic Page OBS Overlay

Hi-Fi Rush inspired stream overlay. The entire stream is **one comic book page**.
Each OBS scene is **one panel** on that page. Switching scenes **pans the camera
across the page** to that panel, the way Hi-Fi Rush moves between panels during
Peppermint's mission report sequences.

---

## 1. Core concept

- One oversized comic page (7680 × 4320) lives inside a 1920 × 1080 browser source.
- The browser source viewport is the **camera**. The page is the **world**.
- Panels are positioned on the page. Some are transparent **holes** with OBS video
  sources behind them; some are pure drawn art.
- "Switching scenes" = animating one CSS transform on the page. Nothing in OBS
  actually swaps.

---

## 2. Architecture (final)

```
OBS scene: COMIC          <- the only real scene
├── Deer      (Browser 1920x1080)   TOP — mascot, over the art
├── Overlay   (Browser 1920x1080)         comic art, masks video spill
├── Chat      (Browser)
├── Cam       (Video Capture Device)
├── Game      (macOS Screen Capture — "Game Capture" is Windows-only)
└── Standby   (Media Source)

Trigger scenes (one per Stream Deck button), each containing
ONLY a nested reference to COMIC:
  START · GAME · CAM · BRB · CHAT · END
```

**Naming: scenes UPPERCASE, sources TitleCase.** OBS keeps scenes and sources in
a single namespace — a scene *is* a source internally — so it refuses to create a
scene named `BRB` while a source named `BRB` exists, and says nothing useful about
why. The lookup is case-sensitive, so this convention makes every scene/source
pair legal. It is also why the source is `Brb`, not `BRB`.

**Why nested trigger scenes:** the browser source is never destroyed or reloaded,
so animation and state survive every switch. Real OBS scene switching (which the
Stream Deck already speaks) with zero teardown.

`tools/obs-setup.py` asserts that whole shape over obs-websocket, so a new
machine is one command rather than an afternoon of clicking. It is idempotent,
and it reports rather than overwrites when a source already exists with a
different kind.

`--export` writes `obs/comic-scenes.json`, a sanitised copy of the collection
for the things the script cannot derive — filters, audio routing, hotkeys. It
has to sanitise: OBS stores browser URLs verbatim, and the setup script puts the
websocket password in them, so the raw collection carries that password and the
absolute repo path. Credentials are scrubbed by *parameter name*, never by
value, and the repo and home paths become `{{REPO}}` / `{{HOME}}`; the export
refuses to write if anything credential-shaped survives. Import, then run the
script — it puts the real path and that machine's own password back.

**The mascot sits over the overlay, not behind it.** Everything else in COMIC is
behind a punched hole; the mascot cannot be, because a punched hole is a
transparent rectangle and would cut a mascot-shaped box out of the comic art
with nothing behind it. Above the overlay, its own alpha composites for free.
`Deer` is therefore not in `managed` and the overlay never touches it — it reads
the scene name for itself and positions itself from `mascot/placement.json`, in
camera-space pixels. The two pages share one fact, the scene name, and no code.

**Data flow**

1. User presses a Stream Deck button → OBS switches to a trigger scene.
2. Overlay hears the scene-name change via `window.obsstudio` (websocket is the
   backup path — see "Scene detection" below).
3. Overlay animates the CSS transform on `.page`.
4. Each frame during the pan, overlay reads `getBoundingClientRect()` on every
   visible hole and pushes `SetSceneItemTransform` to OBS.
5. Pan ends → updates stop. Idle cost is zero.

**Layering — what may be masked and what may not.** A CSS mask applies to the
whole subtree, so nothing that must sit *over* video can share an ancestor with
the mask. Paint is therefore pushed down into two dedicated layers:

```
.page            transform only, paints nothing
├── .page-under  gutter + halftone + skirt        MASKED
└── .panel       border, radius, shadow           never masked
    ├── .under   panel bg, art, speedlines        MASKED
    │   └── ::after  panel halftone               MASKED
    ├── .hole    inked border + hard shadow       never masked
    ├── .panel-tag                                never masked
    └── .over    art lifted above the video       never masked
```

Speedlines and rays live inside `.under` deliberately: nothing animated may play
over live video. The panel halftone is `.under::after`, **not** `.panel::after` —
on `.panel` it would tile straight over the video inside every hole. Same box
either way, since `.under` fills the panel's padding box.

Art authored in `artFor()` sits under the holes by default. Tag it `over` and the
build lifts it out of `.under` to sit on top of the video — used by the `mrrow`
bubble on `brb`, which the webcam would otherwise cover. The tag is always on
top, which matters on `game` where the hole is the whole panel.

**Punching is decided per source, not per panel.** There is one OBS item per
source — `Cam` is referenced by four panels — so a source can only occupy one
hole at a time. For each source the panel on air wins; failing that, whichever
on-screen hole shows the most of itself takes it. That is what lets the webcam
panel bleeding into the CHAT view show real video rather than a placeholder,
while `game:Cam` correctly stays a placeholder on BRB because the live panel has
claimed `Cam`.

Only winning holes are cut, so no hole is ever transparent with nothing behind
it; the rest keep their drawn art via `.hole.punched .fake-source`. The set is
computed from the *resting* transform before the pan starts — `DOMMatrix` over
each hole's page-space corners — so it is decided once per scene change rather
than chased frame by frame. Masks rebuild with it: two small data URIs per pan.

Resulting punch sets: `start` → Standby + Game · `chat` → Chat + Cam · `game` →
Game + Cam · `cam` → Cam · `end` → Cam + Game · `brb` → Game only, since the brb
panel gave its webcam hole up to the mascot.

**A source fills its hole by crop, not by overspill.** `OBS_BOUNDS_SCALE_OUTER`
fits without distorting but renders the whole frame and lets the excess spill
past the bounds box. The mask hides spill that lands on comic art and does
nothing about spill that lands in *another punched hole* — on CHAT that put the
chat browser's overspill straight across the webcam bleeding in from the cam
panel, filling half that window with the wrong source. So `fillTransform()`
crops the source to the opening's aspect first and then stretches: exact fit, no
distortion, and an item paints nothing outside its own opening ever. It needs
the source's pixel size, which is re-read once per scene change, because a
capture can change resolution at any time — a game going fullscreen, a webcam
renegotiating. Until a source has produced a frame there is no size to crop
against, and it falls back to SCALE_OUTER.

Both masks are generated from the same `PANELS` config: one path, `fill-rule`
`evenodd`, one quad cut per hole. Only each hole's **content box** is cut, so
borders and shadows survive by construction. Panel-local cuts are axis-aligned;
page-level cuts carry the panel rotation as hand-rotated corners, because an
axis-aligned approximation leaves slivers at ±1.6°.

**The skirt must exceed the worst fitted bleed.** `.page-under` overhangs the
page by `PAGE_SKIRT` so a fitted panel showing past the page edge shows gutter,
not video. Measured bleed per panel: `chat` 1612 page px (it sits at scale 0.33),
`end` 195, `brb` 118, everything else under 80. Skirt is 2000. Undersize it and
that band goes transparent, exposing black and any `SCALE_OUTER` overspill.

**Cuts may not overlap.** `fill-rule: evenodd` counts crossings, so a cut lying
inside another cut flips that region back to opaque. The game panel hit this on
every switch: its `bare` Game hole is the whole panel and the Cam hole sits
inside it, giving winding 3 — odd — so the webcam window painted solid panel art
over live video. `mergeCuts()` drops any cut contained in another before the
path is built. That is exact here, since the union of A ⊇ B is A, and
containment is the only overlap the layout can produce: holes within a panel are
authored side by side, and panels never overlap each other. Partial overlap
would still flip, so `?debug=1` warns rather than rendering it wrong in silence.

Four ways to get the masking silently wrong, all of which render without error:
separate `<rect>` elements each fill on their own and cut nothing; an SVG
`<mask>` element cannot resolve its own `url(#id)` once the SVG is a data-URI
image; `mask-clip` defaults to `border-box`, which discards the skirt; and one
cut inside another cancels itself, as above.

**Why `getBoundingClientRect()` works with no conversion:** the browser source
viewport is exactly 1920 × 1080, so returned coordinates are already OBS canvas
coordinates. The oversized page is a transformed _child_, not the source size.

**Scene detection — measured, not assumed.** Verified on OBS 32.0.1 /
obs-websocket 5.6.3 / macOS 26.3 with `obs-test.html`, 12 switches:

- `obsSceneChanged` **does** reach a browser source nested two scenes deep, and
  reports the _trigger_ scene name (`GAME`), not the host scene (`COMIC`).
- Both paths fired on all 12 switches, zero misses. Spread between them was
  −1 to +6 ms with the ordering flipping — inside a single 60fps frame, so
  there is no latency argument between them.
- **`window.obsstudio` is therefore the primary path**, because it survives a
  dead websocket. Pans keep working; only hole tracking degrades.
- **`getCurrentScene()` returns `null` at startup** in a nested source — it only
  learns on the first change. Initial panel must come from the websocket's
  `GetSceneList`, or a retried `getCurrentScene`.
- `SetSceneItemTransform` targeting `COMIC` works while a trigger scene is on
  program. Nested addressing confirmed; §2 step 4 is viable as written.

---

## 3. Decisions

| Decision         | Chosen                                 | Reason                                     |
| ---------------- | -------------------------------------- | ------------------------------------------ |
| Video location   | Native OBS sources behind holes        | No re-encode, no generation loss           |
| Geometry truth   | The DOM / CSS                          | One place to author; nothing can desync    |
| Pan mechanism    | CSS transform on one `.page` div       | Any easing; no plugin                      |
| 3D               | CSS 3D only                            | Keeps `getBoundingClientRect()` valid      |
| three.js         | Decorative overlay layer only, if ever | Canvas breaks geometry queries             |
| Browser sources  | One, 1920×1080                         | Best practice; oversized sources tank perf |
| OBS transition   | **Cut, 0ms**                           | The pan _is_ the transition                |
| Overlay z-order  | Above all video                        | Art masks video lag/spill during pans      |
| Beat sync        | Shared wall-clock epoch                | Zero messages, zero drift, zero state      |
| Hole coordinates | Percentages of parent panel            | Art and window can't drift on resize       |
| Alerts           | Camera-space inset, never a panel      | A follow must not pan the viewer off game  |
| Scene detection  | `window.obsstudio`, websocket as backup| Survives a dead socket; measured same-frame |
| Source fit       | Crop to the hole's aspect, then stretch | No overspill to land in a neighbouring hole  |
| Mascot layer     | Own browser source, above the overlay   | A punched hole would put video behind its alpha |
| Mascot placement | Camera-space px in `placement.json`    | A pan must not drag it; no shared code       |
| OBS wiring       | `tools/obs-setup.py` over the websocket| The scene tree is derivable; clicking is not |

### Rejected, and why

- **Video inside the browser (WHIP → mediamtx → WHEP).** Worked, but added
  encode→decode→re-encode generation loss, frame-pacing judder, and a whole
  service to babysit. Killed once we realised the overlay can have holes and the
  video can just sit behind them.
- **Hybrid (browser video during pan, native at rest).** Solved the quality
  problem but needed every panel rect hardcoded twice. Obsolete for the same reason.
- **OBS Move plugin as the animation engine.** Fixed easing presets; can't author
  overshoot → settle → shake. May still be used as a _failsafe_ snap (see §6).
- **Per-panel browser sources.** Solved the oversized-source problem but split
  connective art (gutters, halftone, speed lines) across boundaries. Unnecessary
  once we went back to a single 1920×1080 source.
- **three.js for the page itself.** Canvas rendering kills the DOM geometry
  pipeline; you'd hand-roll 3D→screen projection for no real gain on a flat page.

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
name. `mascot/placement.json` maps a scene to a camera-space spot, and a scene
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
| 1   | start | video | 64, 64     | 2360 × 1180 | −1.0° | **fit** | Standby   |
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

---

## 6. Reliability

Failure modes and guards:

| Fails                            | Result                           | Guard                                                              |
| -------------------------------- | -------------------------------- | ------------------------------------------------------------------ |
| Animation/websocket dies mid-pan | Frozen between panels — dead air | On disconnect, Move filter snaps to a known-good panel             |
| Unknown panel ID sent            | Pan to nowhere                   | Validate against config; unknown = no-op, never a jump             |
| Browser source white-screens     | White box                        | `background: transparent` + art beneath, degrades to a still panel |
| Fonts fail to load               | Fallback stack, wrong look       | Self-host `.woff2` locally                                         |
| Source missing at launch         | Black hole                       | Startup preflight checks all sources exist                         |
| Beat drifts                      | Out of sync pulses               | Immune — wall-clock math, no state                                 |
| Alert flood (raid)               | Minutes of stacked insets        | Serial queue, min gap, collapse to `×N` above threshold            |
| OBS launches, no scene change yet| Overlay sits on an unknown panel | `getCurrentScene()` is null when nested — seed from `GetSceneList` |
| Mascot bridge not up at OBS launch| Sprite sheet 404s, mascot never appears | Boot fetch retries with backoff for ~8 min; heals when the bridge starts |
| Source resolution changes mid-stream| Fill crop goes stale, source letterboxes | Sizes re-read on every scene change |

**Panic key (mandatory).** One Stream Deck button that instantly snaps to the
gameplay panel at exact resting coordinates. No easing, no queue, no server state.

### OBS settings

- Browser source **1920 × 1080 exactly**. Never larger.
- **Uncheck** "Shutdown source when not visible".
- **Uncheck** "Refresh browser when scene becomes active".
- Settings → Advanced → **enable Browser Source Hardware Acceleration**.
- Transition: **Cut, 0ms**.

### Recording

Source Record plugin records each source independently and simultaneously:
gameplay clean, cam clean, program mixed. Editing sources stay raw.
Real ceiling is encoder sessions — mix NVENC and QuickSync/x264 across outputs.

---

## 7. Build order

1. ✅ Mockup — page, panels, pan curve, coordinate readout
2. ✅ Panel art — Start, BRB, End, Chat, Cam, Gameplay + 3 art panels
3. ✅ OBS scene structure + websocket enabled — verified with `obs-test.html`
4. ✅ Overlay connects & authenticates — v5 auth proven, `obs-test.html` identifies
5. ✅ Scene change → pan — `overlay.html`, both paths wired _(confirm in OBS)_
6. ✅ Punch holes + push rects to sources — `overlay-sources.html`
6b. ✅ Mascot — scene-aware placement, `mascot/` + `mascot/placement.json`
6c. ✅ One-command OBS wiring — `tools/obs-setup.py`
7. ⬜ Failsafes + panic key
8. ⬜ Alert layer + queue, Streamer.bot / EventSub feed
9. ⬜ Self-host fonts, go live

---

## 8. Open / unresolved

- Intel board is **placeholder art**. Needs real hand-drawn assets.
- BPM is hardcoded to 120. Should it follow actual playing music, or stay fixed?
- Websocket transforms aren't frame-synced to OBS's render tick — very fast moves
  may jitter. Mitigate: tick at 120 Hz, keep the fastest stage above ~80ms, or send
  a one-frame-ahead predicted rect.
- **`getBoundingClientRect()` returns an axis-aligned box.** Mid-pan the page is
  rotating, so a hole's AABB is larger than the hole. At rest it's exact (the page
  counter-rotates the panel square to the frame), and `OBS_BOUNDS_SCALE_OUTER`
  plus the mask hides the overspill during a pan. If it ever reads badly, send
  `rotation` with the transform and derive the unrotated rect.
- ~~**`Brb` is a source in `COMIC` that no hole maps to.**~~ Resolved by dropping
  it. It was not theoretical: sitting enabled at 1280×720 in the middle of the
  canvas, it showed through the Standby hole on START for the left 456px of that
  window. `obs-setup.py --prune` removes strays like it; `--check` names them.
  Any source in COMIC that no hole maps to will do the same thing.
- **A source may still be pulled between two visible holes on a fast switch.**
  `chooseWinners` decides from the *resting* transform, so mid-pan a hole that
  will lose the source still shows it. Invisible at 980ms; worth knowing if the
  pan is ever shortened.
- Overlay and the existing Stream Deck project should merge into one service; both
  already speak obs-websocket.

---

## 9. Working agreement

- **One step at a time.** Wait for confirmation before the next.
- **Questions get answers, not code.** Only produce updated code when a change is
  explicitly asked for.
- **No "it can't be done."** Find the loophole and explain how, while naming the
  real costs honestly.
- Communication: direct, terse, no generic advice.

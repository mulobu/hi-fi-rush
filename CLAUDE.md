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
└── Game      (Game Capture on Windows; macOS Screen Capture on macOS)

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
├── .skirt-n/s/w/e  gutter + halftone, AROUND the page   never masked
├── .page-under  gutter + halftone, page rect only    MASKED
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

**Unused sources are parked off-canvas, never disabled.** `SetSceneItemEnabled`
false deactivates the source, and coming back is not free: a game capture
re-hooks its target, a capture device reopens — hundreds of ms to seconds of
black the next time that hole is punched. `Chat` was switched off on every view
but CHAT, and `Game` on exactly two, CHAT and CAM (chat's camera starts past
x=3490; the game panel ends at 3464), so every switch out of chat paid for a
re-hook. `syncVisibility` now moves unused items to top-left `(canvas + 200)`
instead: every pixel off-canvas, so they still cannot show through a hole they
do not own, while staying hooked and still feeding Source Record. Enable is sent
only for an item OBS reported disabled, so a source switched off by hand comes
back once rather than being fought over every pan.

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

Resulting punch sets, read back off OBS rather than reasoned about: `start` →
Cam + Game · `chat` → Chat + Cam · `game` → Game + Cam · `cam` → Cam · `end` →
Cam + Game · `brb` → Game + Cam. `brb` was documented here as Game only, on the
grounds that the brb panel gave its webcam hole up to the mascot — but the game
panel's `Cam` hole clips the top-right corner of the BRB view by about 14 × 47
canvas px, wins the source unopposed, and has been punched there all along.
Harmless at that size; the fix, if it ever matters, is a minimum-area floor in
`chooseWinners` rather than moving the panel.

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

**The skirt must exceed the worst bleed *during a pan*, not at rest.**
`.page-under` overhangs the page by `PAGE_SKIRT` so a fitted panel showing past
the page edge shows gutter, not video. Resting bleed per panel: `chat` 1672 page
px (it sits at scale 0.33), `end` 249, `brb` 166, everything else under 60 —
which is what the old skirt of 2000 was sized for, and it was wrong. A pan
interpolates its transform components independently, so the camera passes
through views wider than either endpoint, and the overshoot easing carries it
~4.8% past the target on top of that. Stepping every ordered pair through the
real easing puts the peak at `cam` → `chat`: **2187 page px at 550ms in**, 187
past the skirt — a 54px band of bare canvas along the frame edge, mid-pan, on
every switch into CHAT. `start` → `chat` and `brb` → `chat` exposed 41 and 40px.
That was half of the black-on-switch; the other half is source parking, below.

2500 clears every pan. Skirt is **3000** — headroom, and a whole number of 30px
halftone tiles. Undersize it and that band goes transparent, exposing black and
any `SCALE_OUTER` overspill.

**The skirt is four bands around the page, not one rectangle behind it.** Only
the page can contain a cut — every hole is inside a panel and every panel inside
the page — so only the page rect needs a mask, and a mask forces its own
composited layer. Bands keep the masked element at 7680 × 4320 instead of
13680 × 10320.

The shape that must never come back is a single element at `inset: -SKIRT`. It
covers the page as well as the overhang, and being unmasked it seals every cut
in `.page-under` back up: no video anywhere, on any scene. It renders perfectly
and looks like the punch code broke. The guard is a structural assertion rather
than an eye: at each punched hole's centre, walk `elementsFromPoint` and require
that nothing painting an opaque background arrives unmasked. Page and skirt are
both whole numbers of 30px halftone tiles, so every band's dot grid is in phase
with the page's and the seams do not show.

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

**Vertical canvas — measured, not assumed.** Verified on OBS 32.2.2 /
obs-websocket 5.7.4 / Windows 11 with Aitum Vertical Canvas, by creating a
throwaway scene, transforming an item in it, and deleting it again:

- Aitum builds on OBS 32's **native** canvas API — the binary calls
  `obs_canvas_create`, `obs_canvas_enum_scenes`, `obs_canvas_get_scene_by_name`.
  It is a first-class libobs canvas, not a parallel implementation, which is why
  the standard websocket API sees straight into it. `GetCanvasList` reports
  `Main` 1920 × 1080 and `Aitum Vertical` 1080 × 1920.
- The whole chain works there: `GetSceneList`, `CreateScene`, `CreateSceneItem`,
  `SetSceneItemTransform`, `GetSceneItemTransform`, `RemoveScene`. The transform
  read back exact. **The punch pipeline can drive the vertical canvas** — this
  was assumed impossible on the grounds that no scene-item request takes a canvas
  parameter, which is true of the documented schema and false in practice.
- A source may be referenced from both canvases at once. The scene items are
  independent, so a vertical item's transform and the `COMIC` item's transform
  cannot fight, and `syncVisibility`'s off-canvas parking reaches only `COMIC`.
- Aitum registers **no websocket vendor**. It looks up `obs_websocket_api_get_ph`,
  but eight plausible vendor names all came back "No vendor was found by that
  name". Nothing needs one; the standard API is enough.

**Two traps, both of which fail silently:**

- **`canvasName` is ignored.** `GetSceneList {canvasName: "Aitum Vertical"}`
  returns **Main's** scene list — no error, no warning. Anything keyed on the
  name reads and writes the wrong canvas while looking entirely correct. Only
  `canvasUuid` scopes. That uuid is random per collection — Main's is the
  constant `6c69626f-6273-…` (`libobs` in ASCII), the vertical one is not — so it
  must be discovered from `GetCanvasList` every run and never cached to disk.
- **Vertical scenes are unreachable by `sceneName`.** Name lookup resolves within
  Main only, and the error says so out loud: *"No source was found by the name of
  `X` within the canvas `Main`."* Everything vertical is addressed by `sceneUuid`.
- **`GetCurrentProgramScene` ignores `canvasUuid` too**, returning Main's scene.
  Between this and `canvasName`, the rule is: a canvas argument is honoured on
  `GetSceneList` and `CreateScene` and silently dropped everywhere else, so
  never assume one took.

**Rename the plugin's scene; never create one.** `CreateScene` with a
`canvasUuid` works — libobs takes it, `GetSceneList` returns it — and the scene
is nevertheless **invisible in the Aitum dock**, which means it can never be put
on air, which means its sources never activate and the vertical overlay never
boots. Nothing errors anywhere. The cause is that Aitum's `config.json` stores
only `current_scene` and no scene list, so the dock enumerates the canvas once at
load and thereafter tracks only what its own UI created.

`SetSceneName` on the plugin's default scene is the way in. The uuid is
preserved, so the renamed scene stays whatever the canvas already had on air —
which on a fresh canvas is exactly the scene you wanted. `--vertical` renames
when there is a single scene to rename, creates only when the canvas is empty,
and says so loudly in that case because a created scene needs an OBS restart
before the dock re-enumerates and lists it.

**The dock click cannot be verified, only inferred.** `SetCurrentProgramScene`
refuses a non-main scene, `GetCurrentProgramScene` ignores `canvasUuid` and
reports Main's, and none of the plugin's 14 hotkeys switches a scene. What *is*
observable is `GetSourceActive` on `OverlayV`: inactive means VCOMIC is not on
air, because a scene's sources only activate when it is. That is what the script
checks, rather than printing a warning it cannot substantiate.

**The vertical canvas has ONE scene and never switches.** `SetCurrentProgramScene`
refuses outright — *"The specified scene is not from the main canvas and cannot be
set as the program scene"* — so no script can put `VCOMIC` on air, and since
`GetCurrentProgramScene` ignores the canvas there is no way to read back which
scene is on it either. That would be a problem if the vertical side needed six
trigger scenes the way COMIC does. It does not: `vertical.html` reads the **main**
canvas's program scene and pans itself, so one Stream Deck press moves both pages
and the vertical canvas just sits on `VCOMIC` forever. Selecting it in the Aitum
dock is a once-ever click, which `--vertical` reports because it cannot perform or
verify it.

**Naming carries across canvases.** OBS shares one source namespace globally and a
scene is a source, so the vertical host scene is `VCOMIC`, not a second `COMIC`,
and the vertical browser source is `OverlayV`. `Game` / `Cam` / `Chat` are the
*same inputs* referenced from both canvases; the scene items are independent, so
the two overlays cannot fight over a transform.

**`OverlayV` must not reroute audio.** Alert audio rides the horizontal `Overlay`
(§4). A second browser source with "Control audio via OBS" ticked puts every alert
sound into the mix twice.

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
| Unused sources   | Parked off-canvas, left enabled        | Disabling costs a capture re-hook — black on the way back |
| Mascot placement | Camera-space px in `placement.json`    | A pan must not drag it; no shared code       |
| OBS wiring       | `tools/obs-setup.py` over the websocket| The scene tree is derivable; clicking is not |
| Vertical output  | Second canvas, Aitum Vertical plugin   | Base resolution is per-profile — resizing kills the overlay |
| Vertical addressing | `canvasUuid` / `sceneUuid`, never names | `canvasName` silently resolves to Main |
| Vertical geometry| Its own page and `PANELS`, same engine | 16:9 panels cannot be reframed into 9:16    |
| Encode           | Hardware encoder, `--encoder auto`     | CEF is already carrying a 7680×4320 transform |
| Encoder settings | Left alone — yours                     | Not in the profile ini, and not a fact about the overlay |

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

**The vertical mascot needed no code.** `DeerV` is a second browser source at
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

`DeerV` is last in the stack for the same reason `Deer` is last in COMIC: above
the overlay, because a punched hole is a transparent rectangle and would put live
video behind the mascot's own alpha instead of comic art.

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
| 3   | game  | video | 64, 2312   | 1800 × 3200 | 0.5°  | **fill** | Game, Cam |
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

Its two windows stack — `Game` at 4%, 7%, 92% and `Cam` at 16%, 42%, 68%, both
16:9 against the 1770 × 3170 content box, bottoming out at 63.4% so the last third
carries art and the tag. That is the Shorts composition, built from the multi-hole
machinery the horizontal `game` panel already uses. Neither is `bare`, so unlike
the horizontal page no cut nests inside another and `mergeCuts` has nothing to do.

**Skirt is 1500**, not 3000. Derived the same way — every ordered pair stepped
through the real easing — peaking at `end` → `start`, **1061 page px at 549 ms**.
It is less than half the horizontal figure because the vertical panel scales are
uniform; there is no 0.33-scale `chat` outlier to pan through. 1500 is 41%
headroom and 50 whole halftone tiles; the page is 144 × 256.

The simulator that produced both numbers reproduces the horizontal page's
documented `cam → chat` peak to the decimal, which is why the vertical figure is
trusted rather than guessed.

Punch sets, read back off the built page rather than reasoned about: `start` →
Cam + Chat + Game · `chat` → Chat + Game + Cam · `game` → Game + Cam · `cam` →
Cam · `end` → Cam · `brb` → **nothing**. `brb` punching nothing is the point —
the mascot frame is drawn art with comic behind it, and no source is close
enough to claim a hole there, so the whole view is ink.

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
| Source deactivated between scenes| Capture re-hooks — black hole for up to seconds | Never disabled; parked off-canvas instead |
| Pan passes through a wider view than either end| Transparent band past the skirt | Skirt sized from the simulated pan, not the resting frame |
| Vertical scene not on air in the Aitum dock| `OverlayV` never activates, so it never connects | `--vertical` reports it; the websocket can neither set nor read it |
| Vertical overlay boots before its sources are added| Holes punched over nothing | `loadItemIds` rebinds every 3s while any managed source is missing |
| Vertical scene created rather than renamed | Invisible in the Aitum dock, so it can never go on air | `--vertical` renames the plugin's own scene, keeping its uuid |
| Vertical canvas not showing VCOMIC | Vertical overlay never boots at all | Inferred from `GetSourceActive` on `OverlayV` — it cannot be read directly |
| Fresh profile encodes with x264 | CPU contends with CEF's transform — dropped frames | `--encoder auto`; a run without it still reports the software encoder |
| Deprecated encoder ID in the profile | Works, until the OBS release that removes it | Renamed on any ordinary run — same encoder, current spelling |

**Panic key (mandatory).** One Stream Deck button that instantly snaps to the
gameplay panel at exact resting coordinates. No easing, no queue, no server state.

### OBS settings

- Browser source **1920 × 1080 exactly**. Never larger.
- **Uncheck** "Shutdown source when not visible".
- **Uncheck** "Refresh browser when scene becomes active".
- Settings → Advanced → **enable Browser Source Hardware Acceleration**.
- Transition: **Cut, 0ms**.
- Video encoder: **hardware**, on both the stream and recording outputs.
  `obs-setup.py --encoder auto` asks OBS which ones it registered and picks the
  best — the GPU supporting NVENC and OBS having loaded it are different facts.
  Bitrate, preset and tuning stay yours; they live in `streamEncoder.json`,
  which no websocket request reaches.

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
6d. ✅ Vertical canvas — `vertical.html`, `--vertical`, `DeerV` + vertical placement
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
  canvas, it showed through START's video hole for the left 456px of that
  window. `obs-setup.py --prune` removes strays like it; `--check` names them.
  Any source in COMIC that no hole maps to will do the same thing.
- **A source may still be pulled between two visible holes on a fast switch.**
  `chooseWinners` decides from the *resting* transform, so mid-pan a hole that
  will lose the source still shows it. Invisible at 980ms; worth knowing if the
  pan is ever shortened.
- Overlay and the existing Stream Deck project should merge into one service; both
  already speak obs-websocket.
- **The vertical page layout is undesigned.** The landscape `PANELS` cannot be
  reframed — `game` is 1.735:1, and fitting that into 9:16 leaves ~68% dead
  frame. Vertical needs its own page size, panel set, skirt sizing and pan
  curve. Same engine, all-new geometry.
- **Which canvas drives the pan is unsettled.** The vertical overlay should
  follow the *main* canvas's scene, so one Stream Deck press moves both. That
  argues for the websocket `CurrentProgramSceneChanged` path rather than
  `window.obsstudio`, whose behaviour inside an Aitum canvas is unmeasured.
- A second 1080×1920 encode is another encoder session. §6 already names
  encoder count as the real ceiling.

---

## 9. Working agreement

- **One step at a time.** Wait for confirmation before the next.
- **Questions get answers, not code.** Only produce updated code when a change is
  explicitly asked for.
- **No "it can't be done."** Find the loophole and explain how, while naming the
  real costs honestly.
- Communication: direct, terse, no generic advice.

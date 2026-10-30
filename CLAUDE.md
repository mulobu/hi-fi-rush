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
├── Browser   (Window Capture of Chrome)  in Game's hole while unmuted
├── Game      (Game Capture on Windows; macOS Screen Capture on macOS)
├── Tts       (Browser 64x64, off-canvas)  chat TTS audio, draws nothing
└── Discord   (Application Audio Capture)  audio only

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

**The browser borrows Game's hole; mute is the switch.** `Browser` is a window
capture of Chrome with no hole of its own in either page. While it is
**unmuted**, `feed()` resolves every `Game` hole to `Browser`, so the browser
fills exactly what the game would have filled — on GAME, and where the game
panel bleeds into START, BRB and END — and `Game` parks; muted, it is the other
way round. No scene, no pan, no new panel: the hole changes feed in place, and
`chooseWinners` is untouched because it still decides per `h.src`. Mute was
chosen over a filter because it is *already* the switch for the sound — the
page goes on air with its audio and comes off with it — and because the deck
(`set-input-mute`, state from the action) and OBS's own mixer can both flip it
and read it back. The price is that muting the browser's sound always takes
its picture with it; a fader at −∞ is how to show it silent. Both pages
subscribe to Inputs events for `InputMuteStateChanged` and ask `GetInputMute`
on connect; unknown, missing or removed counts as muted, so the browser never
reaches the stream on a guess. `Browser` sits directly above `Game` and under
`Cam`, whose window lies inside the game panel. It is not in either page's
`managed` set — a VCOMIC without it is complete, and must not keep the vertical
rebind loop spinning — but it is parked and re-enabled like a managed source.
`obs-setup.py` creates it disabled, muted, parked, then enabled: a fresh item
lands at 0,0 above `Game`, and neither page hears about it before its next
scene change. Driven end to end on 2026-10-25 on GAME: unmuted, `Browser` took
`Game`'s exact rect on both canvases (1903 × 1090 horizontal, 977 × 550
vertical) and `Game` parked; muted, the reverse. The deck's `BROWSER` button is
the same mute — cyan `BROWSER ON AIR` while unmuted.

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
- Aitum 1.6.4 answered to **no websocket vendor**: eight plausible names all
  came back "No vendor was found by that name". **Restream's 1.2.0 does** —
  `aitum-vertical-canvas` answers `version` and `status` (measured 2026-10-23),
  and the source registers `start_streaming`, `stop_streaming`,
  `save_backtrack` and more. Nothing in this repo calls it yet.

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

**The control surface is Macro Deck 3, not an Elgato Stream Deck.** Elgato's
mobile app caps the free tier at six keys, and six scenes leave nothing for the
mutes, the camera or the panic key. Macro Deck is Apache-2.0, unlimited keys,
and serves a web client the phone opens over the LAN — so "Stream Deck" earlier
in this document means the control surface generically, not the hardware.

It is configured over **Macro Deck's own loopback admin API**, not by editing
its files: `MacroDeckHost.exe` publishes a pre-authenticated REST API on
127.0.0.1 (port in `%LOCALAPPDATA%\Temp\macro-deck-host.port`), and the
profile JSON under `%APPDATA%\MacroDeck` belongs to the running host, so
writing it underneath is unreliable the same way editing a scene collection
under a live OBS is. `POST /api/actions/options` resolves the live scene and
input lists, which is how a button is wired to a name that actually exists.

**Deck buttons read their state from the action, not from a variable.** OBS
publishes 21 variables through Macro Deck — scene, streaming, recording, FPS —
and **none** for per-input mute or per-source visibility, so a variable binding
cannot drive those. Actions flagged `isStateProviderAction` declare their own
state set instead (`set-scene` → inactive/active, `set-input-mute` →
unmuted/muted, `set-source-filter` → disabled/enabled, each with
`unavailable`), and the button names one of its own action blocks as the
authority. Cycle-on-press is off on every one: otherwise a press advances the
button's look locally and then fights the real state coming back from OBS. The
deck therefore shows what OBS reports, never what it was told — and greys out
to `unavailable` if the websocket drops rather than lying about it.

**The camera kill switch is a filter on the `Cam` input, not a hidden scene
item.** `CAM OFF` is a `color_filter_v2` with `color_multiply: 0`, toggled by
`set-source-filter`. The obvious build — `set-source-visibility` on `Cam` in
`COMIC` — fails twice over, and both failures are silent:

- **It misses the vertical canvas.** Scene items are independent per canvas
  (above), so hiding `Cam` in `COMIC` leaves `VCOMIC` still showing the camera.
  The deck cannot fix that by hiding it in `VCOMIC` too, because a vertical
  scene resolves only by `sceneUuid` and the deck addresses sources by name —
  `VCOMIC` is absent from every scene list it can see, and custom values are
  refused. A filter belongs to the *input*, so one toggle covers both canvases.
- **It does not survive a pan.** `syncVisibility` re-enables a managed item it
  finds disabled, on every scene change, in `overlay.html` **and**
  `vertical.html`. Measured: the visibility toggle reverted on the first
  switch; the filter held across `GAME → CHAT → BRB`.

`color_multiply: 0` is opaque black. **Not `opacity: 0`** — that makes the hole
transparent and shows whatever sits below `Cam` in the stack, which in COMIC is
`Game`. The trade-off is that an input filter blacks every use of that input,
including a Source Record clean-cam capture (§6).

`obs-setup.py` asserts the filter and deliberately never touches its *enabled*
state — that is a live toggle the deck owns, and a setup run must not decide it.

**The camera grade is off, and opt-in.** Taken off `Cam` on 2026-10-17, and
`do_grade_filter` now runs only with `obs-setup.py --grade`.
Without the flag a setup run neither adds a `GRADE` filter nor removes one, so
it cannot come back by itself and a grade added by hand is left alone.
`tools/cam-grade.py` and the generated LUTs stay, so `--grade` restores it
exactly as described below. Everything that follows holds whenever it is on.

**The camera grade is a LUT, and it must sit above the kill switch.** A "Sam
Kolder" grade is a split tone — teal shadows, amber highlights — over a faded
curve, and OBS's Color Correction filter cannot do it: it has one saturation
and one hue shift, and a split tone moves shadows and highlights in *opposite*
directions. That needs a lookup table, so `GRADE` is a `clut_filter` on the
`Cam` input reading `assets/luts/kolder.cube`.

Order is the load-bearing part, not presence. `CAM OFF` multiplies every pixel
by zero to get opaque black; the grade lifts the black point *off* zero,
because a faded toe is half of what the look is — the table maps `0,0,0` to
`0.020 0.070 0.090`. Put the grade second and the kill switch stops killing:
black goes in, teal comes out, and the camera reads as a dim tinted rectangle
rather than off. `do_grade_filter` therefore pins `GRADE` to index 0 and lets
`CAM OFF` follow it, and asserts that ordering on every run rather than only at
creation. Verified by screenshotting the input with `CAM OFF` on over the
grade: a uniform black frame that PNG-compresses to under a kilobyte.

Two settings are deliberately left alone after creation, the way `CAM OFF`'s
enabled state is. `clut_amount` is the taste dial — it blends the table against
the raw image live, which is how the look softens without regenerating
anything — and `image_path` is accepted as given so long as it names a file in
`assets/luts`, so picking `kolder-strong.cube` by hand survives a setup run.
`SetSourceFilterSettings` merges, so repairing a broken path does not reset the
amount. Only a path that is missing or outside that directory is repaired.

The `.cube` is **generated, not committed**: ~860 KB of derived text against a
deterministic generator, with `assets/*` gitignored, so a fresh clone runs
`tools/cam-grade.py` on the first setup instead of carrying a blob in the
history. Three looks sit on one axis — `soft`, `standard`, `strong` — differing
only in lift, highlight rolloff, contrast and tint strength. A LUT cannot do
vignette, halation, grain or bloom; those are spatial, need neighbouring
pixels, and are a real fraction of the look. They want an overlay image or a
shader plugin.

**One capture per application, and no Desktop Audio.** Since 2026-10-25 the
game comes from Game Capture's own **Capture Audio**, the browser from its
window capture's, and Discord from `Discord`, an Application Audio Capture of
`Discord.exe` sitting in COMIC like `Tts` (a source reaches the mix only from a
scene on air). All three are Windows process loopback: one process tree's
sound, whichever endpoint it plays to. So notifications and music stay off
stream, and the endpoint flapping in §8 stops mattering — that was Desktop
Audio's failure, and with `use_device_timing` on it once restarted the source
three times in an evening (*"Source Desktop Audio audio is lagging (over by
683315.27 ms) at max audio buffering"*). `Game`'s sound follows whatever window
`Game` hooks, so a new game is picked in one place.

**Desktop Audio has to be gone first; the order is the load-bearing part.** It
captures the whole output, which already holds the game, the browser and
Discord, so a per-app capture beside it sums the same sound twice from two
independent clocks — a comb filter whose notches sweep as the offset drifts. It
sounds like the game vibrating underwater rather than like a duplicate, which is
why it sends you to the encoder settings instead of here. Measured once, when
Game's Capture Audio was ticked beside Desktop Audio mid-stream: armed 17:18:32,
and the beta path dropped and re-armed itself 22 seconds later. `do_audio`
therefore asserts Capture Audio *both ways* — on while no `wasapi_output_capture`
exists, off while one does — and adds `Discord` only in the first state, warning
in the second.

The websocket cannot disable a global audio device. OBS's own "Disabled" takes
the source off its output channel, which no request does; `RemoveInput` is not
the same thing, and what it leaves on a channel is not worth finding out
mid-stream. So that one step is a dropdown for the user: Settings → Audio →
Global Audio Devices → Desktop Audio → Disabled. Mute is **not** asserted on
any of these — it is a live toggle the deck owns.

Two edges, not yet measured: whether `Discord` hooks by itself when Discord
starts after OBS (OBS re-finds the window, by design), and whether a Discord
minimised to the tray, with no window, can be found at all. Discord's own join
and message sounds come from Discord.exe and do reach the stream.

**The mic denoiser is NVIDIA Noise Removal where OBS can run it, RNNoise where
it cannot, pinned to the top of the chain — and opt-in, with `--denoise`.**

**Why it went opt-in, 2026-10-29.** Viewers said the voice "breaks a lot" — the
voice only, nothing else on stream. The logs ruled out the device (three USB
drops on 10-28, all before going live) and the stream (4 lagged frames in
663k). What was left was the denoiser at both of its most aggressive settings:
with VAD on, a syllable the model misreads is not turned down, it goes to
digital silence (−156 dBFS measured in the gaps). It was taken off and put back
the same evening at **0.7 with VAD off**. That this stops the breaking is **not
yet measured**. A run without `--denoise` neither adds a denoiser nor removes
one — the way `--grade` treats `GRADE` — so the live one is left alone.

The noise that matters at
this desk is the keyboard and the mouse, and RNNoise is built for steady noise —
fan, hum, room. Measured 2026-10-25 on the USB Condenser Microphone: clicks left
RNNoise at −36 to −22 dBFS, the same range as speech (−23 to −31), so nothing
downstream that decides by level can tell them apart. Over 40 s of typing,
alternating the two every 2 s, frames above −60 went 139 → 62 and the loudest
0.1 → −15.6 dBFS. Better, **not silent**. Clicks *under speech* are not
measured: a meter cannot separate them from the voice, so that one is by ear.
Those figures are at intensity 1.0 (the ceiling) with `vad` on — NVIDIA's own
voice detection, which quiets the gaps between words. `NV DENOISE` is an
`nvidia_audiofx_filter`, method `denoiser`, now 0.7 with `vad` off, which lets
more keyboard through by an amount not yet measured. It runs on the GPU, so it
costs the game a little rather than costing CEF's CPU — and it dies with the
GPU: a driver reset leaves it logging `Denoiser run failed` every frame until
OBS restarts (§6).

OBS registers that kind only when NVIDIA's Audio Effects SDK redistributable
for the GPU is installed — an RTX card, Windows, a download from NVIDIA's
Broadcast page (v1.6.1 Blackwell for the RTX 5070 here) — and OBS looks for it
once, at launch, logging `[NVIDIA Audio Effects:] enabled` or `redistributable
not found`. No request installs it, so it is a manual step like disabling
Desktop Audio, and the kind list decides at setup time which denoiser is
primary. `NV DENOISE`'s settings are taste after creation, except a method that
removes no noise at all: `dereverb` alone takes out room echo and leaves the
keyboard, which reads as the filter silently failing, so setup warns.

The fallback is RNNoise, not Speex. OBS ships one Noise Suppression filter with
two engines behind a dropdown. Speex subtracts a fixed noise profile and turns
robotic as you push it; RNNoise is a small recurrent net trained on
speech-plus-noise, so it holds a voice together while taking out fan hum and
room. It costs more CPU, which is a real cost here — CEF is already carrying a
7680 × 4320 transform — but it is a fraction of a core against a browser source
doing compositing.

`suppress_level` is the Speex slider and RNNoise ignores it, so `DENOISE` sets
`method` and nothing else. There is nothing to tune on that path, which is half
of why a script should assert it. The method is written explicitly rather than
left to the default: v2 *does* default to `rnnoise`, but only where librnnoise
was compiled in, and v1 defaults to `speex`. A hand-set `speex` survives a
setup run the way a hand-picked LUT does — it is the documented fallback for a
machine that cannot carry RNNoise, so it is a choice, not a fault. Only a
method that is neither gets repaired.

**Exactly one denoiser on.** Two in a row thin the voice, each taking a little
more of what the other left. Enabled state stays the user's, with two
hand-overs the script makes because it is only finishing its own move: creating
`NV DENOISE` switches an enabled `DENOISE` off, since it is the replacement; and
an `NV DENOISE` that cannot run — the SDK uninstalled, the collection imported
onto a machine with no RTX card — loads as a filter that passes audio through
untouched, so a `DENOISE` left off behind it is switched back on. Both are
pinned, the primary at index 0 and the other directly under it, so the fallback
is already above anything that lifts level the day it comes on. Built against a
stand-in for OBS over twelve chains: a check run reports the same moves a real
one makes, and a second run changes nothing.

Position is asserted for the mirror of the reason the grade's is. Anything that
lifts level — gain, a compressor, an upward compressor — lifts the noise floor
with it, so suppression running after one is undoing work the chain just did,
and a gate below it reads a cleaner signal and can sit closer to the voice.
A compressor or gain filter added by hand is exactly the case the pin is for —
`COMPRESS`'s +20 dB once was.

**The OBS 32.2.2 restart bug did not reproduce.** A forum thread on 32.2.2
reports the NVIDIA filter working when added and silently passing audio after
OBS restarts, cured only by deleting and re-adding it. One graceful restart
here, then NV toggled every 2 s against no filter: median −156 dBFS on, −33
off. One sample, so the check is worth knowing, and it needs no one talking:
with NV on and nothing said, the floor sits near −150 or below; a dead filter
reads the raw room.

**Under the denoiser: `EQ`, `COMPRESS`, `LIMIT`, in that order, at the bottom
of the chain.** Rebuilt 2026-10-29 in the order the streaming guides agree on —
suppression, EQ, compressor, limiter last. The research was meant to come from
Reddit, which refuses both the search tool and the built-in browser; the guides
give the same chain. `do_mic_dynamics` creates the three in list order and
asserts their order on every run, placing from the last one up so each move
leaves the ones below it alone; settings are written at creation only. Built
against a stand-in for OBS over eight chains: check and real runs report the
same moves, and a second run changes nothing.

- **`EQ` is the low-pass, as near as OBS gets.** OBS ships no low-pass filter.
  `basic_eq_filter` is a 3-band EQ of shelves; its `high` band at −6 dB softens
  the top end without the steep cut that would take the consonants with it. It
  is the dial for how soft the voice sounds — −20 is close to a hard cut, 0 is
  off. Its crossover frequency is not confirmed from OBS's source. A true
  low-pass, or the 80–100 Hz high-pass every guide also wants, needs a VST such
  as ReaEQ through `vst_filter`, the path `VOICE GATE` proved (§3, Rejected).
- **`COMPRESS` is back, gentler: 3:1 from −18, 6 / 60 ms, +4 makeup.** The
  guides' starting point, with the makeup held small on purpose: the case
  against it below still holds. What it does to the voice-to-click gap at
  these settings is **not measured**.
- **`LIMIT`** is unchanged: −3 dB, last, because anything under a limiter can
  push past its ceiling and the ducks read the very end of the chain. Through
  NVIDIA the voice already peaked at −3.1 dBFS.

`DENOISE` and `VOICE GATE` were removed rather than left off. `VOICE GATE`'s
blob format is in §3, Rejected, should it ever come back.

**Why the makeup stays small.** `COMPRESS` (4:1 from
−36, +20 makeup) went in on 2026-10-25 to hold the voice steady for the ducks —
the voice wanders 8 dB on posture alone — and the same evening the mic "started
catching noise". A compressor can only narrow the gap between the voice and
what the denoiser leaks: it turns the voice down where the leftovers sit below
its threshold, and below the threshold it is flat gain, so the makeup lifts
them by the full 20 dB. Over RNNoise, clicks near −42 came out near −22, as loud
as speech. Over NVIDIA, from a take the same night: speech frames' median sits
8.8 dB above the leftover clicks' median, and would sit 4.2 above it compressed;
against the loudest tenth of clicks, 2.3 would become 0.6. Turning the makeup
down is no fix — it is the mic fader by another name. That took
`COMPRESS` out from 2026-10-25 to 2026-10-29, with the duck's own ratio
absorbing the voice's wander meanwhile (below). Only position is asserted on an
existing `COMPRESS`, so an older collection may still carry the +20 one.

No gate: the denoiser already takes the floor out between words, and a gate on
top is the classic cause of clipped word endings. It would not catch the
keyboard either: an expander under `DENOISE` (−50 RMS, 3:1, 5 / 200 ms) changed
nothing measurable over 40 s of A/B typing, because clicks leave RNNoise as
loud as the voice.

**The mic is found by input kind, never by name.** `Mic/Aux` is OBS's own label
for the first global audio device — localised, and not a source this script
creates; it comes off the profile, not out of COMIC. So `find_mic` matches
`wasapi_input_capture` / `coreaudio_input_capture` and falls back to the name
only to break a tie. Two capture devices and no `Mic/Aux` is not guessable, and
it says so rather than filtering the wrong one.

**A mic saved against a device that no longer exists is repointed.** OBS saves
the mic as a WASAPI endpoint id, and Windows issues a new one when it reinstalls
the device. 2026-10-29: after the reboot that followed a live NVIDIA driver
install (§6), the USB Condenser Microphone came back as `{651cc1af-…}` with OBS
still holding `{c9702c9a-…}`, and the mic was silent on a live stream. OBS
logged `failed to start` once. The source stayed enabled, unmuted and active,
so over the websocket only the meter looked wrong. `do_mic_device` repoints it
when exactly one real device is offered, and names the candidates otherwise.
`default` would survive a re-id, but it follows whatever Windows makes the
default recording device — and the `Logi C270` has taken over before (§8).

**Three ducks, all sidechain compressors.** `DUCK` on `Game` and on `Browser`,
keyed off the mic, **3:1 from −38 dB, 50 / 1000 ms**. Its depth is
**modelled**: game content moves too much to read a duck straight off its
meter, so the mic's 50 ms meter peaks were run through OBS's own sidechain
envelope (peak, one-pole attack and release in linear amplitude). Fitted
2026-10-25 to a take through `NV DENOISE`, speech and clicks told apart by
shape — a run of 200 ms or more peaking above −30 is speech, one or two
isolated frames a click: a median 11 dB duck while talking, mostly 6 to 15, 22
at a shout; isolated clicks leave the game alone at the median and dip it about
5 dB at the loudest tenth, back inside a second.

The ratio is doing the compressor's old job. Depth is the key's excess over the
threshold times (1 − 1/ratio), and the voice swung 24 dB between phrases in that
take (run peaks −27 to −3): 32:1 passes all of the swing — a 28 dB hole at a
shout, 3 dB under a quiet phrase — where 3:1 passes two thirds. 2:1 is steadier
still and dipped the game a third deeper on clicks. The 50 ms attack is for
clicks as well: a click is ~10 ms, so its envelope rises a fifth of the way,
while speech reaches full depth ~50 ms late, which is nothing against a game.
**Twelve seconds of speech and 22 clicks** — a short take, worth a second one
over a real game. The old 32:1 from −24 was tuned against `COMPRESS`'s +20, and
once that was off it gave a median 3.5 dB.

That a duck is *real* is measured: in an earlier take `Game`'s RMS fell with the
modelled duck, −35 / −45 / −55 dB at none / 1–6 / 6+ dB, so the sidechain does
reach Game Capture's audio. `Game`'s fader was −6 dB for that take and is 0 now;
faders are taste and never asserted, so a fresh machine starts at 0. The old
`DUCK` on Desktop Audio, −38 dB off the raw mic, dug 15 to 22 dB. `DUCK DISCORD`
on `Game`, keyed off `Discord`, 3:1 from −24 dB, 10 / 600 ms — meant as about
8 dB under a friend at normal volume, **untuned: no Discord audio in the take**.
Discord itself never ducks: dipping friends whenever you speak makes cross-talk
unintelligible. A sidechain reads its key at the end of the key's chain, after
the denoiser, so fan and most keys never trigger it; a muted key ducks nothing
(the compressor zero-fills a muted sidechain). Only the sidechain is asserted
after creation; threshold, ratio, attack and release are yours to tune. The old
Desktop Audio `DUCK` goes with Desktop Audio. Alerts ride `Overlay` and TTS
rides `Tts`, so neither ducks. The duck only happens in OBS's mix, so you cannot
hear it on your own speakers. Check it in a recording.

Enabled state is **reported, not asserted**, the way `CAM OFF`'s is, bar the
two denoiser hand-overs above. Toggling a denoiser off to hear the difference is
a legitimate live action and a setup run must not overrule it — but a mic with
no denoiser on is worth one warning line.

**Chat TTS: a bridge reads chat, Piper speaks it, a browser source plays it.**
`chat/chat-bridge.py` reads Restream chat, filters and queues it, synthesises
each line with Piper, and pushes it over Server-Sent Events to `chat/tts.html`,
which the `Tts` browser source in COMIC plays. Every chat line, as *"{name}
says: {message}. On {platform}."*, filtered, one at a time, on stream and in
your ears. The deck's `TTS` button mutes the `Tts` input. `start.py` runs the
bridge alongside the mascot's.

**The page reports the end of each line, and that is what keeps them
serial.** The bridge announces line *n*, the page fetches `/line/n.wav`, plays
it, and POSTs `/done/n` on `ended` or `error`; the reader thread waits on that
before the next. A page that never answers costs the clip's length plus 5 s.
No page connected — OBS closed — and a line is dropped, not queued for an OBS
that may never come.

**`Tts` is `file://`, and the first build proved why.** It was served by the
bridge, like the mascot, and obs-setup created the source while no bridge was
running: the first load failed, and a browser source never retries a page that
failed to load, so the page's own reconnect code never existed to run. 20 s,
zero connections. Loaded from disk the page always boots, and only its
`EventSource` needs the bridge — which retries by itself, so start order stops
mattering. The bridge sends `Access-Control-Allow-Origin: *` on `/events`,
without which a `file://` page's stream is refused in silence. Measured after
the switch: connected within 2 s, six lines played end to end.

**Monitor and Output does not double the line.** The fear was the comb filter
of the game audio all over again: the monitor plays to the default endpoint,
`Desktop Audio` captures that endpoint, and every line reaches the stream
twice. Measured with six lines, monitoring on and then off: the `Tts` and
`Desktop Audio` meters correlate at −0.06 and 0.04 — no echo either way. OBS
says why in its own log: *"Device for 'Audio Output Capture' source Desktop
Audio is also used for audio monitoring. Deduplication logic is being applied
to all monitored sources."* `do_tts` asserts Monitor and Output and parks the
item off-canvas; mute is the deck's and never asserted. With Desktop Audio gone
the question closes for good: the monitor plays from obs64.exe, and every
capture left is of some other single application.

**Piper normalises every line to full scale** — peak 1.00 on the `Tts` meter,
louder than anything else in the mix — so the bridge synthesises at volume 0.5
(−6 dB) and the OBS fader is the taste dial rather than an emergency brake.

**OBS's browser cannot speak.** Measured on OBS 32.2.2 (Chrome 127) with a
throwaway scene: `speechSynthesis.getVoices()` lists David, Mark and Zira after
`voiceschanged`, and `speak()` then reports `end` in the same millisecond, never
`start`, with nothing on any meter — twice, the second time with an explicit
voice. A stub that looks like it works. Speech is therefore synthesised outside
CEF and played in a page as `<audio>`, which "Control audio via OBS" does route.

**The feed is the embed's own socket, not Restream's documented API.** The API
(`wss://chat.api.restream.io/ws`) wants a registered OAuth app, a one-hour
access token, and a refresh that needs the client secret and rotates the pair —
a credential service to run for a read-only feed. The `Chat` source already
carries an embed token, and the embed reads chat with it from
`wss://backend.chat.restream.io/ws/embed?token=…`, read out of its own bundle.
Same actions (`connection_info`, `event`, `heartbeat`), same `eventPayload`
fields, so moving to the documented API later is a URL and a token, not a
rewrite. The cost: it is undocumented, and when Restream moves it the bridge
loops on reconnect and the stream goes quiet with no error anywhere else.
Heartbeats arrive in pairs about 45 s apart (measured over 3.5 minutes), so the
bridge reconnects after 95 s with no frame of any kind — two missed pairs.

The token is **read from OBS, never stored**: the bridge asks for the `Chat`
input's URL on every connect. One copy — regenerate the embed in Restream, paste
it into `Chat`, and the next reconnect follows. `--export` already scrubs
`token` by name.

**Platform comes from the event type.** Restream numbers event types per
platform, so `eventTypeId` alone names the source: 4 Twitch, 5 YouTube, 7
YouTube Super Chat, 25 Kick. The author field is not consistent — Twitch
`displayName` (nullable, then `name`), YouTube `displayName`, Kick `username` —
and one fallback order covers all three. Verified against a real message from
each of Twitch and Kick: a Kick author carries nothing but `id` and `username`,
so a lookup keyed on `displayName` alone would read every Kick viewer as
nobody. TikTok and Instagram are not Restream chat sources at all, so the
vertical audience's comments are never read.

**A reconnect replays nothing.** Measured: after two messages, a fresh
connection received only `connection_info` and heartbeats. A bridge restart
mid-stream therefore never re-reads old chat — and anything said while it is
down is lost, not queued.

**YouTube attaches only while a broadcast is live.** Off air its
`connection_info` is `error: youtube_livechat_ended`; Twitch and Kick report
`connected` regardless. Whether YouTube attaches by itself when a broadcast
starts after the bridge, or needs a reconnect, is not yet measured.

**There is no deletion signal.** The embed's code has no delete action, so a
mod removing a message cannot stop it being read. Moderation happens before
speech — the filters and blocklist — or not at all.

**What gets read.** Everything, minus: bots (the payload's own `bot` flag),
`!commands`, your own accounts, and anything the blocklist hits in the text
*or the sender's name*. Own accounts are one squashed entry, `thedeepeffect` —
letters and digits only — so the Kick handle, the Twitch/YouTube
`thedeepeffect_` and a YouTube channel name like "The Deep Effect" all match it.
What survives is cleaned for the ear: URLs become "a link" (three or more,
"some links"), Kick's `[emote:id:NAME]` tokens and every emoji are dropped,
`@mentions` lose the `@`, underscores become spaces (espeak reads `_` as
"underscore"), runs of four or more of a character become three, a word
repeated four or more times becomes three, and the whole is cut at 200
characters on a word boundary — 13 s of lessac. A line with no letters or
digits left is skipped rather than read as "X says: ."

`chat/blocklist.txt` is whole-word, so `ass` blocks neither `class` nor
`assess`. It sees through stretched letters and the common swaps (`4 @`, `3`,
`1 ! |`, `0`, `5 $`, `7`, and `*` for any vowel — a self-censored "f*ck" is
still read out as one), a trailing `*` makes an entry a prefix, and spaces in
an entry match any run of separators. Spaced-out letters are not caught —
nothing cheap catches "f u c k" without flagging ordinary sentences. It is
recompiled when its mtime changes, so it can be edited mid-stream.

The swaps have one trap: they let digits alone satisfy a word. `ass` becomes
`[a4@*]+[s5$]+[s5$]+`, and "455 damage" matches it. A word entry therefore
never counts on an all-digit match — digits, not letters, because `@$$` must
still count — and entries with no letters of their own (`1488`, an emoji) are
compiled separately and matched as written.

**Seeded: 634 entries** — slurs and harassment, sexual terms and general
swearing, in English and romanized Hinglish. 152 are curated: prefix stems
for the slurs, the TTS-specific phonetic evasions ("knee grow" reads as
harmless text and comes out of the speaker as the slur), harassment phrases,
and Hinglish spellings and abbreviations (`bsdk`, `bkl`, `tmkc`). The rest are
derived from LDNOOBW's `en` and `hi` lists (CC BY 4.0, attributed in the file)
**minus 39 entries that are ordinary chat** — "this boss sucks", "hardcore
mode", "escort mission", "how to kill the boss", *chod* ("leave it"),
*chakke* (cricket sixes), *maal* (stuff), *bc* (because), *mc* (Minecraft).
Every removal is listed in the file with its reason, commented out, so a
stricter list is one `#` away. Tested against 56 messages that must be blocked
and 84 that must not, including the Scunthorpe set (`therapist`, `cockpit`,
`assassin`, `spicy`, `Pakistan`, `Essex`, `Gandhi`): all pass. Compiles in
~35 ms, matches in 0.03 ms a message. One accepted false positive:
stretched letters plus `shit*` also block "shiitake".

**The blocklist is gitignored, and required.** It is personal, and it is a
list of slurs — not something to publish with the repo. That makes it the one
chat file a clone does not have and nothing regenerates, so its absence is
loud everywhere: the bridge exits 2 at startup without it (`--no-blocklist`
overrides), `decide()` refuses to read anything if it is deleted or emptied
mid-stream, `start.py` names it and starts the mascot anyway, and
`obs-setup.py --check` warns. A filter that silently turns off when its list
goes missing is worse than no filter, because it looks like one.

**`start.py` is the one command.** Both bridges, then OBS if it is not open.
Each bridge's output is prefixed with its name; one that crashes after running
a while is restarted with backoff, and one that dies in its first 8 s is left
down — a missing file or a taken port does not get better on retry. The
bridges get their own process group, so the console's Ctrl-C reaches only the
launcher, which stops them itself; otherwise each would die of the same Ctrl-C
and be "restarted" on the way out. On Windows they also live in a job object
with `KILL_ON_JOB_CLOSE`, so however the launcher dies — Ctrl-C, the window
closed, Task Manager — the bridges die with it and never orphan holding a
port. OBS is launched detached from its own `bin` folder (it cannot find its
locale files otherwise) and outlives the launcher. First run builds
`chat/.venv` and fetches the voice, checksum verified.

**One line at a time, newest wins.** The feed never waits on Piper: lines go
into a queue a separate thread speaks from, and `play()` returns only when the
line has finished, which is what keeps it serial. Past five waiting, the
*oldest* is dropped, so a raid reads its first line and its last five rather
than ten minutes of backlog; a line that has waited over 60 s is stale and
dropped. Measured with a 20-line flood in 50 ms: line 00 spoken, 01–14
dropped, 15–19 spoken in order, never two at once.

**Windows' console encoding is a socket fault in disguise.** Redirected,
stdout is cp1252, and the first emoji in a chat line raises
`UnicodeEncodeError` — a `ValueError`, which the feed loop catches as a bad
frame and reconnects over, losing whatever was said meanwhile. stdout is
reconfigured to `backslashreplace`, and each line is handled inside its own
`try`, so a message that trips a bug costs that message and nothing else.

**Piper costs one thread, and capping it wrong is worse than not capping it.**
Measured on the 9800X3D with `en_US-lessac-medium`, 42 chat-shaped lines of
about 3.5 s of speech each:

| Mode | Per line, median / max | CPU per line | Cores busy |
| --- | --- | --- | --- |
| Uncapped | 54 / 98 ms | 0.45 s | ~8 |
| 2 CPUs, onnxruntime's default threads | 689 / 1256 ms | 1.44 s | 2, thrashing |
| 2 CPUs, 2 threads | 122 / 245 ms | 0.26 s | 2 |
| **1 CPU, 1 thread, below normal** | **125 / 266 ms** | **0.14 s** | **1** |

Restricting affinity without restricting onnxruntime's threads puts eight
threads on two CPUs: 13× slower and 3× the CPU of doing nothing. `PiperVoice.load`
exposes no thread count, so the bridge builds the `SessionOptions` itself. With
Piper synthesising back to back for 20 s — ~28× what a serial queue can ever
ask — OBS render time went 1.02 → 1.23 ms with 0 of 1202 frames skipped.
Resident ~145 MB, ~400 MB peak, 1.7 s to load once. No game was running and
nothing was encoding; the single below-normal thread is built to yield to a
game, which is design rather than measurement until a real stream checks it.

Piper is the one pip dependency in the repo, so `chat/` carries its own
`.venv` (gitignored, with `chat/voices/`) and `tools/` stays standard library.
The bridge imports nothing from `tools/` — it duplicates sixty lines of
websocket client so `chat/` can lift out into its own project the day a second
overlay needs it.


**Clips are timestamps, not a buffer.** The deck's clip button runs
`obs-setup.py --clip`, which appends one row to `clip-marks-YYYY-MM-DD.csv` in
the clip folder and does nothing else. The moment is cut afterwards from the
platform VOD or Restream's recording. No replay buffer runs, so nothing sits in
RAM waiting for a press that may never come, and a clip can reach back as far
as the VOD is kept rather than five minutes. The cost: nothing exists until the
stream is over and the recording is downloaded.

The date is the day the stream *started*, not the day of the press: the press
time minus the stream time minus the delay, or minus the recording time when
only recording. Streams here cross midnight — the marks at 00:02 and 01:05 on
2026-10-24 belong to one started at 22:39 the evening before — and naming by the
press would split one stream across two files. Two streams on one day share a
file. The single `clip-marks.csv` from before 2026-10-27 is left where it was.

A row is `time, vod, stream, delay, recording`. `vod` is the one to scrub to —
where what you were looking at when you pressed sits in the recording. It is
`stream + delay`, because libobs counts a frame when it *sends* it, after the
delay queue has held it back: OBS's stream time is what viewers are seeing, and
what you saw is `delay` further on. That ordering is read from libobs's source,
and the first delayed start bore it out: stopped 15 s into the countdown, OBS
logged *Total frames output: 0* against 12 520 drawn. Where `vod` lands in a
real recording is not yet checked. The counter itself is trustworthy — over
the 5 h 32 m stream of 2026-10-22, OBS's *Total frames output* sat within 0.7 s
of the wall clock. Give or take the few seconds Restream and the platform trim
off the start; a reconnect with the delay preserved adds its outage on top.
During the countdown after Start Streaming nothing has been sent, so a press
there gets the time and no position. `recording` is a local recording's
timecode, never delayed, so exact.

The press fails only if the row cannot be written. Excel locks an open CSV, so
a failed write prints the row to stderr rather than dropping it.

**The replay buffer is asserted *off*, in both output modes.** `RecRB` lives per
mode and only the active one is read, so a buffer left enabled in the inactive
section comes back the day the mode is switched. OBS reads `RecRB` only when it
builds its outputs at launch, so turning it off needs one restart; until then
`GetReplayBufferStatus` still answers, and setup says so. The vertical plugin's
backtrack is its own setting in its `config.json`, which OBS rewrites on exit —
reported, never written, and warned about while it is on. It is not only RAM:
**with backtrack on, the plugin sets `RecRB` true in both output modes every
time OBS loads it** and saves the profile. Measured — setup wrote both off, OBS
restarted with backtrack still ticked, and both were back on. The source is the
settings load in `vertical-canvas.cpp` (`!record_advanced_settings && (backtrack
|| …)`). Untick *Backtrack runs while streaming/recording* first, then assert.

**The stream is delayed 120 s, and the delay is RAM.** It was 300 until
2026-10-27, when it was cut by hand in OBS and the script followed. OBS holds
the delayed stream as encoded packets — about bitrate × delay, ~90 MB at
6 Mbps — well under the 300 s buffer it replaced. The delay is for its own
sake. `DelayPreserve` is on: a reconnect resumes where it
cut off rather than skipping ahead, so the VOD has no hole, at the price of the
delay growing by the outage. Stopping drains the full delay before the stream
ends; forcing it discards those minutes.

**The vertical stream inherits the main delay.** When the plugin creates its
stream output it checks `stream_advanced_settings`: off — the default, and the
only mode Restream's 1.2.0 settings dialog offers, which shows no delay field at
all — and it calls `obs_output_set_delay` with the main profile's
`DelayEnable` / `DelaySec` / `DelayPreserve`. Its own `stream_delay_*` in
`config.json` apply only with advanced settings on, and setup warns only in that
case. Read from Aitum's `vertical-canvas.cpp`; Restream's binary carries the
same keys and the profile-config call. Not yet measured on a stream. It also
means the vertical delay is another ~90 MB, so the two delays together hold less
than one of the dropped buffers did.

**With a delay, the vertical stream comes up a full delay late.** The plugin
starts it on OBS's *streaming started* event (`streaming_match_main`, the dock's
Autostart), and with a delay OBS fires that only when the countdown ends and the
main output actually connects — 120 s after Start. The vertical then runs its
own inherited 120 s countdown, so it goes live four minutes after the click,
never having captured the first two; once up, both run 120 s behind real time
and in step. Measured half: on a 15 s test the plugin logged *Main stream
starting* at the click and started nothing before the stop. The four-minute
figure follows from the source, not from a full run.

**`--go-live` starts both at the click, and the deck's GO LIVE runs it.** Main
first, then the vertical through the plugin's `start_streaming` vendor request,
scoped to the 1080 × 1920 dock by `width` / `height`. The plugin queues the
start onto the dock and answers before anything has happened, so each side is
confirmed by polling — `GetStreamStatus`, and the vendor's own `status` — rather
than taken from the reply. It cannot double-start the vertical: a delayed output
reports active from the click, and the plugin's start routine returns early on
an active output, so when the main countdown ends and Autostart fires it finds
the vertical already up. Without a delay an output is active only once
connected, and a second start could land mid-connect, so in that case the
vertical is left to Autostart.

Start-only, never a toggle: a side already live is left alone, because a
mis-press must never end a stream. On the deck it is a **long press** (Macro
Deck's `onLongPress`, 600 ms) for the same reason — with the delay a stray start
is two minutes of countdown to cancel, without one it is live. Built against a
stand-in for OBS, all nine branches; never pressed against the real one, since
that starts a stream.

**One OBS profile per Restream setup.** Restream keeps channels, titles and
categories per *setup* — `Default RTMP` and each RTMP setup beside it — and
each setup has its own key. A profile per setup therefore makes the game a
profile switch: categories are set once per setup on Restream, and OBS's
Profile menu picks which one goes out. The vertical follows for free. Restream's
plugin repoints the main output at `/horizontal` and sends the vertical to
`/vertical` on the *main profile's* key (log: `Horizontal stream url changed`),
and its own config holds no key at all.

**Only one profile may be connected to the Restream account.** Connect Account
fetches `api.restream.io/v2/user/streamKey`, the account's default key, and
`OAuthStreamKey::OnStreamConfig` writes it over whatever key the profile holds
(both read from OBS's source). So a connected profile is `Default RTMP` whatever
it was given, and every other profile is Disconnect Account → Use Stream Key.
The Restream docks come only with the connected one.

**Duplicate, never New.** Measured with a throwaway profile on 2026-10-27:
`CreateProfile` gives 1280 × 720 output under the 1920 × 1080 canvas, 30 fps,
Simple mode, x264, the delay off and no service, and its bitrate sits in
`streamEncoder.json`, which no request reaches. Profile → Duplicate copies all
of it, so creating a profile stays a click in OBS rather than something the
script does badly. The folder is not the name either — OBS made `zz-probe` into
`zzprobe` — so profiles on disk are matched by `[General] Name`.

**The script visits every profile.** Only the active profile is readable over
the websocket, so `do_profiles` switches to each, asserts canvas, delay, replay
buffer and encoder, and puts the original back. `SetCurrentProfile` answers
before the switch has happened, so `switch_profile` waits for
`CurrentProfileChanged`, which OBS fires at the end. A switch resets video and
rebuilds every output, and was otherwise harmless when measured: `Overlay`,
`OverlayV`, `Deer` and `DeerV` stayed active, the vertical canvas kept its
1080 × 1920, the main key came back unchanged, about a second a switch. Never
while anything is live: then the others are named, not visited. Shared keys,
more than one connected profile and differing encoder settings are compared
from disk, keys hashed and never printed.

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
| Vertical game bg | Navy + burst + chevrons, not `--ink`   | Its holes cover 40%, not 100% — ink is a black slab |
| Vertical safe zones | TikTok's 140/324/164, everywhere      | Restream fans one encode to every platform — the strictest wins |
| Right rail        | Windows cross it; text never does      | The action is centred, so a covered corner of footage costs nothing |
| Vertical tag position | Measured per panel at boot         | Six fit scales, one authored value — no constant clears all six |
| Vertical GAME stack | Cam above game, both full width      | Face top is where mobile eyes go; equal windows read as two panels |
| Encode           | Hardware encoder, `--encoder auto`     | CEF is already carrying a 7680×4320 transform |
| Encoder settings | Left alone — yours                     | Not in the profile ini, and not a fact about the overlay |
| Control surface  | Macro Deck 3, web client on the phone  | Free at any key count; Elgato caps the free tier at six |
| Deck wiring      | Macro Deck's loopback admin API        | Pre-authenticated on 127.0.0.1; its profile files are host-owned |
| Deck button state| The action, never a host variable      | OBS publishes no mute or visibility variable to bind |
| Camera off       | `CAM OFF` filter on the `Cam` input    | An input filter crosses canvases and survives a pan; a hidden item does neither |
| Clipping         | A timestamp row per press, cut from the VOD later | No RAM held for presses that never come; reach-back is the VOD's lifetime |
| Clip button      | `obs-setup.py --clip`, run by the deck | The deck cannot send OBS a hotkey, and a CSV append is not a deck action |
| Stream delay     | 120 s, preserved on reconnect; vertical inherits it | ~bitrate × delay in RAM, per canvas |
| Going live       | `--go-live` on a deck long press: main, then vertical by vendor | Autostart waits out the delay; a long press cannot be a stray tap |
| Game metadata    | One OBS profile per Restream setup; only one connected to the account | Categories live per setup; a connected profile always streams on the default key |
| New profiles     | Profile → Duplicate; the script checks every profile | A clean profile is wrong five ways, and its bitrate is out of the websocket's reach |
| Camera grade     | Off; `--grade` adds a `clut_filter` LUT above `CAM OFF` | Removed 2026-10-17. When on: a split tone moves shadows and highlights opposite ways; Color Correction is global |
| Grade LUT file   | Generated by `tools/cam-grade.py`      | 860 KB of derived text; deterministic, so a clone rebuilds it |
| Game audio       | Game Capture's own Capture Audio       | Follows the hooked window; nothing else on the PC reaches the stream |
| Discord audio    | `Discord`, Application Audio Capture in COMIC | Process loopback ignores which endpoint Windows picked |
| Desktop Audio    | Disabled by hand; per-app audio refused until it is | Two captures of one sound comb-filter; no request disables a global device |
| Browser on stream| `Browser` window capture in Game's hole while unmuted | One switch for picture and sound; no scene, no pan, deck and mixer both flip it |
| Mic denoise      | `NV DENOISE` 0.7, VAD off, pinned first; opt-in with `--denoise`, RNNoise where NVIDIA cannot run | At 1.0 with VAD a misread syllable goes to silence — "the voice breaks"; anything above it raises the floor it removes |
| Mic dynamics     | `EQ` high −6, `COMPRESS` 3:1 from −18 +4, `LIMIT` −3 last; no gate | The guides' order; the EQ is the nearest OBS has to a low-pass; makeup lifts leaked clicks by its full amount, so it stays small |
| Mic device       | Repointed when its saved endpoint is gone | Windows re-ids a device it reinstalls, and OBS then captures nothing without saying so |
| Ducking          | `DUCK` 3:1 from −38, 50 ms attack, on Game and Browser off the mic; `DUCK DISCORD` on Game | The ratio absorbs the voice swing no compressor now holds; a slow attack lets ~10 ms clicks pass; Discord, alerts and TTS never duck |
| Mic identity     | Found by input kind, name as tie-break | `Mic/Aux` is localised, and comes off the profile, not COMIC |
| Chat feed        | Restream embed socket, token read from `Chat` | The documented API is an OAuth service to run for a read-only feed |
| TTS engine       | Piper `en_US-lessac-medium`, 1 thread, below normal | OBS's `speechSynthesis` is a stub; uncapped Piper bursts 8 cores |
| TTS audio        | Its own `Tts` source in COMIC          | Own fader — the deck mutes TTS without muting alerts |
| TTS page         | `file://`, events from the bridge      | A browser source never retries a failed first load |
| TTS monitoring   | Monitor and Output                     | Measured: OBS 32 dedups it out of Desktop Audio |
| TTS blocklist    | Gitignored, required to start          | Personal and a list of slurs; a missing filter must be loud |
| Launching        | `start.py` — bridges, then OBS         | One command; a job object so no bridge orphans |

### Rejected, and why

- **Video inside the browser (WHIP → mediamtx → WHEP).** Worked, but added
  encode→decode→re-encode generation loss, frame-pacing judder, and a whole
  service to babysit. Killed once we realised the overlay can have holes and the
  video can just sit behind them.
- **Hybrid (browser video during pan, native at rest).** Solved the quality
  problem but needed every panel rect hardcoded twice. Obsolete for the same reason.
- **OBS Move plugin as the animation engine.** Fixed easing presets; can't author
  overshoot → settle → shake. May still be used as a _failsafe_ snap (see §6).
- **Replay buffers for clips.** Dropped 2026-10-23 for timestamps (§2): 300 s
  held in RAM on each canvas, all stream long, for presses that might never
  come. What it took to get right, should it come back: a buffer *enabled* in
  Settings is not *running*, and `SaveReplayBuffer` against a stopped one
  reports success. OBS and the vertical plugin both register
  `ReplayBuffer.Save` and the websocket reaches the plugin's, so one press
  needs `SaveReplayBuffer` *and* `TriggerHotkeyByName`. Macro Deck's synthetic
  keystrokes never reach OBS's hotkey hook in any of its three delivery modes,
  though all three report success. `StopReplayBuffer` is a one-way door — the
  buffer will not start again before an OBS restart, so any deck button for it
  must be start-only. And `AdvOut/RecRBSize` sat at 512 MB, which would have
  shortened clips silently above ~13 Mbps.
- **Per-panel browser sources.** Solved the oversized-source problem but split
  connective art (gutters, halftone, speed lines) across boundaries. Unnecessary
  once we went back to a single 1920×1080 source.
- **three.js for the page itself.** Canvas rendering kills the DOM geometry
  pipeline; you'd hand-roll 3D→screen projection for no real gain on a flat page.
- **A gate or expander for keyboard clicks.** Clicks leave RNNoise at −36 to
  −22 dBFS, the voice's own range, so a level detector cannot tell them apart:
  an expander at −50 RMS, 3:1, A/B'd every 2 s over 40 s of typing, moved
  nothing. OBS's expander also starts every sound from a −60 dB gain floor, so
  an attack slow enough to swallow a click swallows the first 10 ms of every
  word too (modelled from `expander-filter.c`).
- **werman's RNNoise VST2 with voice detection (`VOICE GATE`).** It decides by
  "is this speech", not by level, so it can mute a click as loud as a voice —
  and between words it did, to exact digital silence. Under speech the gate is
  open and the denoiser beneath it is the same RNNoise, so clicks pass; at VAD
  0.85 some slipped while silent too. Left in the collection, off, at VAD 0.95,
  and not asserted; it needs `rnnoise_stereo.dll` (v1.10, JUCE) in
  `%CommonProgramFiles%\VST2`. Its settings are a JUCE state blob: `chunk_data`
  is base64 of `copyXmlToBinary` — `VC2!`, a uint32 length, the APVTS XML, a
  NUL — and obs-vst applies it whenever `chunk_hash` is absent or matches.

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

### Socials

Paper cut-outs, one per platform, in `socials/*.svg` — scissor-faceted paper,
inked edge, taped, logo glued on with a hard shadow. Kick is `thedeepeffect`,
Twitch and YouTube share `thedeepeffect_`, Instagram is `@thedeepeffect__` —
three labels. `SOCIALS` is duplicated in `overlay.html` and `vertical.html`
(the pages share no code), so a handle change is two edits.

Each scene panel carries a `socials` entry. They are sized in **canvas px** via
`--u = 1 / restScale(p)`, because panels rest at 0.33× to 1.17× and page-px sizes
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
| Camera hidden as a scene item | Back on at the next pan, and vertical never hid at all | `CAM OFF` filter on the input — neither page touches filters |
| Deck button press races OBS's real state | Button lies about mute or camera | State comes from the action; cycle-on-press off on every button |
| Replay buffer left enabled in the other output mode | Back in RAM the day the mode is switched | `RecRB` asserted off in both modes |
| Vertical advanced stream settings turned on | Its own delay (0 by default) replaces the main one — vertical goes out 120 s ahead | Setup compares it against the main delay in that mode only |
| Today's `clip-marks-*.csv` open in Excel | The row cannot be written | Printed to stderr; the press exits non-zero |
| Clip pressed after midnight | Marks split across two days' files | The file is dated by the stream's start, not the press |
| Clip press during the delay countdown | Row has the time and no VOD position | Find it by clock time from when Start Streaming was clicked |
| Started from OBS's own button, not GO LIVE | Vertical goes live a full delay after the main | Use GO LIVE; Autostart only fires when the main countdown ends |
| GO LIVE pressed while already live | A toggle would end the stream | Start-only; each side already up is left alone |
| Vertical plugin swapped for one with no vendor | Main starts, vertical does not | `--go-live` exits 1 and says to use the dock |
| A per-app capture beside Desktop Audio | Every sound combs — a sweeping warble that reads as a bad encoder | `do_audio` keeps Capture Audio off and adds no `Discord` while any output capture exists, and says how to disable it |
| Default output endpoint changes mid-stream | Nothing — process loopback follows the application, not the endpoint | Desktop Audio removed |
| Browser item created at 0,0 | Desktop on stream until the next scene change | `create_browser`: disabled, muted, parked, then enabled; `--vertical` parks it in VCOMIC |
| Browser mute unknown — socket down, request failed, input removed | Would guess | Treated as muted: the game shows |
| A filter added under `LIMIT` by hand | Voice pushed past the ceiling | `do_mic_dynamics` moves `LIMIT` back to the bottom |
| A compressor or gain filter added above the denoiser | Suppression removes a noise floor the chain just lifted | `do_mic_denoise` pins both denoisers to the top on every run |
| Mic renamed, or the profile is not English | A name-keyed filter lands on nothing, silently | The mic is matched by input kind; an ambiguous match warns |
| Every denoiser switched off and forgotten | Mic goes out raw | Enabled state is reported, never overruled — one warning line when none is on |
| NVIDIA SDK missing — uninstalled, or the collection imported onto a machine with no RTX card | `NV DENOISE` loads as a passthrough; the mic goes out raw while the filter shows on | Setup warns, switches `DENOISE` on as the fallback and pins it first |
| SDK installed while OBS is running | No NVIDIA filter kind exists until a restart — OBS looks once, at launch | Restart OBS; its log says `[NVIDIA Audio Effects:] enabled` |
| Two denoisers on at once | The voice thinned twice over | Creating `NV DENOISE` switches `DENOISE` off; both on is a warning |
| NVIDIA filter dead after an OBS restart (32.2.2 forum report) | Mic raw while the filter shows on | Not reproduced here; with NV on and nobody talking the floor should read ~−150 dBFS |
| Compressor makeup over a denoiser that leaks clicks | Keyboard lifted to the voice's level | `COMPRESS` created at +4; an older one keeps its settings, so check it is not the +20 one |
| NV DENOISE at intensity 1.0 with VAD | A misread syllable drops to silence — viewers hear the voice break | 0.7 with VAD off since 2026-10-29 |
| Mic re-id'd by a driver reinstall or reboot | Mic silent while the source reads enabled, unmuted and active | `do_mic_device` repoints it when one real device is offered |
| GPU driver reinstalled under a running OBS (Windows Update did it 2026-10-29) | Every browser source blank — overlay, mascot, chat — while all report active; `NV DENOISE` dead | Restart OBS. The log says `Device Remove/Reset!`, then `gs_texture_open_nt_shared` about 100 times a second |
| Voice swings with posture and nothing compresses it | Duck depth swings with it — 28 dB at a shout, 3 under a quiet phrase at 32:1 | `DUCK` at 3:1 passes two thirds of the swing |
| Grade filter lands under `CAM OFF` | Kill switch returns lifted teal, not black | With `--grade`, `do_grade_filter` pins the grade to index 0 |
| Grade LUT missing on a fresh clone | Filter points at a file that is not there | With `--grade`, the `.cube` is generated by the setup run, not committed |
| Panel CSS copied from the horizontal page | A background sized for a full-panel hole renders as a black slab | Vertical holes cover 40% of `game`, so its background is drawn art |
| Art authored against the full 1080 × 1920 | Tags and type land under the platform UI — invisible, and fine in OBS | `fitTagsToSafeArea()` measures each panel at boot; art held inside `SAFE_RIGHT` |
| Two conic gradients on one vertical panel | Moiré resolves to a grey wash on a downscaled phone, reading as a paint failure | Only one radial layer on vertical `game` — the static `.burst` |
| Restream moves the embed socket | TTS goes silent — nothing errors in OBS | The bridge logs every disconnect and retry; the documented API is the fallback, same payloads |
| Chat socket dies without a close frame | Feed stops silently, the way a sleep or router drop presents | Silence watchdog: no frame in `SILENCE_LIMIT` and the bridge reconnects |
| Embed token regenerated in Restream | Bridge holds a dead token | Token is re-read from `Chat` on every connect, never stored |
| A mod deletes a message | It is read aloud anyway | No deletion signal exists — filters and the blocklist run before speech |
| Piper capped by affinity alone | 13× slower and 3× the CPU of no cap at all | Thread count set in `SessionOptions`, not just affinity |
| Raid floods chat | Minutes of backlog read long after the moment | Queue of five, oldest dropped; stale after 60 s |
| Emoji in chat, stdout redirected on Windows | `UnicodeEncodeError` reads as a bad frame — socket dropped, chat lost | stdout `backslashreplace`; every line handled in its own `try` |
| `Tts` created before its bridge is up | Page never loads; TTS silent until someone refreshes the source | `Tts` is `file://`; only its EventSource needs the bridge, and it retries |
| Blocklist missing on a fresh clone | Chat read aloud unfiltered | Bridge refuses to start; `start.py` and `--check` both name the file |
| Launcher killed hard | Bridges orphaned, ports held, next start says "already running" | Windows job object with `KILL_ON_JOB_CLOSE` |
| OBS closed while the bridge runs | Lines synthesised for nobody pile up | No page connected = line dropped, never queued |
| Two profiles on one stream key | Switching profile changes nothing — same Restream setup | `do_profiles` compares key hashes across every profile |
| A duplicated profile left connected to Restream | It streams on `Default RTMP` whatever key it holds | Warned when more than one profile is connected |
| Profile made with Profile → New | 720p output, 30 fps, x264, no delay, OBS's default bitrate | Every profile is visited and warned; encoder settings compared with the active one |
| Setup run while live, with several profiles | A switch would rebuild every output mid-stream | Other profiles are named, never visited |

**Panic key (mandatory).** One deck button that instantly snaps to the
gameplay panel at exact resting coordinates. No easing, no queue, no server state.
Still unbuilt; the deck has a free cell waiting for it.

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
6e. ✅ Control surface — Macro Deck 3, nine state-aware buttons, `CAM OFF` filter
6f. ✅ Camera grade + audio path — `tools/cam-grade.py`, `do_grade_filter`, `do_audio`
    (grade since made opt-in with `--grade`, and off)
6g. ✅ Vertical real estate — safe zones, face-top `game`, measured tag pass
6h. ✅ Chat TTS — `chat/chat-bridge.py`, Piper, `Tts` source, deck `TTS` mute,
    `start.py`
6i. ✅ Per-app audio, `Browser` in Game's hole, mic chain, three ducks, deck
    `GAME AUDIO` / `BROWSER` / `DISCORD` — `do_audio`, `do_mic_dynamics`,
    `do_duck`, `feed()` in both pages. Live 2026-10-25; open edges in §8
6j. ✅ NVIDIA Noise Removal on the mic, RNNoise as the fallback —
    `do_mic_denoise`; ducks refitted to 3:1 from −38, `COMPRESS` dropped. Live
    2026-10-25; open edges in §8
6k. ✅ One OBS profile per Restream setup — `do_profiles` visits and compares
    every profile; profiles themselves made with Profile → Duplicate
6l. ✅ Mic chain rebuilt — `EQ` (the low-pass), `COMPRESS` +4, `LIMIT`;
    `NV DENOISE` at 0.7 / VAD off and opt-in with `--denoise`; `do_mic_device`.
    Live 2026-10-29; open edges in §8
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
- **The deck is not in the repo.** `obs-setup.py` rebuilds the whole OBS side on a
  new machine, but the nine buttons live only in `%APPDATA%\MacroDeck`, so a fresh
  install gets an empty deck. Committing the profile needs one thing solved first:
  its flows embed *this* machine's OBS configuration GUID, which differs on every
  install, so a straight copy imports nine buttons pointing at nothing. Rewrite it
  at import the way `--export` already tokenises `{{REPO}}` and `{{HOME}}`.
- Overlay and deck should merge into one service; both already speak obs-websocket,
  and Macro Deck has a Streamer.bot integration the alert layer (§4) will want.
- ~~**The vertical page layout is undesigned.**~~ Designed: its own 4320 × 7680
  page, own `PANELS`, own 1500 skirt, and §5's safe-zone pass. The landscape
  `PANELS` were never reframable — `game` is 1.735:1, and fitting that into 9:16
  leaves ~68% dead frame.
- **The vertical `game` info band is drawn art, not information.** Canvas
  1352–1596 currently holds the chevron strip, one scrawl and the tag. It is
  sized and clear of platform chrome precisely so the alert layer (§4) and a
  LATEST readout can claim it, which is step 8. Until then the band is honest
  empty page rather than a placeholder that has to be torn out.
- **Only `game` was recomposed.** The other five vertical scenes were pulled
  inside the safe box but their compositions are untouched: `brb` punches
  nothing and `cam`, `start` and `end` sit at 20–22% coverage, well under the
  40–50% the vertical material gives the primary zone. Whether that matters
  depends on how long those scenes are actually on air.
- **The safe margins are dated.** 140/324/164 is TikTok as of 2026; platform
  chrome moves, and an expanded description on Shorts already pushes the bottom
  to ~400. `SAFE_*` are constants in one place for that reason.
- ~~**Which canvas drives the pan is unsettled.**~~ Settled: the *main* canvas
  does. `vertical.html` subscribes to `CurrentProgramSceneChanged` with **no**
  `canvasUuid`, which is Main's program scene, and pans itself off that — so one
  deck press moves both pages and `VCOMIC` never switches. `window.obsstudio` is
  still wired underneath as the secondary path.
- **The mic chain was rebuilt live on 2026-10-29, and none of it is measured.**
  Whether 0.7 with VAD off stops the voice breaking, how much more keyboard it
  lets through, and what `COMPRESS` at +4 does to the voice-to-click gap all
  want one take: normal speech and typing over a real game, recorded and played
  back. Clicks *under speech* are still by ear. The ducks were fitted to the old
  chain — NV at 1.0, no compressor — so with clicks reaching the key louder,
  expect the game to dip on typing until they are refitted; check the depth in
  a recording, since the duck is only in OBS's mix. And what still gets
  through is acoustic: the mic hears the
  keyboard about as loud as the voice, and on a desk stand it hears it through
  the desk as well. An arm or shock mount, 10–15 cm from the mouth, is the fix
  no filter is — and a closer mic would narrow the voice's 24 dB swing that the
  duck now has to absorb.
- **The audio switch is live; three edges are not yet seen.** 2026-10-25: Desktop
  Audio disabled, setup applied, both overlays refreshed, mic and voice duck
  tuned from two meter takes, deck rewired (`DESKTOP` → `GAME AUDIO` on `Game`,
  new `BROWSER` row 1 col 1 and `DISCORD` row 1 col 2; row 1 col 4 stays for the
  panic key). The browser switch was driven end to end — mute from the
  websocket and from the deck's own `run-flow` — and read back: `Browser` took
  Game's exact rect on both canvases, `Game` parked, and the deck button went
  cyan `BROWSER ON AIR` within 2 s. Not yet seen: `DUCK DISCORD` with a friend
  actually talking; `Discord` hooking a Discord started after OBS; the browser switch
  watched on an actual stream. `obs/comic-scenes.json` predates all of it —
  re-export after OBS next quits cleanly.
- ~~**Windows keeps moving the default output endpoint.**~~ No longer reaches
  the stream once Desktop Audio is disabled: every capture left is process
  loopback, which follows an application, not an endpoint. History: `Realtek HD
  Audio 2nd output` invalidated, *"Default output device changed"*, then the
  monitor's `VG270 M3 (NVIDIA High Definition Audio)` initialised three times in
  four seconds — and after the next OBS restart it booted on the monitor and
  stayed. `Desktop Audio` is on `default`, so it follows.

  **Pinning it to a named device is the wrong fix, and it is the obvious one.**
  A WASAPI loopback captures what is rendered *to that endpoint*. Pin OBS to the
  Realtek while Windows routes to the monitor and the result is not a dropout,
  it is a **silent stream** — an endpoint rendering nothing, captured faithfully,
  with no error anywhere in OBS. `default` is never silently wrong: it always
  follows what you are actually listening to, at the cost of a dropout per flip,
  and `use_device_timing: false` already stops that flip restarting the source.

  So the endpoint stayed on `default` and `preflight` watched it, reading the
  resolved device out of OBS's log. That check was removed with the move off
  Desktop Audio on 2026-10-25. The mic can still flap the same way — it did once, `Logi C270`
  invalidated and `USB Condenser Microphone` took over — and that is still
  repaired in Windows Sound, by disabling the device you never talk into.
- With `--grade`, the grade bakes into a Source Record clean-cam capture, the
  same trade-off §2 already names for `CAM OFF`. If clean cam ever matters, the
  grade has to move off the input and onto a scene item, which costs it the
  vertical canvas.
- A second 1080×1920 encode is another encoder session. §6 already names
  encoder count as the real ceiling.
- **Chat TTS has two unmeasured edges, and both need a live stream.** Whether
  YouTube attaches by itself when a broadcast starts after the bridge, or needs
  a reconnect; and whether Piper's below-normal thread really yields to a
  CPU-heavy game — measured only against an idle desktop. Monitoring double
  capture, the third, is measured and closed (§2).
- **TTS reaches the vertical stream only if its output carries the main mix.**
  `Tts` is in COMIC alone; whether the vertical plugin's output takes the same
  audio tracks is a setting on that output, not checked here.
- **No profile on a pasted key has streamed yet.** Whether Restream's plugin
  does its `/horizontal` swap for a profile that is not connected to the
  account is not measured; the vertical depends on it. First stream on one:
  look for `Horizontal stream url changed` in the log, and the vertical live on
  that setup's channels. Also unseen: whether the duplicate's Disconnect Account
  leaves the original's Restream docks logged in.
- **GO LIVE has not been pressed for real.** First use: hold it, check that
  both the main button and the vertical dock show a countdown, and that the
  vertical goes live with the main rather than two minutes after.
- **The clip mark's `vod` column is not yet checked against a recording.** That
  OBS's stream time excludes the delay is measured (§2); that Restream's
  recording starts at the first sent frame is not. First stream with the delay
  on: press once on a scene switch, then check that row's `vod` lands on the
  switch in the Restream recording. If it is 120 s late, the delay is already
  counted and `vod` should be `stream` alone.

---

## 9. Working agreement

- **One step at a time.** Wait for confirmation before the next.
- **Questions get answers, not code.** Only produce updated code when a change is
  explicitly asked for.
- **No "it can't be done."** Find the loophole and explain how, while naming the
  real costs honestly.
- Communication: direct, terse, no generic advice.

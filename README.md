# Overlays

Stream overlays for OBS, one per show. The shared parts — OBS wiring, chat TTS,
the mascot, the tools — live at the root; each overlay's own design lives in
`overlays/<name>/`. Scene and source names are the same in every overlay, so
one deck drives every show.

| Overlay | What it is |
| --- | --- |
| [overlays/hi-fi-rush/](overlays/hi-fi-rush/) | Hi-Fi Rush inspired. The whole stream is one comic page; each OBS scene is one panel, and switching scenes pans the camera across the page |
| [overlays/_template/](overlays/_template/) | Not a show: the plain, working starting point for a new overlay. Its README has the steps |

| Path | What it is |
| --- | --- |
| [CLAUDE.md](CLAUDE.md) | Architecture, decisions, reliability — everything overlays share |
| [core/](core/) | The page code every overlay shares: OBS link, punched holes, the pan. [core/README.md](core/README.md) is what a page must define |
| [docs/adr/](docs/adr/) | Decision records, one dated file per decision |
| [docs/OBS-SETUP.md](docs/OBS-SETUP.md) | Scene/source wiring in OBS, by hand |
| [tools/obs-setup.py](tools/obs-setup.py) | The same wiring, asserted over obs-websocket |
| [tools/obs-test.html](tools/obs-test.html) | Scene-detection probe used to verify §2 |
| [tools/hero-asset.py](tools/hero-asset.py) | Turns a look-around video into a sprite sheet |
| [start.py](start.py) | One command that starts everything a stream needs running |
| [chat/](chat/) | Chat TTS: reads Restream chat aloud through OBS, with Piper |
| [mascot/](mascot/) | Cursor-following, scene-following mascot browser source; sprite sets in `mascot/sets/` |
| [assets/socials/](assets/socials/) | Platform icons every overlay's socials row loads |

Inside each overlay folder:

| Path | What it is |
| --- | --- |
| `overlay.html` | The live overlay. Point the browser source here |
| `vertical.html` | The same engine, 1080×1920, for the vertical canvas |
| `chat.css` | How the chat embed is styled to sit in the overlay's art |
| `mascot/placement.json` | Where the mascot sits, per scene — only if the overlay has one |
| `mascot/placement-vertical.json` | The same, in the vertical canvas's pixels |
| `obs/scenes.json` | Exported scene collection, credentials stripped |
| `CLAUDE.md`, `README.md` | The overlay's concept, art direction and panel layout |

---

# Set up on a new machine

Everything OBS needs is derivable, so there is a script for it. What is *not*
derivable is anything tied to the hardware in front of you — which camera,
which monitor, which window. The script creates those sources and leaves them
for you to point at something.

## 1. Install

| | macOS | Windows |
| --- | --- | --- |
| OBS 31+ | [obsproject.com](https://obsproject.com) | same |
| Python 3.8+ | preinstalled | `winget install Python.Python.3.12` |

obs-websocket 5 ships inside OBS; there is nothing extra to install. Nothing
you run needs `pip install` by hand — the scripts are standard library only,
and the one dependency in the repo, Piper for chat TTS, is installed into its
own `chat/.venv` by `start.py` the first time it runs (step 7). `ffmpeg` is
needed only to build a *new* sprite sheet, never to run the overlay.

**OBS 32+ if you want the vertical output**, plus the Aitum Vertical Canvas
plugin — step 9. 31 is enough for everything else.

On Windows substitute `py -3` for `python3` in everything below. `python3` is
not a command there: Windows ships a `py` launcher instead, and the bare names
`python` / `python3` hit a Microsoft Store stub that installs nothing and exits
0, which looks like a script that did nothing rather than one that never ran.

## 2. Clone it

```bash
git clone <your-repo-url> Overlays
cd Overlays
```

## 3. Turn on the websocket, once

OBS → **Tools → WebSocket Server Settings → Enable WebSocket server**. Leave
the generated password alone. `obs-setup.py` reads it out of OBS's own config
file, so you never have to copy it anywhere.

While you are in Settings:

- **Video** → Base *and* Output resolution **1920×1080**. Every hole rectangle
  the overlay pushes is in canvas pixels, so this is load-bearing, not taste.
- **Advanced** → **Browser Source Hardware Acceleration** on.

## 4. Build the scene collection

Each overlay lives in its own OBS scene collection, named in its
`overlays/<name>/overlay.json` ([ADR 0003](docs/adr/0003-one-scene-collection-per-overlay.md)):

```bash
python3 tools/obs-setup.py --overlay hi-fi-rush
```

`--overlay` switches OBS to that overlay's collection first, or creates it if
it does not exist — never while anything is live. Without it, the script
builds whichever overlay the active collection belongs to. `--no-profiles`
builds the collection and leaves every profile alone.

It creates the `COMIC` host scene, the six trigger scenes, the video sources
and the browser sources — `Overlay`, `Mascot` if the overlay has one, and
`Tts`, the chat TTS
player, parked off-canvas with its audio on "Monitor and Output"; puts them in
the right stacking order; squares the
nested `COMIC` up to the canvas in every trigger scene; and sets the transition
to **Cut**. Run it as often as you like — it only reports and repairs what is
wrong, and it never deletes or overwrites a source you already have.

**Audio is one capture per application.** First, in OBS: Settings → Audio →
Global Audio Devices → **Desktop Audio → Disabled**. The websocket cannot do
that one, and until it is done the script refuses the rest, because Desktop
Audio already carries everything below and each sound would go out twice. Then
the script:

- turns on **Capture Audio** on `Game` (the game's sound follows whatever window
  `Game` captures) and on `Browser`
- adds `Discord`, an Application Audio Capture of `Discord.exe`
- builds the mic chain: `EQ` (high band −6 dB, the nearest OBS has to a
  low-pass) → `COMPRESS` (3:1 from −18, +4 dB) → `LIMIT` at −3 dB. The EQ's
  high band is the dial for how soft your voice sounds
- repoints the mic if Windows has given it a new device ID since OBS saved it,
  which it does when it reinstalls the device. The mic then reads enabled and
  active while capturing nothing
- ducks `Game` and `Browser` under your voice and `Game` under Discord — about
  11 dB and 8 dB to start, yours to tune by ear. Discord never ducks.

Notifications, music and anything else on the PC stay off stream. Discord's own
join and message sounds do not — turn them off in Discord if you do not want
them heard.

**`Browser` puts a browser window on stream in place of the game.** It is a
window capture of Chrome, created muted. **Unmute it and it takes over the game
window**, picture and sound, in every scene and on both canvases; mute it and
the game is back. No scene of its own, no pan. Mute is the switch, so it works
from the deck or from the speaker icon on `Browser` in OBS's mixer. Want the
picture without the sound? Pull its fader down instead of muting.

```bash
python3 tools/obs-setup.py --check
```

is the same pass with nothing written, exiting non-zero if anything is off. It
also runs a read-only preflight over the things the websocket *cannot* set, and
which each break the overlay in a way that looks like an overlay bug:

- canvas is not 1920×1080
- **Browser Source Hardware Acceleration** is off — it lives in OBS's app-wide
  `global.ini`, so no script can reach it. Without it OBS renders a 7680×4320
  CSS transform on the CPU and the pan judders
- nothing is listening on the mascot bridge's or the chat bridge's port
- a file the sources point at is missing from the repo
- `chat/blocklist.txt` is missing — it is gitignored, so a fresh clone never
  has it

Worth running before you go live.

No capture hardware on this machine yet? `--placeholders` makes the video
sources flat colour blocks instead, which is enough to see every scene work.

`--grade` adds a teal-and-amber colour grade to the camera (a LUT filter called
`GRADE` on `Cam`, generated by `tools/cam-grade.py`). It is off by default, and
without the flag a setup run leaves the camera's filters alone.

`--denoise` adds a noise filter at the top of the mic chain: `NV DENOISE`
(NVIDIA Noise Removal, intensity 0.7, voice detection off) when OBS can run it,
which takes an RTX card and NVIDIA's
[Audio Effects SDK redistributable](https://www.nvidia.com/en-us/geforce/broadcasting/broadcast-sdk/resources/)
installed before OBS starts; otherwise `DENOISE` (RNNoise). Without the flag a
setup run neither adds a noise filter nor removes one. At intensity 1.0 with
voice detection on it made the voice break up, which is why it is opt-in.

## 5. Point the sources at your hardware

The script cannot guess these. In OBS, double-click each and pick:

| Source | Set |
| --- | --- |
| `Game` | the display, window, or game to capture — its sound comes with it |
| `Cam` | your webcam |
| `Chat` | your chat widget URL |
| `Browser` | only if it is not Chrome, or not the Chrome window you want |
| `Discord` | nothing, unless you run Discord PTB or Canary |

Sizes do not matter. The overlay crops and fits every source into its hole.

## 6. Put the encode on the GPU

```bash
python3 tools/obs-setup.py --encoder auto
```

A fresh OBS encodes on the CPU, with x264. That is the wrong place for it here:
the pan is a 7680×4320 CSS transform running inside CEF, and Source Record adds
an output per source on top of the program encode. `auto` picks the best
hardware encoder *this* OBS reports — NVENC, then QuickSync, then AMD, then
VideoToolbox — and sets it for both the stream and the recording. Name one
instead if you would rather: `--encoder nvenc | qsv | amd | apple | x264`.

It asks OBS what it has rather than guessing from the GPU, because a card that
supports NVENC is not the same thing as an OBS that registered it — a driver
too old, a plugin that failed to load, and the encoder is simply not there. If
you ask for one this OBS did not register, the script says so and changes
nothing.

An ordinary run without the flag still does two things:

- **Rewrites a deprecated encoder ID.** `jim_nvenc` is the pre-OBS-30 name for
  `obs_nvenc_h264_tex`. OBS still accepts it, maps it to the same encoder, and
  logs `Encoder ID 'jim_nvenc' is deprecated and may be removed in a future
  version` once per output per launch. Renaming it changes nothing about the
  encode, so it happens without being asked.
- **Reports a software encoder** if a hardware one is sitting unused.

It never switches encoder on its own, because x264 can be a deliberate choice —
a dedicated encoding PC, or a recording you want CPU quality for — and this
script does not overwrite deliberate choices.

**Bitrate, preset and tuning are yours.** They live in the profile's
`streamEncoder.json`, which no websocket request can reach, and they are a
judgement about your upload and your GPU that a repo has no business making.
Settings → Output, with the encoder already correct.

## 7. Start everything

```bash
python3 start.py --overlay hi-fi-rush
```

On Windows, `py -3 start.py --overlay hi-fi-rush`. This is the one command to
run before a stream — name the show's overlay, and OBS opens on its scene
collection; add `--profile vALO` to pick the Restream setup too. An OBS that
is already open is switched over the websocket instead, unless something is
live. It starts both bridges and then OBS if it is not already open:

| | What | Feeds |
| --- | --- | --- |
| `mascot` | `mascot/bridge/cursor-bridge.py` on 127.0.0.1:4460 — only for an overlay with a mascot | `Mascot`, `MascotV` |
| `chat` | `chat/chat-bridge.py` on 127.0.0.1:4461 | `Tts` |
| OBS | launched detached, once both bridges are listening | — |

Leave it running while you stream; Ctrl-C stops both bridges and leaves OBS
alone. Every line either bridge prints comes out prefixed `[mascot]` or
`[chat]`. A bridge that crashes after running a while is restarted; one that
dies in its first seconds — a missing file, a port already in use — is
reported and left down rather than restarted into the same problem. A bridge
already running on its port is left alone, so running it twice is harmless.
On Windows the bridges live in a job object, so even a hard kill of
`start.py` cannot leave one behind holding its port.

**The first run does some setup**: it creates `chat/.venv`, installs Piper into
it (about 50 MB), and downloads the lessac voice from Hugging Face (63 MB,
checksum verified). Later runs skip all of that.

**Copy `chat/blocklist.txt` across from your old machine.** It is gitignored —
see [Chat TTS](#chat-tts) — so a clone never has it, and without it the chat
bridge refuses to start. `start.py` says so and starts the mascot anyway.

| Flag | Does |
| --- | --- |
| `--overlay NAME` | open OBS on `overlays/NAME`'s scene collection, or switch a running OBS to it |
| `--profile NAME` | the same for the OBS profile — the Restream setup |
| `--display N` | mascot follows the cursor on display N (`py -3 mascot/bridge/cursor-bridge.py --list-displays`) |
| `--only mascot` / `--only chat` | start just one bridge |
| `--no-obs` | do not launch OBS |

If you forget it, nothing breaks for good: the mascot keeps asking for its
sprite sheet and the TTS page keeps reconnecting, and both come alive the
moment their bridge is up — no OBS refresh needed.

## 8. Map the deck

The deck is Macro Deck 3 on a phone (see [CLAUDE.md](CLAUDE.md) §2). One button
per scene: `START` `GAME` `CAM` `BRB` `CHAT` `END`, plain OBS scene actions —
the overlay hears the switch and pans itself. Then `MIC`, `GAME AUDIO`,
`DISCORD`, `TTS` and `BROWSER`, each an OBS **Set input mute** toggle on
`Mic/Aux`, `Game`, `Discord`, `Tts` and `Browser` — `BROWSER` unmuted is the
browser on air in place of the game, and the key turns cyan and reads
`BROWSER ON AIR`; `CAM ON` toggles the `CAM OFF` filter on
`Cam`; `CLIP 5 MIN` runs
`obs-setup.py --clip`, which logs the press to `clip-marks-YYYY-MM-DD.csv` in
the clip folder, dated by the day the stream started — so a stream past
midnight stays in one file — and the `vod` column is where the moment sits in the Restream recording or
platform VOD, to cut after the stream. Nothing is buffered. `HOLD TO GO LIVE`,
bottom left, fires on a long press and runs `obs-setup.py --go-live`, which
starts the main and vertical streams at the same click — start OBS's own button
instead and the vertical waits out the whole delay first. Every toggle takes its
look from OBS's real state, not from the press.

## 9. Vertical output, if you want it

Optional, and entirely separate from everything above — skip it and the
horizontal overlay is unaffected.

A second 1080×1920 canvas, so one Stream Deck press moves both pages at once.
It is a second canvas rather than a second profile because base resolution is
*per profile*: switching profiles to go vertical would resize the canvas under
the horizontal overlay and every hole rect it has pushed.

1. **Install [Aitum Vertical Canvas](https://github.com/Aitum/obs-vertical-canvas)**,
   then **restart OBS**. Plugins bind at process start; nothing appears until
   you do.
2. In the new **Vertical** dock, add a canvas and set it to **1080×1920**.
   `obs-setup.py` cannot do this — obs-websocket has no request that sets a
   canvas resolution — so it checks it and complains if it is anything else.
3. ```bash
   python3 tools/obs-setup.py --vertical
   ```
   This renames the plugin's own scene to `VCOMIC`, adds `Game` / `Cam` /
   `Chat` — the *same inputs* the horizontal canvas uses, with independent
   scene items, so the two overlays cannot fight over a transform — and creates
   the `OverlayV` and `MascotV` browser sources above them.
4. **Click `VCOMIC` in the Aitum dock.** This is the one step nothing can
   automate. `SetCurrentProgramScene` refuses a scene that is not on the main
   canvas, `GetCurrentProgramScene` ignores the canvas argument and answers for
   the main one, and the plugin registers no websocket vendor and no
   scene-switching hotkey. Until you click it, `VCOMIC` is not on air, its
   sources never activate, and the vertical overlay never boots — silently. The
   script infers it from whether `OverlayV` has activated and says so.
5. Set the vertical output's server and key in the dock's own output settings.

There are no trigger scenes on the vertical canvas and it never switches:
`vertical.html` reads the **main** canvas's program scene and pans itself, so
`VCOMIC` sits on air forever and step 4 is a once-ever click.

### What does not carry across

- **Aitum keeps its outputs in its own plugin config**, not in the OBS profile
  — bitrate, server, and your **stream key in clear text**. `--export` does not
  touch that file and neither does anything else here; it is per-machine, and
  it must never be committed.
- The encoder stored there is only read when **Advanced** is ticked in Aitum's
  output settings. With it off the plugin picks one itself, which means a
  config can sit for months reading `ffmpeg_svt_av1` and encode on the GPU
  anyway — right up until somebody ticks Advanced and puts a second 1080×1920
  encode on the CPU. `--vertical` reports it either way.
- A second encode is a second encoder session. `CLAUDE.md` §6 names encoder
  count as the real ceiling, not GPU load.

## 10. One profile per Restream setup, if you want more than one

Restream keeps channels, titles and categories per **setup** — each card on its
home screen, `Default RTMP` and any RTMP setup beside it — and each setup has
its own stream key. So a profile per setup makes the game a profile switch: set
each setup's category once on Restream, and OBS's **Profile** menu decides which
one goes out. The vertical stream follows, because Restream's plugin sends it
on the main profile's key.

1. **Profile → Duplicate**, never Profile → New. A new profile starts at
   1280×720, 30 fps, Simple output, x264 and no delay, and its bitrate lives in
   `streamEncoder.json`, which no websocket request reaches. Duplicate copies
   all of it.
2. In the duplicate, **Settings → Stream → Disconnect Account**, then **Use
   Stream Key**, and paste that setup's key (Restream home → the setup's card).
   A profile connected to the Restream account always streams on the account's
   *default* key — OBS fetches it at login and writes it over any key you paste
   — so keep the account in one profile only, the one on `Default RTMP`. Its
   Restream docks come with it; for the other setups, a Custom Browser Dock on
   `https://app.restream.io/home` edits any of them.
3. ```bash
   python3 tools/obs-setup.py --check
   ```
   It visits every profile, checks canvas, delay, replay buffer and encoder in
   each, puts back the one you were on, and warns when two profiles share a
   key, when more than one is connected to the account, or when their encoder
   settings differ.

Switch profiles only while offline: a switch resets video and rebuilds every
output. The script will not visit other profiles while anything is live; it
names the ones it skipped.

## Carrying your OBS settings across too

`obs-setup.py` builds the *shape* — scenes, sources, order, transforms. It does
not know about filters, audio routing, hotkeys, or anything else you tune by
hand later. Export the collection for that:

```bash
python3 tools/obs-setup.py --export
```

writes [overlays/hi-fi-rush/obs/scenes.json](overlays/hi-fi-rush/obs/scenes.json), sanitised and safe to
commit. On the new machine:

1. OBS → **Scene Collection → Import** → pick `overlays/hi-fi-rush/obs/scenes.json`.
2. Switch to the imported collection ("Hi-Fi Rush").
3. `python3 tools/obs-setup.py` — repairs the browser URLs, which the export
   deliberately left as tokens: two for `Overlay` and `Mascot`, or four with
   `--vertical`, which adds `OverlayV` and `MascotV`.
4. Point `Game` / `Cam` / `Chat` at your hardware, as in step 5.
5. `--encoder auto` and the Aitum setup do not ride along in the collection —
   steps 6 and 9 again, on the new machine.

### What the export strips, and why it has to

The raw collection is **not** safe to commit. OBS stores browser source URLs
verbatim, and `obs-setup.py` puts the websocket password in them — so the live
file held that password three times, plus the absolute path to this repo, which
carries your username. The export removes:

| Removed | Replaced with | Because |
| --- | --- | --- |
| `pw` / `password` / `key` / `token` query params | dropped | it is a credential, and it is per-install anyway |
| settings keys named like credentials | `""` | same |
| `file:///…/hi-fi rush/` | `{{REPO}}` | absolute, and it contains your username |
| your home directory, anywhere | `{{HOME}}` | catches module and script paths too |

Then it refuses to write the file at all if anything credential-shaped survived.
Scrubbing is by *name*, never by value, so the tool never has to be told what
your password is.

Step 3 is what puts the real values back: `obs-setup.py` computes the repo path
on the machine it is running on and reads that machine's own websocket password
out of OBS's config. Verified end to end — set the URLs to the exported tokens,
ran the script, both came back correct and the overlay rendered.

### Two caveats

- **OBS keeps the collection in memory** and writes it out on its own schedule,
  so the file on disk can be many minutes behind what you are looking at. An
  export of a stale file is worse than none — it looks right and ships the setup
  you already fixed. So `--export` compares the file against the *live* scene
  graph over the websocket and **refuses** rather than warns:

  ```
  error: Untitled.json is stale -- OBS has changes it has not written out yet.
         on disk : Game < Brb < Cam < Chat < WiringTest < Overlay < Deer
         in OBS  : Game < Cam < Chat < Overlay < Deer
  ```

  Two ways to clear it. Quit OBS — it saves on a clean exit — and run `--export`
  again. Or, without restarting, **Scene Collection → Export** in OBS writes a
  file straight from memory, and `--export-from <that file>` sanitises it.
- **Capture device selections are left alone.** They are UIDs for hardware that
  will not exist on the other machine, so step 4 still applies. Nothing is
  gained by blanking them and a stale UID is no more confusing than an empty one.

Right now the export is close to redundant — it is exactly what the script
already builds. It starts earning its place the moment you add a chroma key to
the cam, noise suppression to the mic, or a hotkey.

## What the script does *not* do

Eight things, and `--check` names six of them:

| Not automated | Why |
| --- | --- |
| Enabling obs-websocket (step 3) | Chicken and egg — the script needs it to connect |
| Canvas 1920×1080 (step 3) | Reported, not set. Rescaling someone's canvas is not a thing a setup script should do behind their back — say the word and I'll make it a flag |
| Browser Source Hardware Acceleration (step 3) | In OBS's app-wide `global.ini`, not the profile, so there is no websocket request for it. Reported only |
| Capture device selection (step 5) | Machine-specific by definition |
| Bitrate, preset, tuning (step 6) | In the profile's `streamEncoder.json`, which the websocket cannot reach — and a judgement about your upload, not a fact about the overlay |
| The vertical canvas's resolution (step 9) | No obs-websocket request sets one. Reported against 1080×1920 |
| Putting `VCOMIC` on air (step 9) | Refused for a non-main canvas, unreadable back, no vendor, no hotkey. Inferred from whether `OverlayV` activated |
| Making a profile, and its stream key (step 10) | No request duplicates a profile, and `CreateProfile` makes one wrong five ways with a bitrate nothing can reach. The key is a credential, pasted by you. Each profile is checked, and keys compared by hash |

Also deliberately per-machine, so not in the repo:

- **The websocket password.** Generated per install, read from OBS's own config.
- **The bridge's display index** if you run more than one monitor.
- **Your deck profile.** It lives in Macro Deck's own data folder.
- **`chat/blocklist.txt`.** Personal, and a list of slurs — copy it by hand.
- **`chat/.venv` and `chat/voices/`.** Rebuilt by `start.py` on first run.
- **Nothing else.** `assets/` holds ~390 MB of sprite build scratch and stays
  out of git, but the three originals it grew from — `deer-raw.png`,
  `deer-plate.png`, `deer.mp4` — are committed. They are the inputs no command
  reproduces: a prompt does not re-roll an image generator's output, and the
  look-around video is a one-off render. Everything derived from them
  (`scrub/`, `deer/frames/`, the contact sheets, the spare `.png` sheet) is
  regenerable from `tools/hero-asset.py` and is ignored.

---

# Chat TTS

Reads your Restream chat aloud, on stream and in your ears:

> *ninja fan says: that jump was clean. On Kick.*

```
chat/
  chat-bridge.py     reads Restream chat, filters it, speaks it with Piper
  tts.html           the Tts browser source: plays each line, draws nothing
  blocklist.txt      what is never read aloud -- gitignored, copy it by hand
  .venv/  voices/    Piper and the lessac voice, built by start.py
```

`start.py` runs it (setup step 7). The chain:

1. The bridge reads chat from the socket Restream's own chat embed uses. The
   embed token comes out of your `Chat` source in OBS on every connect, so
   there is one copy of it: regenerate the embed in Restream, paste the new
   URL into `Chat`, and the bridge follows.
2. Each message is filtered, cleaned for the ear, and queued — one line at a
   time, newest wins in a flood.
3. Piper synthesises the line (about 125 ms for 3–4 s of speech, on one
   thread at low priority, so a game always gets the CPU first).
4. The `Tts` browser source plays it. That puts TTS on its own fader in OBS,
   so the deck's `TTS` button mutes it without touching alerts or game audio.

Twitch, YouTube and Kick are read. TikTok and Instagram are not Restream chat
sources at all, so the vertical audience's comments never are.

## What gets read

Everything, except:

| Skipped | Why |
| --- | --- |
| bots | the platform's own bot flag |
| `!commands` | they are for bots |
| your own accounts | `thedeepeffect` / `thedeepeffect_` — `OWN_NAMES` in `chat-bridge.py` |
| anything matching the blocklist | in the message *or the sender's name* |
| a line with nothing left to say | an emote or emoji on its own |

What is left is cleaned up: links become "a link", emoji and Kick emotes are
dropped, `@` and underscores go, `lolllllll` becomes `lolll`, and the line is
cut at 200 characters. Past five lines waiting, the oldest are dropped, so a
raid reads its newest lines rather than ten minutes of backlog.

## The blocklist

`chat/blocklist.txt`: one word or phrase per line, explained at the top of the
file. It is seeded with 634 entries — slurs and harassment, sexual terms and
swearing, English and romanized Hinglish — and leaves ordinary chat alone:
"this boss sucks", "hardcore mode", *chod de yaar*, *chakke* in cricket chat.
Every word left out on purpose is in the file, commented, with the reason;
remove the `#` to block it. Edit it mid-stream and the next message sees the
change.

**It is gitignored**, because it is personal and because it is a list of
slurs. So it is the one file you carry between machines by hand. Without it
the bridge refuses to start rather than read chat unfiltered; `--no-blocklist`
overrides that if you really mean it.

Restream sends no signal when a mod deletes a message, so the blocklist is the
only moderation TTS has: anything it lets through is read before a mod can act.

## Trying it

```bash
chat/.venv/Scripts/python chat/chat-bridge.py --say "testing one two"
```

speaks one line on this machine's speakers through the same filter and voice,
and exits. `--play` runs the whole bridge that way instead of through OBS;
`--read-own` lets your own messages through, for testing from your own
account. On macOS the venv's python is `chat/.venv/bin/python`.

The `Tts` page is `file://` like the overlay, so it always loads, and it
reconnects to the bridge by itself — start order does not matter.
`chat/tts.html?debug=1` in a browser shows what it is doing.

---

# Mascot

A character that follows your cursor, as its own OBS browser source. It shares
no code with [overlay.html](overlays/hi-fi-rush/overlay.html) -- no imports, no globals, no reach
into the comic page. The only fact the two have in common is the name of the
OBS scene, which they each read for themselves. Add it, move it, hide it,
delete it; the comic overlay never notices.

```
mascot/
  mascot.html            the page. one file, no build step
  placement.json         where the mascot sits, per OBS scene
  bridge/
    cursor-bridge.py     reads the OS cursor, serves the folder over HTTP
  deer/
    sheet.webp           72-cell sprite sheet -- the one that ships
    manifest.json        grid, cell size, per-frame gaze angles
```

It sits **above** the overlay in `COMIC`, not behind it. A mascot behind the
overlay would need a punched hole to show through, and a punched hole is a
transparent rectangle -- which would cut a mascot-shaped box out of the comic
art and put nothing behind it. Over the top, its own transparency does the job.

## Why a bridge is needed at all

An OBS browser source receives **no mouse events from your desktop**. The only
mouse input it ever sees comes from right-click -> Interact. There is no setting
that changes this. So the cursor has to be read outside the browser and pushed
in.

`cursor-bridge.py` does that with the standard library only -- no `pip install`.
macOS calls `CGEventGetLocation` through `ctypes`, which is a poll rather than an
event tap and so needs **no Accessibility permission**. Windows calls
`GetCursorPos` from `user32`. Both normalise to 0..1 within one display, so every
platform difference dies inside the bridge and the page sees one shape of data.

It also serves the `mascot/` folder over HTTP, so OBS has a single URL to point
at and there is no `file://` or CORS fiddling.

It binds to `127.0.0.1`, never `0.0.0.0` -- binding to all interfaces trips the
Windows Firewall dialog on every new machine.

## Run it

The mascot bridge is one of the two bridges `start.py` runs (setup step 7):

```bash
python3 start.py
```

On Windows, `py -3 start.py`. That is all a stream needs: it starts the
bridge, restarts it if it crashes, and prefixes its log with `[mascot]`.
`obs-setup.py` creates the `Mascot` source and keeps its settings right, so there
is nothing to add in OBS by hand. `start.py --only mascot` runs just this one.

### Running the bridge directly

For debugging -- watching its own output, trying a flag -- run it without the
launcher:

```bash
python3 mascot/bridge/cursor-bridge.py
```

On Windows, `py -3 mascot\bridge\cursor-bridge.py`. Not while `start.py` is
running: the port is already taken, so the second one cannot bind and exits.
Stop `start.py` first, or the other way round -- `start.py` leaves a bridge it
finds already listening alone.

| Flag | Does |
| --- | --- |
| `--list-displays` | prints the displays it can see, and exits |
| `--display N` | normalises the cursor against display N (default 0, the primary) |
| `--port N` | listens on N instead of 4460 -- the `Mascot` URLs and `ports.mascot` in `core/contract.js` would need changing too |
| `--hz N` | cursor polling rate (default 60) |

### Adding the source by hand

Only if you are not using `obs-setup.py`. A **Browser** source pointing at:

```
http://127.0.0.1:4460/mascot/mascot.html?set=deer&overlay=hi-fi-rush
```

Set it to **1920x1080**, and uncheck **Shutdown source when not visible** so the
connection survives scene changes. Name the source `Mascot` -- scenes UPPERCASE,
sources TitleCase, per [CLAUDE.md](CLAUDE.md) §2.

## Where it sits, per scene

`placement.json` maps an OBS scene name to a spot in **camera space** -- pixels
in the 1920x1080 canvas, not page coordinates. The mascot is a sibling of the
comic page, never a passenger on it, so a pan never drags it off frame.

```json
{
  "scenes": {
    "GAME": { "x": 352,  "y": 742, "size": 360 },
    "BRB":  { "x": 1531, "y": 437, "size": 390 },
    "CHAT": { "x": 1600, "y": 792, "size": 400 }
  }
}
```

| Key | Means |
| --- | --- |
| `x`, `y` | the **pivot** -- the point the gaze rotates about, which sits `pivot` of the way down the cell. Not the cell's top-left, not its centre |
| `size` | displayed cell height in canvas px |
| `pivot` | optional per-scene override of the default 0.30 |
| `hidden` | `true` to name a scene and still keep the mascot off it |

**A scene with no entry hides the mascot.** That is why it appears on GAME, BRB
and CHAT and nowhere else, and why adding it to START is one line rather than a
code change.

On a scene change it walks to its new spot over 980ms on the same easing as the
comic pan, so it travels with the page instead of teleporting mid-switch.

The three shipped spots:

| Scene | Where | Why there |
| --- | --- | --- |
| `GAME` | bottom left, over the capture | clear of the `GAMEPLAY` tag, out of the way of most HUDs |
| `BRB` | inside the taped photo frame | that panel's webcam hole was removed and drawn as a frame instead -- see CLAUDE.md §5 |
| `CHAT` | bottom right, in the gutter | the chat panel is portrait, so `fit` leaves 555px of empty page beside it. Nothing to cover |

### Authoring a new one

```
http://127.0.0.1:4460/mascot/mascot.html?set=deer&overlay=hi-fi-rush&edit=1
```

Right-click the `Mascot` source in OBS → **Interact**, switch to the scene you
want in OBS, drag the mascot where you want it, and the panel prints the JSON
line for *that* scene. Paste it into `placement.json` under `"scenes"`, refresh
the browser source, done. Switch scenes and repeat.

## Scene detection

Same two paths as the overlay, for the same measured reasons (CLAUDE.md §2):

- **`window.obsstudio`** is primary. It survives a dead websocket, and it
  reports the *trigger* scene name even though the source is nested two scenes
  deep.
- **obs-websocket** seeds the first scene, because `getCurrentScene()` answers
  `null` in a nested browser source until the first switch. Without the seed
  the mascot would stay hidden until you pressed a button.

`obs-setup.py` puts the password in the source URL. Outside OBS, `?scene=GAME`
forces a scene so you can lay things out in a normal browser.

## Multiple displays

```bash
python3 mascot/bridge/cursor-bridge.py --list-displays
```

lists them and exits. Then start with the one OBS is capturing:

```bash
python3 start.py --display 1
```

Display 0 is the primary on both platforms, and the default.

## URL parameters

| Param | Default | Does |
| --- | --- | --- |
| `set` | `deer` | Sprite folder next to `mascot.html` |
| `place` | `placement.json` | Per-scene placement file, or `off` to ignore scenes and stay put |
| `scene` | -- | Force a scene name, for laying out in a normal browser |
| `host` | `ws://127.0.0.1:4455` | obs-websocket url |
| `pw` | -- | obs-websocket password |
| `size` | `320` | Displayed cell height in canvas px |
| `anchor` | `bottom-right` | Also `bottom-left`, `top-right`, `top-left`, `center` |
| `margin` | `48` | Distance from the anchored edges |
| `x`, `y` | -- | Explicit pivot in canvas px; overrides `anchor` |
| `pivot` | `0.30` | Where the head sits down the cell, 0..1. This is what the gaze rotates about, not the cell centre |
| `ease` | `0.18` | Per-frame follow. Lower is lazier |
| `aimease` | `0.22` | Smooths raw cursor direction before the head follows it |
| `hold` | `0.24` | Frame hysteresis. Higher reduces cell flicker near sprite boundaries |
| `maxrate` | `900` | Degrees per second cap, so it can't snap 180 degrees instantly |
| `flip` | `0` | Mirror horizontally |
| `dir` | manifest | Override sprite order: `clockwise` or `counterclockwise` |
| `edit` | `0` | Drag/resize setup mode that generates the final OBS URL |
| `debug` | `0` | Readout: input source, angle, cell, cursor |

## Edit mode

Keep the OBS Browser source full canvas, such as 1920x1080. Move the mascot
inside the page instead of moving the OBS source itself:

```
http://127.0.0.1:4460/mascot/mascot.html?set=deer&overlay=hi-fi-rush&edit=1
```

Right-click the Browser source in OBS, choose **Interact**, drag the mascot, and
adjust size/pivot in the panel.

What the panel prints depends on whether a placement file is in play. With one
(the normal case) it prints the `placement.json` line for the scene currently on
air. With `place=off` it prints a finished browser-source URL carrying explicit
`x`, `y`, `size` and `pivot`, and no `edit=1`.

## Testing without OBS

Real `mousemove` events never fire inside OBS, but they do in a normal browser,
and the page listens for both. Open the same URL in any browser and move your
mouse -- it works immediately, with `debug=1` showing which input path is live.
That is how to develop this without touching OBS at all.

## When things fail

| Fails | Result |
| --- | --- |
| Bridge not running at OBS launch | The sprite sheet is served *by* the bridge, so the page keeps asking for it with backoff and appears the moment the bridge comes up. It does not give up |
| Bridge not running | Page loads, sits at rest, `EventSource` retries on its own. Nothing blanks |
| obs-websocket down | `window.obsstudio` still drives every switch. Only the startup seed is lost, so the mascot waits for the first scene change instead of appearing immediately |
| Scene not in `placement.json` | Mascot hides. Deliberate: that is how it stays off START, CAM and END |
| Bridge dies mid-stream | Mascot holds its last pose, reconnects when the bridge returns. Under `start.py` the bridge is restarted for you |
| `start.py` says *already listening on 4460* | A bridge is already up -- usually a direct run from earlier. It is left alone and keeps working; close it if you want `start.py` to supervise the mascot |
| Cursor-locked fullscreen game | The OS cursor stops moving, so the mascot holds still. Not fixable without an event tap and Accessibility permission |
| Sprite set missing | On-screen message naming the path it tried |

Idle cost is zero by construction: the animation loop cancels itself once the
head settles and only wakes on cursor movement.

## Adding another mascot

Build a sheet with `tools/hero-asset.py`, drop the folder in `mascot/`, and
change `?set=`. Nothing in `mascot.html` is deer-specific -- grid, cell size and
per-frame gaze angles all come from `manifest.json`.

---

# Interactive hero assets

A character that follows your cursor with its head. The motion is not rigged —
it's an AI-generated video of the character looking around in one continuous
circle, cut into a sprite sheet. At runtime the overlay picks the cell matching
the cursor's angle.

`tools/hero-asset.py` covers everything between "I have an image" and "I have a
sprite sheet". Same commands on macOS and Windows.

| Subcommand | Does |
| --- | --- |
| `bg` | Reports an image or video's background colour and whether it is keyable |
| `plate` | Cuts the subject out and rebuilds the background flat |
| `probe` | Reports a video's dimensions, fps, frame count, duration |
| `scrub` | Dumps timestamped stills so you can pick the loop points |
| `build` | Keys, crops, normalizes, tiles, and writes the manifest |
| `verify` | Reports sprite coverage and writes contact sheets |

## Requirements

**ffmpeg and ffprobe on your PATH.** That's it for the main pipeline.

macOS:
```bash
brew install ffmpeg webp
```

Windows (PowerShell):
```bash
winget install Gyan.FFmpeg
```

`webp` / `cwebp` is optional — it only shrinks the final sheet. Many ffmpeg
builds ship without `libwebp`, and the script falls back to `cwebp` if it's
there and to plain PNG if it isn't. Nothing breaks either way.

**Python 3.8+.** Standard library only, no `pip install` needed to run it.
On Windows the launcher is usually `py -3` rather than `python3`:

```bash
py -3 tools\hero-asset.py --help
```

Everything below uses `python3`; substitute `py -3` on Windows.

`rembg` is needed **only** for `plate`, and only if your source image doesn't
already have transparency:

```bash
pip install "rembg[cli]"
```

---

## Step 1 — Get a source image

Generate one, or find one. It must be a **front-facing head-and-shoulders
portrait** — the body has to stay still through the whole animation, so a full
body pose gives the model room to wander.

A prompt that produces a usable plate (see the end of this file for a
deer-specific one):

> Front-facing head and shoulders portrait of a cute stylized deer fawn,
> looking directly at the camera, symmetrical, centered. Soft even lighting
> with no directional shadow and no cast shadow. Flat solid pure green
> background, no gradient, no vignette, no texture, no floor, no horizon.
> Large expressive eyes clearly visible, ears clearly separated from the head
> silhouette. No props, no accessories in front of the face, no text. Clean
> vector-adjacent illustration style, thick confident outlines, flat saturated
> color. Generous empty space around the head on all sides.

Three things in there are load-bearing: **no cast shadow** (a shadow that
doesn't move when the head turns reads as broken), **flat background** (it's
your key), and **space around the head** (the head swings outside the resting
silhouette).

## Step 2 — Check the background, then build the plate

Image generators essentially never give you the colour you asked for. Ask what
you actually got:

```bash
python3 tools/hero-asset.py bg deer.png
```

It samples all four corners and reports two numbers:

- **corner drift** — how much the colour changes across the frame. Catches
  gradients and vignettes.
- **local texture** — per-pixel spread inside one corner. Catches grain, noise,
  and paper texture, which corner averages hide completely.

Then it tells you which path you are on:

- **FLAT** — skip `plate`. Note the `--key-hex` value it prints and use it on
  `build`.
- **SLIGHTLY UNEVEN** — try `--key-hex` with `--similarity 0.20`; fall back to
  `plate` if the key leaves patches.
- **NOT FLAT** — chromakey cannot save this. Run `plate`.

### plate

If your image already has a flat background you control, skip this. Otherwise:

```bash
python3 tools/hero-asset.py plate deer.png --out assets/deer-plate.png
```

Cuts the subject out, trims the transparent margin, and centers it on a flat
green field. Use `--color magenta` if the character has green in it. `--size`
and `--fill` control the canvas and how much of it the subject occupies.

If your image already has an alpha channel:

```bash
python3 tools/hero-asset.py plate deer.png --out assets/deer-plate.png --keep-alpha
```

## Step 3 — Generate the video

Upload the plate to [Higgsfield](https://higgsfield.ai) → Seedance, with this
prompt:

> Use the uploaded image as the exact reference. Preserve the character, facial
> expression, proportions, lighting, camera angle, composition, and the flat
> solid background color exactly as they appear. Keep the camera completely
> locked with no zoom, pan, rotation, cropping, or scene changes.
>
> Animate only the character. Do not create, render, or introduce any cursor,
> pointer, dot, insect, toy, hand, shadow, particle, or any other new visual
> element. Do not alter the background color or add any gradient, texture, or
> vignette to it.
>
> Make the character track something moving in one smooth, continuous clockwise
> circle around it. Begin looking straight up, then rotate the gaze smoothly and
> evenly clockwise — through upper-right, right, lower-right, straight down,
> lower-left, left, upper-left — and back to straight up. One single unbroken
> rotation at a constant speed. Do not pause, reverse, or return to center at
> any point.
>
> The eyes lead and the head follows with a slight delay. The ears rotate subtly,
> the neck moves naturally, and any whiskers or fur have minimal secondary motion.
>
> Keep the body, shoulders, chest, and sitting posture completely still. No
> stretching, face distortion, spinning, exaggerated rotation, breathing, or body
> pumping. The first and last frames must be identical so the animation loops
> seamlessly for frame-by-frame scrubbing.

**One continuous rotation is the whole point.** The published version of this
workflow sweeps left, then center, then right — that ordering is fine for a
looping hero video but useless here, because cursor angle maps linearly onto
frame index. Any pause, reversal, or return-to-center puts two unrelated poses
in adjacent cells and the head snaps as your cursor crosses them.

Download the result as MP4.

## Step 4 — Check what you got

```bash
python3 tools/hero-asset.py probe deer.mp4
```

Then watch it. You are checking three things, and only one of them is fixable
downstream:

- **Did the body stay put?** Not fixable. Regenerate.
- **Did the background stay flat?** Not fixable. Regenerate.
- **Is the rotation one direction at constant speed?** Not fixable. Regenerate.

## Step 5 — Find the loop points

It will not honor "identical first and last frame" exactly, so pick the loop
yourself:

```bash
python3 tools/hero-asset.py scrub deer.mp4 --out assets/scrub
```

Dumps stills at 8 fps into `assets/scrub/`. The timestamp of `t_NNNN.png` is
`(NNNN - 1) / 8` seconds. Find where the gaze passes 12 o'clock going in and
coming out — those two numbers are your `--start` and `--end`.

## Step 6 — Build the sheet

```bash
python3 tools/hero-asset.py build deer.mp4 --out assets/deer --start 0.5 --end 4.9
```

One command does the key, the despill, the crop, the frame normalization, the
tiling, and the manifest. Output:

```
assets/deer/
  sheet.png       the sprite sheet, RGBA
  sheet.webp      same, lossless, smaller (if a webp encoder exists)
  frames/         the 72 individual cells
  manifest.json   grid, cell size, degrees per frame
```

Copy `sheet.webp` and `manifest.json` into `mascot/sets/deer/` to ship them. That
pair is all `mascot.html` loads -- it reads the sheet's filename out of the
manifest. The `.png` and `frames/` are for looking at, and are gitignored.

### Options worth knowing

| Flag | Default | When to touch it |
| --- | --- | --- |
| `--frames` | 72 | 72 = 5° per cell. Lower reads as steppy on slow cursor drift |
| `--cell` | 400 | Max cell edge in px. Raise for a bigger on-screen character |
| `--color` | green | Which despill to apply. Keying colour comes from `--key-hex` if set |
| `--key-hex` | off | The colour actually in your plate, from `bg`. Almost always needed if you skipped `plate` |
| `--similarity` | 0.12 | **Raise** toward 0.20 if the key leaves speckles; **lower** if it eats into the subject |
| `--blend` | 0.06 | Edge softness |
| `--no-despill` | off | If despill is washing the subject out |
| `--pad` | 8 | Slack around the auto-crop |
| `--start` / `--end` | whole clip | Your loop points from step 5. Not needed with `--angle-uniform` |
| `--angle-uniform` | off | **Usually what you want.** Pick cells at equal angles instead of equal times |
| `--head-frac` | 0.55 | Top fraction of the subject treated as the head, for angle tracking |
| `--interp-fps` | 0 | Motion-interpolate the generated clip before tracking and sampling. Slower, but can remove repeated cells |
| `--calibrate` | off | Visual anchors for manifest angles, e.g. `down=1,left=19,up=37,right=55` |

### Angle-uniform selection

These clips never rotate at a constant speed. The generator dwells at some
directions and races through others -- a 0 to 164 deg/s spread is typical. Picking
frames at even *time* intervals then spends a dozen cells on one lingering pose
and skips whole arcs, so the character sticks in some directions and jumps in
others.

```bash
python3 tools/hero-asset.py build deer.mp4 --out assets/deer --key-hex 0x07CB32 --angle-uniform
```

With `--angle-uniform` the tool tracks the head's centroid through every frame,
normalises the ellipse it traces (yaw swings it further than pitch does),
unwraps the angle, finds the longest span that advances one way through a full
360 degrees, and then picks the frame nearest each of your N target angles. A dwell
collapses to a single cell. Pacing stops mattering, and you no longer need
`--start` / `--end` at all -- it finds the rotation itself.

The detected per-frame angles are written into `manifest.json`. Runtime picks
the nearest manifest angle for the cursor direction, so a sheet can start at any
point in the rotation and still follow correctly without rebuilding the sprite
frames.

If the tracker gets the visual direction wrong, calibrate the manifest from
frames you inspect in the contact sheet:

```bash
python3 tools/hero-asset.py build deer.mp4 --out assets/deer --key-hex 0x07CB32 --angle-uniform --calibrate down=1,left=19,up=37,right=55
```

If the source moves too fast through part of the circle, add interpolation:

```bash
python3 tools/hero-asset.py build deer.mp4 --out assets/deer --key-hex 0x07CB32 --angle-uniform --interp-fps 60 --calibrate down=1,left=19,up=37,right=55
```

It reports how many cells had to reuse a neighbouring frame. That happens where
the source moved more than one cell's worth of angle between frames, and it is a
property of the clip, not of the selection.

### Verify the sheet

```bash
python3 tools/hero-asset.py verify assets/deer
```

This prints cardinal frame mapping, repeated-source-cell counts, and angle-gap
stats, then writes `verify-frames.jpg` and `verify-cardinals.jpg` next to the
sprite sheet.

It refuses rather than guessing when the clip has no rotation to find: a
left-right sweep with almost no vertical component, or a longest run that never
reaches 360 degrees. Both messages name the fix.

**The crop is measured, not guessed.** The script keys every frame in the range,
takes the union of the subject's bounding box across all of them, and crops to
that. This is the step that would otherwise clip the ears on the frames where the
head is turned hardest — the resting pose is never the widest one.

### Guards

The build stops rather than producing something silently wrong:

- **Key matched nothing** — the background isn't flat, or `--similarity` is too
  tight.
- **Subject measures ~100% of frame** — `--color` is almost certainly wrong.
  Override with `--allow-full-frame` if the character really does fill the frame.
- **Sheet over 4096px** — past the safe single-texture limit on older GPUs.
  Lower `--cell` or `--frames`, or split into two sheets.
- **Not enough source frames** — the trim range is shorter than `--frames`.

## Step 7 — Verify

Open `sheet.png` and check the seam: `frames/f_001.png` and `frames/f_072.png`
are adjacent angles once the cursor wraps past 12 o'clock, so they should look
nearly identical. If they don't, your `--start`/`--end` are off — go back to
step 5.

---

## Why a sprite sheet and not the video

Scrubbing `video.currentTime` seeks to keyframes. At 60 cursor updates a second
against interframe-compressed video that stutters badly, and no amount of
tuning fixes it — you'd have to re-encode all-intra anyway, at which point the
file is larger than the sheet.

The sheet is one `background-position` shift per update: deterministic, no
decode, no seek latency, no codec-support question inside CEF, and identical
behavior across every OBS restart. `manifest.json` carries the grid and cell
size so the overlay never hardcodes them.

---

## Deer prompt

For the image generator in step 1. Tuned for a soft, wide-eyed storybook fawn:

> A cute baby deer fawn character, front-facing head and shoulders portrait,
> looking directly at the camera. Symmetrical and centered, with generous empty
> space above and to both sides of the head.
>
> Strongly neotenous design: oversized head relative to the body, very large
> round dark eyes set low and wide apart on the face, long delicate eyelashes, a
> small soft rounded muzzle with a tiny dark nose, rounded cheeks, and a slender
> neck. Two large soft ears angled gently outward. No antlers, or the smallest
> possible nubs. Warm reddish-tan fur with a cream muzzle, cream chest, and a
> scatter of soft white spots across the shoulders.
>
> Sweet, gentle, slightly shy expression. Wide-eyed and curious, mouth closed or
> barely smiling. Innocent storybook character, not realistic wildlife.
>
> Bold clean illustration style with thick confident outlines and flat saturated
> color. No gradients, no rendered fur texture, no painterly shading, no
> photorealism.
>
> Soft even frontal lighting with no directional shadow and no cast shadow
> anywhere. Flat solid pure green background (#00FF00), completely uniform, with
> no gradient, no vignette, no texture, no ground plane, no horizon line.
>
> No props, no hat, no scarf, no flowers, no foliage, nothing overlapping the
> face or ears. No text, no watermark, no border.

Swap the green for magenta (`#FF00FF`) if you end up with a green-tinted fawn,
and pass `--color magenta` to `plate` and `build`.

### Dialing the cuteness

Cute is neoteny, and it comes from four sliders. Push these, in this order:

1. **Eye size and placement** — bigger, lower on the face, further apart. This is
   most of the effect on its own.
2. **Head-to-body ratio** — a larger head reads younger.
3. **Muzzle length** — shorter and rounder. A long muzzle reads adult instantly.
4. **Roundness** — round cheeks and soft jaw over any angular structure.

Add "chibi proportions" or "slightly oversized head" if it still comes out too
mature. Add "no antlers at all" if nubs keep appearing and you don't want them.

### Don't name a franchise character

This overlay deliberately carries no franchise references -- see
[CLAUDE.md](CLAUDE.md) §4, where the caption bar and every character name were
removed for exactly this reason. Naming a known animated deer in the prompt pulls
the generator toward that studio's actual character design, which is the one
result you can't put on a public stream. Describe the traits instead; the prompt
above is what those traits look like written out.

It also happens to be the wrong style. That film's look is soft painterly
watercolor, which keys badly at the edges and clashes with flat halftone comic
panels.

### Fitting the comic art direction

The overlay's look is flat saturated color under a halftone grid, hand-inked
wobbly borders, black silhouette figures. A soft rendered fawn will read as
pasted-in against that. Two ways to keep it coherent: push the prompt harder
toward flat vector with heavy black outlines, or lean into the mismatch and frame
the deer as a taped-on photo inset with a hard offset shadow -- already an
established element in the art direction rather than a new one.

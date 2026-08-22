> **There is a script for this now.** `python3 tools/obs-setup.py` builds and
> repairs everything below over obs-websocket, and `--check` verifies it without
> writing. See the README's "Set up on a new machine". This document stays as
> the explanation of *what* it is building and why, and as the manual path if
> you would rather click.

# OBS setup — build order step 3

Written for **OBS 32.0.1 on macOS 26.3**, which is what's installed here.
Follow top to bottom. Every name in `code` must be typed **exactly** — same
spelling, same capitals. The overlay finds OBS sources by name and nothing else,
so `cam` instead of `Cam` fails silently later with no error message.

Goal: prove that switching scenes reaches the browser source, and that the
overlay can move a source that lives one scene deeper than the one on screen.

---

## 0. Learn the window first

Open OBS. Along the bottom are docked panels, left to right:

| Panel                | What it holds                                            |
| -------------------- | -------------------------------------------------------- |
| **Scenes**           | Your scenes. Click one to switch to it.                  |
| **Sources**          | What's inside the **selected** scene.                     |
| **Audio Mixer**      | Volume. Ignore for now.                                  |
| **Scene Transitions**| How switches animate.                                     |
| **Controls**         | Start Streaming, Settings, etc.                          |

Two rules that explain most OBS confusion:

- **Sources belong to the selected scene.** The Sources list changes every time
  you click a different scene. If a source "disappeared", you're likely just
  looking at a different scene.
- **In the Sources list, top = in front.** The item at the top of the list is
  drawn over everything below it. This matters in step 4.

If the panels aren't there: menu bar → **Docks → Reset UI**.

---

## 1. Set the canvas to 1920 × 1080

**Do not skip this.** The overlay reads pixel coordinates out of the browser and
hands them straight to OBS with no conversion. That only works if the OBS canvas
and the browser source are the same size. If your canvas is 2560 × 1440, every
hole lands in the wrong place and nothing will tell you why.

1. **Controls** panel → **Settings** (or `⌘ ,`).
2. **Video** in the left sidebar.
3. **Base (Canvas) Resolution** → `1920x1080`.
4. **Output (Scaled) Resolution** → `1920x1080`.
5. **Common FPS Values** → `60`.
6. **Apply**, then **OK**.

---

## 2. Turn Studio Mode off

Look at the **Controls** panel for a **Studio Mode** button. If it's highlighted
(on), click it to turn it off.

Studio Mode splits the screen into preview and program and makes you click
"Transition" to actually switch. That breaks the one-press-one-pan model. Off.

---

## 3. Enable the websocket server

This is how the overlay talks to OBS. It ships inside OBS — nothing to install.

1. Menu bar → **Tools** → **WebSocket Server Settings**.
2. Tick **Enable WebSocket server**.
3. Leave **Server Port** at `4455`.
4. Leave **Enable Authentication** ticked.
5. Click **Show Connect Info** → a panel appears with **Server Password**.
6. Copy that password somewhere. You need it in step 6.
7. **Apply**, then **OK**.

---

## 4. Build the `COMIC` scene

This is the only scene that ever holds anything. Everything else just points at it.

1. In the **Scenes** panel, click **+** (bottom-left).
2. Type `COMIC` — capitals — and click **OK**.

You'll probably have a leftover scene called `Scene` from install. Right-click it
→ **Remove** → confirm. Keeps the preflight check honest.

### 4a. Add six placeholder sources

Real cameras and capture cards can wait. Right now you want to prove the plumbing,
and coloured rectangles do that faster — no permission prompts, no hardware.

With `COMIC` selected in Scenes, do this **six times**:

1. In the **Sources** panel, click **+**.
2. Choose **Color Source**.
3. The dialog has **Create new** selected and a name field. Clear it and type the
   exact name from the table below.
4. Click **OK**.
5. A properties window opens. Click the colour swatch, pick the listed colour,
   **OK**. Then **OK** again.

| Order to add | Name      | Colour       | Why this colour                    |
| ------------ | --------- | ------------ | ---------------------------------- |
| 1st          | `Standby` | grey         | added first = ends up at the bottom |
| 2nd          | `Brb`     | purple       | TitleCase, not `BRB` — see below   |
| 3rd          | `Game`    | green        |                                     |
| 4th          | `Cam`     | orange       | the one you'll ping in step 9      |
| 5th          | `Chat`    | blue         |                                     |
| 6th          | `Overlay` | yellow       | added last = ends up on top        |

> **Scenes and sources share one namespace.** In OBS a scene *is* a source
> internally, so you cannot have a scene and a source with the same name — OBS
> refuses the second one, usually without saying why. Since step 7 creates a
> **scene** called `BRB`, the source here must be `Brb`.
>
> The rule for this project: **scenes UPPERCASE, sources TitleCase.** That's why
> the scene `GAME` and the source `Game` can coexist — the comparison is
> case-sensitive. Follow the convention and nothing ever collides.

Adding in that order gives you the right stacking for free — each new source goes
above the previous one, so `Overlay` lands on top, which is where the real comic
art has to sit. If the order comes out wrong, drag items in the list, or select one
and use the **∧ ∨** arrows at the bottom of the Sources panel.

Your Sources list should now read, top to bottom:
`Overlay`, `Chat`, `Cam`, `Game`, `Brb`, `Standby`.

> **Swapping in the real thing later.** On macOS the source types are:
> `Cam` → **Video Capture Device** · `Game` → **macOS Screen Capture** (set
> Method to Window or Application) · `Brb` / `Standby` → **Media Source** ·
> `Chat` → **Browser**.
>
> Note that `CLAUDE.md` §2 says "Game Capture" — that source type is
> **Windows-only**. On macOS it's **macOS Screen Capture**, and it needs
> System Settings → Privacy & Security → **Screen & System Audio Recording** →
> enable OBS, then restart OBS. Camera access prompts the first time you add
> Video Capture Device.

---

## 5. Check browser hardware acceleration

1. **Settings** (`⌘ ,`) → **Advanced**.
2. Scroll to the **Sources** section.
3. Tick **Enable Browser Source Hardware Acceleration** if it isn't already.
4. **Apply** → **OK**.

Without this the oversized comic page repaints on the CPU and the pan stutters.

---

## 6. Add the test rig

This browser source goes **inside `COMIC`**, on purpose. That puts it at exactly
the same nesting depth the real overlay will have, so the result actually means
something.

1. Make sure `COMIC` is selected in **Scenes**.
2. **Sources** → **+** → **Browser**.
3. Name it `WiringTest` → **OK**.
4. In the properties window:
   - Leave **Local File** **unticked**.
   - **URL** — the absolute path to your clone, with your password from step 3
     replacing `YOUR_PASSWORD`:

     ```
     file:///path/to/hi-fi%20rush/obs-test.html?pw=YOUR_PASSWORD
     ```

     The `%20` is the space in "hi-fi rush". Leave it encoded — a literal space
     makes the source load nothing and show white. `tools/obs-setup.py` builds
     this string for you from wherever the repo actually sits, which is why the
     script is the easier path.
   - **Width** `1920`, **Height** `1080`.
   - **Untick** *Shutdown source when not visible*.
   - **Untick** *Refresh browser when scene becomes active*.
   - Tick **Control audio via OBS**. (Not needed today; it's what will carry
     alert sound later, and it's easier to set now.)
5. **OK**.

It should appear at the top of the Sources list, above `Overlay`. Good — you want
to see it. You'll delete it in step 11.

You should now see the test page in the preview: a dark panel reading
**COMIC — OBS WIRING TEST**, with the websocket dot green and
`obsstudio: present`.

---

## 7. Build the six trigger scenes

Each of these is an empty shell whose only job is to be a Stream Deck target.
Pressing one switches OBS; the overlay hears the name and pans. Nothing inside
them ever changes.

Do this **six times**, once per name — `START`, `GAME`, `CAM`, `BRB`, `CHAT`, `END`:

> If OBS won't let you create one of these, a source somewhere already has that
> exact name — scenes and sources share a namespace (see step 4a). Rename the
> source to TitleCase, then create the scene.

1. **Scenes** panel → **+** → type the name → **OK**.
   (OBS switches to the new empty scene automatically. The preview goes black.
   That's expected.)
2. **Sources** → **+** → **Scene**. It's near the bottom of the list — the source
   type literally called `Scene`.
3. In the dialog, click **Add Existing**, select `COMIC` from the list → **OK**.
4. The preview now shows your `COMIC` scene. Right-click it in the preview →
   **Transform** → **Fit to Screen** (or press `⌘ F`) so it fills the canvas edge
   to edge.
5. **Add nothing else to this scene. Ever.**

**Why it's built this way:** the browser source lives in `COMIC` and only in
`COMIC`. Because every trigger scene just points at that same one instance, OBS
never destroys and rebuilds the browser when you switch. Your page keeps running,
the animation keeps its state, and nothing reloads. If you instead put a copy of
the overlay in each scene, every switch would reload it and you'd see a white
flash and a reset animation.

When you're done, the **Scenes** panel lists seven: `COMIC`, `START`, `GAME`,
`CAM`, `BRB`, `CHAT`, `END`.

---

## 8. Set the transition to Cut

**Finding the panel:** it's in the bottom row, **between Audio Mixer and
Controls**, and it's usually squeezed narrow enough to miss — often just a
dropdown reading `Fade` and a **Duration** spinner. If it isn't on screen at all,
menu bar → **Docks** → tick **Scene Transitions**.

1. **Scene Transitions** panel → dropdown → **Cut**.
2. **Duration** → `0` ms. (Greyed out for Cut in some builds — fine.)

The pan *is* the transition. Any fade here would double up and smear it.

**While you're here, verify FPS.** Settings → **Video** → **Common FPS Values**
→ `60`. OBS defaults to 30, and the default survives step 1 if you only changed
resolution. The pan is a 980ms overshoot-and-settle; at 30fps the settle gets
roughly eight frames and reads as a stutter instead of a punch.

---

## 9. Run the test

### 9a. What this step is even for

The finished overlay has to answer one question, constantly: **"which scene is
live right now?"** That's what tells it which panel to pan to.

There are two possible ways for a web page inside OBS to find that out:

- **Path A — `window.obsstudio`.** OBS injects a little object into every browser
  source and fires an event at it when the scene changes. Simple, instant, no
  setup.
- **Path B — the websocket.** The page opens a network connection to OBS and OBS
  reports the scene change over it. More moving parts, and if the connection
  drops, the page goes deaf.

Path A is clearly better. **But we don't know if it works here**, because of how
we built things: the page lives inside `COMIC`, and `COMIC` is *nested inside*
`GAME`, `CAM` and the rest. When you click `GAME`, does OBS bother telling a
browser source buried two levels down? Nobody's documentation says.

So the test page listens on **both paths at once** and shows you a box for each.
Switch scenes, see which boxes light up. That's the whole thing.

### 9b. Open the page so you can click it

A browser source is a web page rendered as a video layer. You can *see* it in the
preview, but clicking there just selects and drags the source — the clicks never
reach the page. OBS has a separate mode for that:

1. In the **Sources** list, right-click `WiringTest`.
2. Choose **Interact**.
3. A new window opens showing the page on its own. Clicks and typing **in this
   window** go to the page.

Keep that window open and positioned so you can see the OBS main window at the
same time. You'll be clicking in OBS and reading results in the Interact window.

Check the top-right of the page first. You want a green dot next to
**websocket: identified** and another next to **obsstudio: present**. If the
websocket dot is red, jump to troubleshooting — the test is only half valid
without it.

### 9c. The scene test

Click these in the **Scenes** panel of the main OBS window, pausing about a second
on each, and watch the two big boxes at the top of the Interact window:

| You click | Left box (`window.obsstudio`) should read | Right box (`obs-websocket`) should read |
| --------- | ----------------------------------------- | --------------------------------------- |
| `GAME`    | `GAME`                                    | `GAME`                                  |
| `CAM`     | `CAM`                                     | `CAM`                                   |
| `BRB`     | `BRB`                                     | `BRB`                                   |
| `GAME`    | `GAME`                                    | `GAME`                                  |

A box flashes yellow when it updates, so you can see which one reacted. Under each
name it shows the time, and if both paths reported the same scene it shows how far
apart they were in milliseconds.

The wide bar underneath states the verdict in words. What it can say:

| Verdict                            | What it means                                                                                                                                     |
| ---------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------- |
| green **PASS**                     | Both paths work. The overlay pans using Path A and only needs the websocket for moving sources around. If the websocket dies, pans still happen.    |
| red **PARTIAL**                    | Only the websocket heard it. Path A doesn't survive nesting. The websocket becomes the single point of failure for panning, so step 7's failsafe matters a lot more. |
| Either box shows `COMIC`           | A trigger scene is built wrong — its contents were made directly instead of adding `COMIC` as a Scene source.                                       |
| Left box updates, right stays `—`  | Websocket never connected. See troubleshooting.                                                                                                    |

Either PASS or PARTIAL is a usable result. This is a *measurement*, not a
pass/fail exam — I need to know which one so step 5 gets written correctly.

### 9d. The ping test

Different question, equally important.

In the finished overlay, the transparent holes in the comic art have real video
behind them, and the overlay has to keep repositioning those OBS sources so they
stay lined up with the holes as the page pans. Those sources live in `COMIC` — but
`COMIC` is never the scene that's actually on screen. `GAME` is. So: **can we move
something inside `COMIC` while `GAME` is what's live?**

1. Click `GAME` in the Scenes panel, so `GAME` is what's on screen (not `COMIC`).
2. In the Interact window, scroll to the table headed **COMIC SCENE ITEMS ·
   TRANSFORM PING**.
3. Find the row for `Cam` and click its **ping** button.

**What should happen:** the orange rectangle jumps to the upper-left area and
becomes 1280 × 720. The `x, y` column for that row changes to `320, 180`.

If the orange rectangle moves, step 6 is unblocked — the overlay can reach through
the nesting and position sources. If it errors, the log line says why.

Click **Restore all** to put everything back where it was.

### 9e. Send me the result

Click **Copy log** at the top of the Interact window, then paste it to me. The log
has the timing numbers for both paths, which is what decides how step 5 is built.

If Copy log doesn't work (clipboard access from a local file is sometimes
blocked), just tell me: the verdict bar's colour and wording, and whether the
orange rectangle moved.

---

## 10. Troubleshooting

**Test page is white / blank.** The URL is wrong. Check the `%20` survived the
paste. Right-click `WiringTest` → **Properties** and read the URL back carefully.

**`websocket: closed` or `socket error`.** Server isn't on — redo step 3. If it is
on, confirm the port there is `4455`.

**Socket closes right after connecting (code 4009).** Wrong password. Tools →
WebSocket Server Settings → Show Connect Info, copy it again, and re-paste the
whole URL into the source properties.

**Buttons don't respond.** You're clicking the preview, not the page. Use
right-click → **Interact** (step 9).

**OBS won't create a scene — the OK button does nothing, or it says the name is
already in use.** A source already has that exact name. Scenes and sources live in
one namespace. Rename the source to TitleCase (`BRB` → `Brb`), then create the
scene. Case-sensitive, so `Game` and `GAME` are fine together.

**Red chips under "Scenes expected" or "Sources expected".** Something's misnamed.
Red = expected but not found. Grey "(extra)" = found but unexpected. Right-click
the item → **Rename** and match the spelling exactly.

**`ping` fails with an error in the log.** Read the log line — it names the source
and the reason. Usually the item was renamed after the last scan; click
**Re-scan**.

---

## 11. When it passes

1. Right-click `WiringTest` → **Remove**. It's a diagnostic, not part of the show.
   (Its URL has your websocket password sitting in it in plain text, which is
   another reason not to leave it lying around.)
2. **Scene Collection → Export** from the menu bar, and keep the file. Rebuilding
   this by hand after a crash is a bad evening.
3. Tell me which of the two paths passed — that decides how step 5 is written.

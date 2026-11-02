# CLAUDE.md — Money Talks Monday

The Monday show's overlay, themed on an Indian ₹2000 note. The frame is one
banknote split across its middle. On a scene switch the two halves slam back
together into one whole note, and a Gandhi coin spins in its empty centre.

This file is what is this overlay's own: its concept, art direction and
layout. How it reaches OBS — scenes, sources, the punch pipeline, audio, the
deck, the vertical canvas, reliability — is shared by every overlay and
lives in the [root `CLAUDE.md`](../../CLAUDE.md), with the working agreement.
The page contract is [core/README.md](../../core/README.md). Decisions go in
[docs/adr/](../../docs/adr/README.md).

**Status, 2026-11-02:** both pages are built, and in OBS as the
`Money Talks Monday` scene collection.

- **Punch sets read back off OBS on both canvases:** all six as in §3.
- **Real-time frames from one GAME → CAM sting** captured on time on both:
  rewind at 151 ms, slam at 404, the coin at 1001, opening at 1551.

**Files.** Both pages run the same `smash.js`, and what they draw alike is in
`money.css` (styles) and `art.js` (plates, socials, the coin's face, the
rosette). Each page keeps only its canvas, its `FRAMES`, `PANELS`, where its
plates sit, and `SOUND`: on for `overlay.html`, off for `vertical.html`.

**How the collection was built.** `Cam`, `Game`, `Browser` and `Chat` were
copied from Hi-Fi Rush before setup ran. Setup then still made `Cam` a
`dshow_input`; since [ADR 0014](../../docs/adr/0014-cam-is-the-iphone-camera.md)
it makes the iPhone's `ios_camera_source` itself.

**Open in that collection:**
- **No mic yet:** Settings → Audio → Mic/Auxiliary Audio, then re-run setup.
- **The passbook `chat.css` does not reach the Restream embed.** It shows
  its own dark default, and its first line runs under the divider. Its
  selectors are the template's YouTube ones; the embed's own DOM has not been
  read yet.

---

## 1. Core concept

**One note, split at its middle.** The top half is the header and the bottom
half the footer. At rest they are pulled apart and the video shows between
them. Their cut edges carry the white borders: the header's border is on its
bottom edge, the footer's on its top edge.

**The note's central rosette is empty, and the coin goes there.** On every
scene switch, the halves close back into one whole note and the coin spins in
the rosette. START, BRB and END are that closed note held on screen. Going
from one of them to GAME plays only the opening half. START → BRB is one spin
and a change of text.

**The rewind has a reason.** The white borders are the seam. They have to be
gone before the halves join, or the closed note would show a white line
across its middle.

## 2. Art direction

### Art files, in `assets/`

| File | What | State |
| --- | --- | --- |
| `note.png` | The note. In use: 1774 × 887 (2:1). Wanted: 3840 × 2160, composed for 16:9 | In use; the re-export would replace it |
| `note-portrait.png` | The note for the vertical canvas, 2160 × 3840 | Waiting on the re-export |
| `gandhi.png` | The coin face: Gandhi in sunglasses with a chain, 1389 × 1132, real alpha | In use |
| `socials/*.svg` | Engraved medallions, one ink (`#6d0a35`) on a hatched ground | Drawn 2026-11-02 |

**How a 2:1 note covers a 16:9 frame:**

- It is drawn at the canvas width plus 24 px bleed on each side, 1968 px wide
  (`BLEED`, so the impact shake never shows an edge). That is 984 px tall,
  scaled 1.11×.
- Each half is then topped up with paper colour: 48 px above the note and 48
  below show when it is shut.
- `NOTE` in `overlay.html` holds the file's own size, and everything derives
  from it. A 3840 × 2160 re-export is a change of two numbers, and the paper
  bands disappear.

**The rosette centre** is at 0.5, 0.43 of the image, read off a crop of
`note.png`. The coin and END's camera window are centred there.

**Palette**, sampled off `note.png` rather than guessed: paper `#fb9fc6` (its
outer edge), ink `#be1860` (its darkest 5%). Deep ink `#6d0a35` and light
paper `#ffe3ef` are for text and plates.

**Muted at rest, full colour in motion.** On 2026-11-02 the user found the
bright pink right for the sting but too loud to sit under a scene. So the
note is drawn through `saturate(0.78) brightness(0.89)` whenever a scene is
settled, and the paper around it is that same colour, `#d292ad`. The first
try, `saturate(0.55) brightness(0.78)`, read too dark; this is halfway back
to full colour.
`#frame.loud`, set by `smash.js` from the rewind until the scene settles,
lifts both back to full colour over 450 ms. The plates, handles and the
coin are not muted, so they now carry the eye.

**No LIVE badge, anywhere.** There was one in every open scene's header
(horizontal) and beside the title (vertical); the user had it removed on
2026-11-02. The platforms already say live.

**Fonts:** Rozha One for display and Devanagari, Cinzel for small capitals,
Space Mono for serial numbers. They load from Google Fonts like the comic's,
until step 9 self-hosts them.

### The coin

- **Gandhi on both faces.** It spins on its vertical axis, like a turntable.
- **The back face is its own copy of the image.** If the front were simply
  seen from behind, it would read mirrored, and the sunglasses and chain would
  flip mid-spin.
- **A flat element has no thickness.** Edge-on it shrinks to a line, so either
  draw a ridged rim or turn fast enough that edge-on lasts only 1–2 frames.
- **No real motion blur.** It is expensive in OBS's browser, so 2–3 faint
  trailing copies stand in for it during the fast turns.
- **It settles with a shine** sweeping across the face.

### Socials

- **Icons:** engraved, single-ink versions of the platform logos in
  `assets/socials/<platform>.svg` ([ADR 0012](../../docs/adr/0012-social-icons-are-each-overlays-art.md)).
  Not drawn yet.
- **Handles:** set like the new series' serial numbers, each character
  bigger than the last, left to right.
- **On GAME:** in the header band.
- **On the closed scenes:** in the two serial-number panels in opposite
  corners, where a real note prints its serial number twice.
- **Motion:** they tick in character by character, like a numbering machine,
  as the frame opens.

### Text on the note

- **It is parody bank text**, e.g. "Bank of Money Talks", and the episode
  number in place of a serial, `MTM 000001`.
- **Never "Reserve Bank of India", the Lion Capital emblem, or the real
  promise clause.** India's law against "documents resembling currency notes"
  (IPC 489E, carried into the BNS) is broadly worded, and parody keeps the art
  clearly outside it.

### Sound

A whoosh as the halves travel, a thud on impact, a ting as the coin lands.

- **Synthesised with Web Audio in `smash.js`**, so there is no file to lose:
  filtered noise, a falling sine, three bell partials.
- **They play through `Overlay`'s audio**, like alerts, so they are in the
  stream mix.
- **`?sfx=0` silences them.**
- **Their level in the mix is not yet heard in OBS.**

## 3. Layout

**Every cam cutout is 16:9**, the shape of the 3840 × 2160 iPhone camera
([ADR 0014](../../docs/adr/0014-cam-is-the-iphone-camera.md)), so the source
fills it with nothing cropped. The user asked for this on 2026-11-02, after a
4:3 notch and a round window cut off too much of the camera.

**The bands are slim.** On the same day the header went from 105–152 px to
62–92, and the footer's widest part from 260 px to 136.

### GAME

The user's drawing, kept in shape, in canvas px on 1920 × 1080:

| Edge | Position |
| --- | --- |
| Header, bottom edge (white) | y 92 at the left → y 70 at the right |
| Cam window, top and right edges (white) | x 0–528, y 783–1080: **528 × 297, 16:9** |
| Footer, top edge (white) | y 1010 at x 528 → y 944 at the right edge |

The first build followed the drawing exactly: header 152 → 105, a 400 × 297
cam (4:3), footer 970 → 820.

- **The edges are not parallel, and that's intended.** The game window
  narrows from right to left.
- **The cam sits in a notch in the footer.** The footer's border runs along
  the cam's top, down its right side, then up the slant.
- **At rest each band shows the strip next to the cut**, not the note's outer
  border. The halves slide.
- **Header:** the socials.
- **Footer:** its thick right end holds the title plate, "MONEY TALKS MONDAY",
  lettered like the numerals on a note.
- **The game is never shrunk.** Its hole is the whole frame (`bare`) and the
  bands are `over` art painted on top of it, so the slants need no core
  change ([ADR 0007](../../docs/adr/0007-holes-are-each-overlays-design.md)'s
  rectangles-only rule holds).
- **The cam hole sits inside the game's**, so `mergeCuts` drops it. `Cam` is
  above `Game` in OBS's stack, which is what makes that work.
- **The bands cover the game's edges:** 70–92 px at the top, 70–136 px at
  the bottom. The thicker end is bottom-right, where games often put a HUD.

### The smash: the transition

It plays on every switch, about 1.9 s in all
([ADR 0013](../../docs/adr/0013-money-talks-monday-smash-replaces-the-pan.md)):

| Time (ms) | What happens |
| --- | --- |
| 0–260 | **Rewind.** Both white borders drain from right to left over a faint track, with a white playhead knob riding the end, like a YouTube progress bar being scrubbed back. The open frame's art fades with them. |
| 260–460 | **Slam.** The halves speed into the middle with no bounce, because it is a collision. On the way, the slanted edges straighten to the flat cut, and the cam notch closes. |
| 460 | **Impact.** The frame shakes 11 px, settling over 280 ms, and the seam flashes. **From here the whole frame is covered, and the holes and the OBS sources change now.** |
| 460–1220 | **Coin.** It stamps into the rosette (1.35× to 1, 160 ms), spins two full turns (520 ms) with two faint ghosts trailing it, and lands with a ting and a shine sweeping across it. |
| 1280–1420 | **The coin shrinks away.** |
| 1420–1780 | **Open.** The halves fly apart into the next scene's frame with a 1.25% bounce. |
| 1670–1970 | **The borders play forward**, left to right, and the art fades in. The handles tick in like a numbering machine. |

- **From a closed scene, only the coin and the open play.** START → GAME
  measured about 1.6 s in slow motion.
- **Between two closed scenes, the coin spins once and the words crossfade.**
  About 0.53 s.
- **Leaving END,** its camera window irises shut first, over 200 ms.
- **The shake happens only while the note is closed**, so the video not
  shaking with it is never visible.

Read from the code and checked by stepping the logic. In OBS, frames from one
GAME → CAM switch landed on time: rewind at 151 ms, slam at 404, the coin at
1001, opening at 1551. The frame rate itself is not measured.

### The closed scenes

| Scene | What's on the note | Video |
| --- | --- | --- |
| START | "STARTING SOON" and the countdown; the coin wobbles slowly, with a shine every ~6 s; the episode serial | None |
| BRB | "I PROMISE TO BE RIGHT BACK", set in the note's promise-line style | None |
| END | "SEE YOU NEXT MONDAY" and the socials | Cam in the rosette, where the coin was |

- **The scene's words sit on a cartouche** on the note's upper-left cloud.
- **The socials sit on a serial-number panel** on its lower-right cloud.
  Both are plain mesh in the art, so the text covers no vignette.
- **START's serial is `MTM` plus the date**, DDMMYY.
- **BRB carries a Hindi promise line** under the English.
- **END puts the camera in the rosette.** The design said the watermark
  window. It was moved on 2026-11-02 because the rosette is the note's
  biggest clear area, and the streamer taking the portrait's place reads
  better than a small oval.
  - **It is 704 × 396, 16:9, with 22 px corners** (`WINDOW`): a mask on the
    frame, an engraved frame around it, and a `Cam` hole of the same size
    behind it.
  - On the way in, the coin shrinks into it as it grows open from the centre.
  - The first build made it a 250 px-radius circle, which cut off nearly half
    the camera.

### CAM and CHAT

**CAM:** the same frame, flatter.

- Header: y 84 → 64. Footer: y 1000 → 976.
- The cam is a full-frame 16:9 hole, like the game. The bands cover 64–84 px
  of its top and 80–104 of its bottom.
- The footer carries a news-style name strap: "The Deep Effect", with "Money
  Talks Monday" under it.

**CHAT:** header y 80 → 62. A slanted strip of the shut note, white on both
edges, splits cam from chat.

- **Cam:** 0, 56, 1280 × 720, 16:9. The header covers its top 12 px and the
  footer its bottom 8.
- **The footer rises under the cam** to y 768–762. Its step down to y 1004
  under the chat follows the divider's left edge, so the two borders are one
  line. The title plate sits in that raised block.
- **Chat:** 1317, 50, 603 × 962. `overlay.json`'s `chat` sizes the `Chat`
  source to exactly that, so nothing is cropped
  ([ADR 0015](../../docs/adr/0015-chat-source-sized-per-overlay.md)).
- **The divider** runs from x 1282–1362 at the top to x 1234–1314 at the
  bottom. It covers the gap between the holes, x 1280–1317, at every height
  the window is open.
- **The divider hides up to ~45 px of the chat hole's left edge.** `chat.css`
  makes that the ruled margin of a bank passbook, but it does not yet reach
  the Restream embed (Status).

**Every hole reaches under the frame's edges with room to spare.** That
covers the open's 1.25% bounce, so no gap ever shows between art and video.

### Punch sets, as built

Read back off OBS on 2026-11-02, from each source's transform in `COMIC`:

| Scene | Holes |
| --- | --- |
| GAME | Game 0,0 1920 × 1080 + Cam 0,783 528 × 297 |
| CAM | Cam 0,0 1920 × 1080 |
| CHAT | Cam 0,56 1280 × 720 + Chat 1317,50 603 × 962 |
| START | None |
| BRB | None |
| END | Cam 608,273 704 × 396 |

**Every cam hole reads 1.778:** the camera's own 16:9.

**The page of panels paints nothing.** Six panels, each exactly the canvas
inside a transparent 15 px border, sit side by side 2000 px apart, and
`smash.js` jumps the page between them while the note is shut. Every visible
pixel is the `#frame` layer above it.

**Outside OBS, punched holes keep their striped stand-ins**
(`body.preview`), so a browser review shows where each source would sit.

### Vertical

1080 × 1920, built 2026-11-02. It is driven by the main canvas's program
scene, so one deck press moves both pages.

**The note is the landscape file turned a quarter anticlockwise**
(`NOTE.rotate: -90`), because there is no portrait art yet.

- Its middle cut becomes the horizontal seam, and the rosette lands on it.
- The engravings lie on their side.
- `note-portrait.png` is a change of `src`, `w`, `h`, `rotate: 0` and its own
  `rosette`.

**Everything is centred on x 540.** The user asked for that on 2026-11-02:
the first build put the rosette left of centre, at x 461, and the plates
followed it.

- **Centring the turned rosette costs a little scale.** The rosette sits 43%
  of the way across the turned note, not half. So the note is drawn just wide
  enough (1312 × 2624, `NOTE_X` −24) that, with the rosette at x 540, it still
  reaches `BLEED` past both edges.
- **The halves stay the canvas width plus bleed** (`HALF_W`), and the note
  layer inside them is clipped.

**Type stays inside `SAFE_*`:** x < 916, 140 < y < 1596. A plate's border
may touch the right rail; its type does not. The bands' parts under platform
chrome are art only. On every open scene the 16:9 cam sits on top, face
first, as on the comic's vertical.

**On GAME and CHAT the cam is small and the content big** (the user asked on
2026-11-02, for phones).

- **The cam:** a 640 × 360 window cut into a band of note (an evenodd
  `path` decor, `camBand()`). The band also carries the title under it.
  On CHAT it starts at y 150, below TikTok's top bar.
- **GAME's whole stack is centred** in the safe area, 140–1596: cam, title,
  game and socials are one block, 264–1464, around its middle, 868. The user
  asked for that on 2026-11-02.
- **Socials are set for phones:** 24 px handles and 44 px medallions (they
  were 17 and 30), on two centred lines under the game and the chat, and
  stacked on CAM and the shut scenes.
- **Every plate sits in a centred row** (`.vrow`) whose top the config
  computes from the layout, so moving a scene moves its plates with it.
- **The game:** 1080 × 608. That is its own 16:9 at the full width: the
  biggest it can be on a 1080-wide canvas without cropping, and 11% bigger
  than the template's 977 × 550. A 4:3 crop (1080 × 812) was tried and
  dropped the same day: the user wants the aspect kept.
- **Chat:** a 526 × 840 column, narrowed from 574 × 916 to make room for the
  bigger socials. `chat.css` zooms the chat page 1.5×, which
  makes its type bigger without needing the embed's markup. The zoom applies
  on both canvases.

| Scene | Layout |
| --- | --- |
| GAME | Header 142 → 130, art only. A centred stack: Cam 220,264 640 × 360 in the band, the title under it, Game 0,716 1080 × 608, socials on two lines under the game (1342) |
| CAM | Header down to 478 → 466, with the title centred (220). Cam 0,456 1080 × 608. Footer from 1062 → 1050 with the name strap and stacked socials, centred |
| CHAT | Cam 220,150 in the band. Chat is a centred column, 277,604 526 × 840: the `Chat` source's own 603:962, and clear of the caption zone. The footer runs along the band, down the column's sides and under it, with the socials on two lines below (1458) |
| START, BRB, END | The scene's words above the coin (170,236 740 × 400), the socials below it (from 1270), all centred. END's window is 880 × 495 at 100,713; its right end runs under the rail, which a picture may |

**Punch sets, read back off OBS:**

| Scene | Holes |
| --- | --- |
| GAME | Cam 220,264 640 × 360 + Game 0,716 1080 × 608 |
| CAM | Cam 0,456 1080 × 608 |
| CHAT | Cam 220,150 640 × 360 + Chat 277,604 526 × 840 |
| START, BRB | None |
| END | Cam 100,712 880 × 495 |

**A 60/40 GAME was previewed and declined, 2026-11-02.** The user asked to
see the split many reels use: 40% cam over 60% game, at Cam 1080 × 699 and
Game 1080 × 1047, with a band of note between them.

- **The cost:** both sources cropped to fill the width, against ADR 0014's
  16:9 rule. The game showed its middle 58%, and its bottom ~30% sat under
  TikTok's captions.
- **The user kept the stacked GAME**, and the preview switch was removed.
- **Where captions go in edits:** the open question that came up. A 60/40
  reel puts burned-in captions at the seam, and the band was already there.
  For the stacked layout the same advice holds: captions under the face, over
  the cam's bottom, leave the band and the game clear.

- **Silent:** `SOUND` is off, because `OverlayV` must not reroute audio (root
  `CLAUDE.md` §2). The horizontal page's sounds are the stream's.
- **Each half is as tall as the farthest resting cut needs.** On the
  vertical CHAT the footer rests above the middle, and the first build left
  it 52 px short of the canvas bottom.

## 4. Build order

One step at a time, each checked before the next:

1. ✅ Per-overlay social icons ([ADR 0012](../../docs/adr/0012-social-icons-are-each-overlays-art.md)).
2. ✅ This folder, copied from the template.
3. ✅ GAME and `smash.js`, checked in a browser. Built against the 1774 ×
   887 note; the re-export is a two-number change.
4. ✅ START, BRB and END; then CAM and CHAT. Reviewed in OBS by the user on
   2026-11-02, then given 16:9 cam cutouts and slimmer bands.
5. 🟨 OBS:
   - ✅ `--overlay money-talks-monday` built the collection.
   - ⬜ A mic for it.
   - ⬜ The chat styling.
   - ⬜ The profile, which is the user's clicks: Profile → Duplicate, then
     Disconnect Account → Use Stream Key.
   - ⬜ The Monday entry in `shows.json`.
6. ✅ The vertical page, on the turned note, in OBS 2026-11-02. ⬜ Portrait
   art when it exists.

## 5. Open

- **The Gandhi image may be a legal issue.** India's Emblems and Names
  (Prevention of Improper Use) Act, 1950, Schedule item 9-A, covers "the name
  or pictorial representation of Mahatma Gandhi". Section 3 bars its use in
  any trade, business or profession without central government permission,
  and one court read that as ruling out commercial use (the Montblanc pen
  challenge). The likelier cost is backlash or mass reports. Raised on
  2026-11-02 and left as the user's call. The coin face is one file to swap.
- **Is ~1.9 s too long for every switch?** The comic's pan is 0.98 s. The user
  chose the full sting everywhere. How it feels across a real stream is not
  yet known.
- **A press during a sting:** see ADR 0013.

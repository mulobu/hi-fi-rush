# 0033 — Neon Nights: a sunset page, and the cruise replaces the pan

- **Date:** 2026-11-19
- **Status:** Built. Both pages render all six scenes in the browser and
  every window's hole was read back at its authored rect (below). Not yet
  in OBS, not yet streamed

## Context

The user asked for an overlay for a GTA VI stream, taking the design from
the look of GTA Vice City, with good transitions.

Mid-build the user added two constraints, in this order:

1. **"do not mention vice city or GTA wordings just theme is inspired by
   them."** The look is the reference; the words are not.
2. **"no need to add txt like neon nights."** The replacement show name
   the overlay had been given was itself unwanted.

So the page carries **no game, studio, city or show name anywhere on
screen**. The only brand on it is the channel's own, `THE DEEP EFFECT`,
and the handles that were already in `core/contract.js`.

`neon-nights` is the folder and the OBS scene collection — an identifier,
never drawn. Renaming it later is `overlays/<new>/` plus `collection` in
`overlay.json`, and [ADR 0010](0010-building-and-choosing-an-overlays-collection.md)
does the rest.

## Decision

### The page is one frame, not a page to pan across

Like Friday's sheet ([0027](0027-fitness-friday-blueprint-sheet-and-word-sting.md)),
each scene is exactly the canvas and the camera never moves. The page of
panels still exists and still paints nothing: it is there for its holes,
which `core/holes.js` punches and fills with OBS sources
([0007](0007-holes-are-each-overlays-design.md)).

### Each scene is a `.cut` layer and an `.over` layer

The split is what lets animated art sit on this page at all.

- **`.cut`** holds everything that must never cross a window — the sky,
  the sun, the city, the grid floor, the scanlines. `cruise.js` sets its
  `clip-path` to `path(evenodd, "<canvas> <holes>")`, so a punched window
  is simply outside the clip and the video shows through.
- **`.over`** holds what is allowed over the video: window frames, their
  tabs, type, the HUD.

**A CSS clip, not an SVG cut.** Friday cuts the windows out of an SVG
background by writing one evenodd `d`, which works because that sheet is
flat. This page is not: the floor scrolls, the palms sway, the sun bleeds,
the neon flickers. Animated art has to be DOM, and DOM inside a clipped
layer is cut for free — one property per switch instead of a second cut
path per animated element. Measured in Chromium: the window placeholders
render through the clip on all six scenes, on both canvases.

The contained-cut rule is the same one the masks follow (root `CLAUDE.md`
§2): under `evenodd` a cut inside another cut flips that region back to
opaque, so `cutPath` drops any hole contained in another before building
the path. That is what makes GAME's cam window work inside its full-frame
game window.

A scene drawn as bands over the game names its own `solid` rects instead,
and takes `sky-bar` — a *horizontal* ramp. A full-canvas vertical sky gives
the top band its dark end and the bottom band its lit end, and the two stop
looking like one HUD.

### The art is generated, not drawn

`art.js` computes everything: the slatted sun, the palms, the art deco
skyline, the car, the radar, the stars, the deco burst, the star field.
No image file but the four social icons ([0012](0012-social-icons-are-each-overlays-art.md)).
Both canvases use the same builders at different sizes, so there is no
second set of assets for the vertical page.

Two facts about the drawing that are easy to get wrong:

- **The sun's slats are a mask, not sky-coloured bars.** The sky behind
  the sun is a gradient, and a bar painted "the sky colour" is right at
  exactly one height. Masked out, the real sky shows through.
- **A palm is drawn 400 × 1000 at `preserveAspectRatio="none"`**, so any
  box that is not 2 : 5 squashes the fronds flat. Every caller keeps
  `h = 2.5w`. The first build did not, and the palms read as poles.

### Type

- **Headlines** are Anton, skewed −9°, filled with a chrome ramp whose
  specular band sits at 51%, over a hard `#2a0845` drop shadow. Each line
  is fitted to its box at boot, so a short line sets bigger than a long
  one; `same` sets a block at its smallest line's size.
- **Signs** are Monoton, drawn as two tubes — a white core and a coloured
  bloom. The social icons are the same two passes.
- **Everything else** is Share Tech Mono.

### The HUD has one real number

The clock is the machine's own and updates every 10 s. Nothing else on
this page has a feed, so nothing else is drawn as a readout: the radar,
the stars and the meters-that-are-not-there are ornament, and are drawn as
ornament. A fake health bar would be a readout that lies.

### The cruise replaces the pan

`cruise.js`, loaded in place of `core/camera-pan.js` (`core/README.md`,
"Another transition"). A switch is:

1. **In, ~300 ms.** The sunset rises from the bottom edge, a lit cyan rule
   at its leading edge and speed streaks running ahead of it.
2. **Covered.** The layout, the windows and the OBS sources change — only
   here, and only while the frame is covered.
3. **The words, 235–310 ms each.** The destination's name slams in as
   chrome, one word at a time, over the sun and the grid; the word before
   it zooms out through the frame as a magenta outline. The last word is
   dark on a sunset flash.
4. **Out, ~320 ms.** The sky keeps going and leaves out of the top.
5. **The tear, 170 ms**, fired 190 ms into the exit so it lands on the new
   scene: eight bands shear on their own steps, over `feTurbulence` static
   and an RGB split.

**Nothing moves that the video shows through.** The motion is all in the
cover, so a window never slides out from under its own frame mid-switch.
That is why the streaks are on the cover's leading edge rather than a
transform on the scene, which was the first build and was wrong.

Three details carried over from Friday's sting, for the same reasons:

- **Newest press wins and presses never queue.** While covered the words
  restart for the new scene; while uncovering, the sky comes back from
  wherever it has got to.
- **The clock decides when a slide has landed, not the animation.** A page
  whose frames stall — a hidden tab, a GPU reset — must still switch, so on
  time the end state is committed wherever the animation got to.
- **The first scene OBS reports settles with no cruise**, so the overlay
  does not play a switch on OBS startup.

### The flash is a ramp, not a strobe

The last word's flash is `radial-gradient(#ffe98a → #ff2d95)`, not flat
gold. A full-frame flat strobe for a quarter of a second is harder to watch
than the beat is worth, and the ramp reads as the sun coming up behind the
word instead.

### The word is centred on the caps, not on the baseline

`skewX(-9)` moves a point left by `0.1585 y`. Compensating at the baseline
centres the word where no ink is and puts the letters about a twelfth of a
frame to the right; the shift is taken at the caps' mid-height. The same
0.1585 is added to the width the word is fitted against, or a two-letter
word runs off both edges at the size the metrics said would fit.

### `Chat` is 440 × 930

Not 540. On the vertical canvas the chat window sits at x 476, so 440 puts
its right edge on 916 — exactly `CANVAS_W - SAFE_RIGHT`. At 540 the last
80 px of every chat line sits under the platform right rail. The source
size is one number for both pages ([0015](0015-chat-source-sized-per-overlay.md)),
so the horizontal page takes the narrower window too.

## Consequences

- A fifth overlay, and the third to replace `core/camera-pan.js` rather
  than use it. `core`'s "Another transition" contract has now carried three
  different ones unchanged.
- The clip-path layer is a pattern Friday's sheet could adopt if it ever
  wants animated art, but there is no reason to change it while it does
  not.
- Nothing is in OBS yet. `tools/obs-setup.py --overlay neon-nights` builds
  the collection; the twelve punch sets have to be read back off OBS the
  way every other overlay's were.
- The fonts come from Google Fonts, like Monday's, Tuesday's and Friday's.
  Self-hosting is still step 9 in the root build order for all of them.

## Rejected

- **A camera pan across a city.** The pan is Hi-Fi Rush's
  ([0013](0013-money-talks-monday-smash-replaces-the-pan.md) and
  [0016](0016-tech-talks-tuesday-glitch-replaces-the-pan.md) both left it
  for the same reason): six scenes on one page means authoring a page six
  frames wide, and this design's hero is a single composed frame.
- **The borrowed HUD as a readout** — money, health, armour, wanted level.
  It is the most recognisable part of the reference and the most dishonest
  thing to draw: four numbers on screen all stream, none of them connected
  to anything. The radar and the stars survive as ornament because they are
  obviously ornament; the numbers did not.
- **An animated grid floor as a DOM layer over the SVG background.** It is
  how the floor is drawn now, but only because the whole `.cut` layer is
  clipped. Over an uncut background it paints straight across every window.
- **A transform on the scene during the switch.** See above: it slides the
  art out from under its own window frames while the video stays put.

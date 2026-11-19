# 0032 — The ECG follows the heart rate, by spacing the beats, not by scrolling faster

- **Date:** 2026-11-07
- **Status:** Built, in `overlays/fitness-friday/`. Driven on both pages
  against the bridge at 58 and 150 bpm. Revises
  [0028](0028-heart-rate-from-our-own-watch-app.md)'s "the ECG keeps its
  drawn speed".

## Context

[0028](0028-heart-rate-from-our-own-watch-app.md) gave Fitness Friday a
live heart rate and left the ECG strip alone, on this reasoning: *"A real
trace scrolls at a constant paper speed, and changing the CSS animation's
duration mid-run makes it jump."* Both halves of that are true. The
conclusion drawn from them was not: the strip stayed pinned at 72 bpm, so
a heart at 150 was drawn beating at 72 beside a readout saying 150.

**What a real trace does.** Paper speed is constant — 25 mm/s. What a
faster heart changes is the distance between complexes, and the QT, which
shortens with rate (Bazett: QT = QTc x sqrt(RR), QTc ~0.40 s in a healthy
adult). What it does **not** change is the complex itself: a QRS is about
90 ms at 50 bpm and about 90 ms at 160.

**What the old trace did.** `ANATOMY.ecg` laid every landmark out as a
fraction of the beat — P at 0.14, R at 0.345, T from 0.5 to 0.66. Correct
P-QRS-T morphology, so it was never the "random waves" it could look like
at 52 px tall; but drawn that way the whole complex stretches and squashes
with the rate, which no heart does. The point was moot while the rate was
frozen, and becomes the bug the moment it is not.

## Decision

**The paper speed is fixed and the scroll animation is never touched.**
`beat` px per beat at 72 bpm fixes it at `beat x 1.2` px/s. The loop
length, the width, the shift and the `animation-duration` are written once
at build and never change, so there is no retiming and therefore no jump —
0028's objection is answered rather than overridden.

**The rate changes how many beats are drawn inside that loop.** `ECG.tune`
rewrites the path's `d` and nothing else; the transform carries on
underneath. `HEART` calls it on every reading, and once at boot with the
design's 72.

**The complex is drawn in seconds, not in fractions of the beat.** P 90 ms,
PR segment 70 ms, QRS 90 ms, then ST and T sharing QT − QRS, with QT from
Bazett. Diastole is whatever is left, and it is the only part the rate
moves. Above ~190 bpm even that runs out, and the whole complex is squeezed
to 94% of the cycle rather than drawn over its neighbour. The T wave is
asymmetric — peak at ~60% — because a real one climbs slower than it falls.

**The beats per loop must be whole**, or the loop's seam would cut a beat
in half, so the rate the trace draws is quantised. The loop is six times
the strip: **measured, within 3.2% between 60 and 180 bpm and 4.8% over 40
to 200** — a beat or two, next to a readout that is exact. Longer loops are
finer and cost path length; at 185 bpm this one is already ~2700 points.

## Consequences

- **The trace and the number agree**, which is the whole point of a live
  readout next to a drawn one.
- **A rate change cannot make the trace jump.** The scroll is untouched;
  only the drawn content changes, and only when the beats-per-loop count
  actually moves — `ECG.tune` returns early when it does not, so most
  readings redraw nothing.
- **It stays a compositor animation.** No `requestAnimationFrame`, no
  canvas, nothing per-frame in JS — which matters on a page CEF is already
  carrying a 7680 x 4320 transform for.
- **The redraw is not free at high rates.** 150 bpm is a ~28 KB path
  string per strip, rebuilt when the count changes. Not measured against a
  running game.
- **The drawn rate is quantised**, as above. If that ever shows, the lever
  is the loop multiplier in `ecgStrip`.

## Rejected

- **Scrolling faster for a faster heart.** It is what the readout seems to
  ask for and it is wrong twice: paper speed is constant on a real trace,
  and changing `animation-duration` on a running animation retimes it, so
  every reading would jolt the strip sideways.
- **Drawing the trace per frame on a canvas.** It would give an exact rate
  with no quantisation and no seam, and it would put a `requestAnimationFrame`
  loop on the overlay for a 600 x 52 strip. Reach for it only if the
  quantisation ever becomes visible.
- **Leaving it at 72.** It was defensible while the live rate was unbuilt.
  With the watch feeding real numbers it is a drawing that contradicts the
  number printed beside it.

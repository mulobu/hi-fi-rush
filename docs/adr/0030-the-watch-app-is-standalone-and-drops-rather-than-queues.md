# 0030 — The watch app is standalone, discards its workout, and drops a reading rather than queueing it

- **Date:** 2026-11-07
- **Status:** Built, in `watch/`. Driven end to end on the watchOS 26.4
  simulator against the bridge and Fitness Friday's page. Never yet run on
  the real watch.

## Context

[0028](0028-heart-rate-from-our-own-watch-app.md) settled the protocol and
built the PC side, and left the app itself to a session on the MacBook,
with three things unresolved: whether an iPhone app is needed beside it,
what plain `http://` to a LAN address needs under App Transport Security,
and what a workout session costs the user.

**Measured here**, Xcode 26.4, watchOS 26.4 simulator (Apple Watch Series 11
46mm), against `heart/heart-bridge.py` and
`overlays/fitness-friday/overlay.html`:

- **The watch simulator synthesises heart-rate samples during a workout
  session**, one every 5.000 s. So the real `HKWorkoutSession` →
  `HKLiveWorkoutBuilder` → delegate path runs on a Mac with no watch in the
  room. An invented feed was written for this and then deleted, because the
  simulator's own data is better evidence and one less thing that could put
  a made-up number on stream.
- **`NSAllowsLocalNetworking` alone is enough for a LAN IP literal.** A post
  to `http://192.168.0.102:4462/hr` went through with no
  `NSAllowsArbitraryLoads` anywhere. 0028 expected to need the exception;
  it did not expect it to cover more than loopback.
- **HealthKit hands a sample over 0.4 to 2.2 s after the timestamp on it**
  (`rx - at` at the bridge, a dozen samples). This is why the page's
  staleness clock is its own and not the watch's `at` — 0028 decided that
  from the YouTube chat clocks; here it is a measured gap in this feed.
- **The whole chain works.** Sample → `POST /hr` → bridge → SSE → the page
  went `live`, the GAME band drew 61 and beat at 968 ms; Stop → the bridge
  logged *no reading for 15s* and the page went `lost` and showed `--`.

**Not measured, and the simulator cannot say:** whether the watch reaches
the PC without the iPhone. The simulator shares the Mac's network stack.

## Decision

**One standalone watchOS app, no iPhone target.** 0028 made a companion
conditional on the watch not reaching the PC alone, and that is still
unknown — but a watch-only app is what gets tested first, and the relay, if
it is ever needed, is an addition rather than a rewrite: the `POST /hr` call
does not change, only who makes it.

**The workout is discarded, never saved.** The session is the only thing on
watchOS that keeps the sensor on and the app alive with the wrist down, so
it has to run; but this is a readout, not a training log. `stop()` calls
`discardWorkout()`, so no five-hour "Other" workout lands in Health after
every stream. **This replaces 0028's consequence** that a session "counts
as a workout" — what it still counts towards, while running, is the
Activity rings, which is not something an app can decline.

**A reading that cannot be sent now is dropped, not queued.** No retry, no
backlog, one request in flight, a 4 s timeout — shorter than the ~5 s
between samples. The page judges a reading stale by when it arrived, so a
late one would be believed as current: worse than none, which shows as
`lost` and is true. A dropped post costs one beat of the readout.

**The address is the only setting**, in `UserDefaults`, typed from the line
the bridge prints. Its check is a `GET /status`, never a `POST`: a test
reading would show on stream as live for the next 15 s.

**The app wears Fitness Friday's palette** — yellow on the royal sheet,
grid and all (`blueprint.css`, [0027](0027-fitness-friday-blueprint-sheet-and-word-sting.md)).
The icon is drawn by `watch/icon.py` rather than stored, the way the camera
LUTs are generated rather than committed.

**It lives in `watch/`**, as 0028 said it would, so the app and the endpoint
it posts to change together.

## Consequences

- **It can be developed and regression-tested with no watch and no PC**, on
  any Mac with Xcode: the simulator feeds real HealthKit samples and the
  bridge runs on macOS. The screen says `SIMULATED BPM` on a simulator
  build, so a screenshot of a test cannot pass for a reading off a wrist.
- **A gap in the readout is honest.** Nothing can arrive late enough to lie.
- **`Go Live` is a deliberate press.** The app does not start the sensor by
  itself when opened — a workout session nobody asked for is a surprise, and
  the one press is at the same moment as the stream's own.
- **It is signed as MuLoBu.** `DEVELOPMENT_TEAM` is `H47UMF8X7W`, MULOBU
  SOFTWARES LLP — also the only *valid* codesigning identity in the build
  machine's keychain, among four Apple Development certificates under
  three different teams. A team is set by ID, never by the name on the
  certificate, and three of those four names would have been wrong.
- **A device build is blocked on an account step, not on code.** Apple
  answers the provisioning request with *PLA Update available … agree to
  the latest Program License Agreement*, so Xcode cannot add the HealthKit
  capability to the App ID and the profile comes back without it. Signing
  the agreement at developer.apple.com unblocks it; nothing in the project
  changes. The simulator strips entitlements and does not enforce them,
  which is why everything above could be measured before this surfaced.
- **The entitlements file carries `com.apple.developer.healthkit` alone.**
  `com.apple.developer.healthkit.access` is clinical health records and
  needs Apple's approval per team and bundle id; an empty array is still a
  request for it and fails a device build. It was written in and taken
  out — the device build is the only thing that catches it.
- **Still open, and it needs the watch:** whether it reaches the PC off the
  iPhone, whether readings keep coming with the wrist down across a whole
  stream, and what it costs the battery.

## Rejected

- **An invented heart rate on the simulator.** Written, then deleted once
  the simulator turned out to feed real samples: it duplicated them, and
  any code that can fabricate a number is a thing that could one day
  fabricate one on stream.
- **A queue with retries.** It is the obvious shape for an unreliable
  network and the wrong one here: everything it delivers is a number the
  page will believe is current.
- **Saving the workout.** It would put an "Other" workout in Health for
  every stream, which is not what the user asked for. `discardWorkout()`
  costs nothing while the session runs.
- **Starting the session when the app opens.** It would hold the sensor
  open any time the app is glanced at.

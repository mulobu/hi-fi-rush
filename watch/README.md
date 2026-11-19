# watch/

**Heart Rate** — the wrist half of [ADR 0028](../docs/adr/0028-heart-rate-from-our-own-watch-app.md).
A watchOS app that holds the heart-rate sensor on and posts every reading to
`heart/heart-bridge.py`, which the overlay pages read. Today only Fitness
Friday shows it.

```
Apple Watch  --POST /hr-->  heart-bridge.py :4462  --SSE /events-->  overlay pages
(this folder)               (heart/)                                 (HEART in sheet.js)
```

| | |
| --- | --- |
| `HeartRate.xcodeproj` | Open it in Xcode. One target, one scheme, no packages |
| `HeartRate/` | The app: six Swift files, `Info.plist`, entitlements, the icon |
| `icon.py` | Draws the app icon. `python3 watch/icon.py` rewrites the PNG |

## The app

One screen: the number, whether the bridge is getting it, a **Go Live /
Stop** switch, and a row that opens the PC's address. It wears Fitness
Friday's palette — yellow on the royal sheet, grid and all — so the wrist
matches the page it drives.

| File | What it is |
| --- | --- |
| `HeartRateApp.swift` | `@main`, and `Feed`: the wiring that sends every reading out |
| `Monitor.swift` | The `HKWorkoutSession` and its `HKLiveWorkoutBuilder` |
| `Poster.swift` | `POST /hr`, and the `GET /status` the address screen checks with |
| `Config.swift` | The address, in `UserDefaults`. The only setting |
| `ContentView.swift` | The two screens |
| `Blueprint.swift` | The palette, the drafting sheet, the beating heart |

**The workout is discarded, never saved.** The session is what keeps the
sensor on and the app alive with the wrist down; nothing else on watchOS
does that. But this is a readout, not a training log, so `stop()` calls
`discardWorkout()` and no five-hour "Other" workout lands in Health.

**No retry, no queue, one request in flight.** The page judges a reading
stale by its own clock, from when it arrived (ADR 0028), so a reading
delivered late would show as current — worse than one that never arrives.
The next sample is ~5 s away and the timeout is 4 s, so a dropped post
costs one beat of the readout and nothing else.

**`Save & Check` does a `GET /status`, never a `POST`.** A test reading
would show on stream as live for the next 15 s.

## Running it

**In the watch simulator, with no watch and no PC.** watchOS's simulator
synthesises heart-rate samples during a workout session — one every 5.000 s
— so the real `HKWorkoutSession` path runs there end to end. That is how
everything below was measured. The screen says `SIMULATED BPM` on any
simulator build, so a screenshot of a test cannot be mistaken for a reading
off a wrist.

```bash
python3 heart/heart-bridge.py
```

```bash
xcodebuild -project watch/HeartRate.xcodeproj -scheme HeartRate -configuration Debug -destination 'platform=watchOS Simulator,name=Apple Watch Series 11 (46mm)' build
```

Install it, then launch with the address already set — `-bridgeHost` is read
straight out of `UserDefaults`, so no typing on a simulated watch:

```bash
xcrun simctl launch booted com.thedeepeffect.overlays.heartrate -bridgeHost 127.0.0.1
```

**On the real watch:** open the project in Xcode, pick the watch as the
destination, Run. `DEVELOPMENT_TEAM` is `H47UMF8X7W` — **MULOBU SOFTWARES
LLP**, which is also the only valid signing identity in this Mac's keychain
(`Apple Development: Deep Manek (45M3CSB9K2)`). Three other Apple
Development certificates are installed and none of them is valid; two of
them are under other teams, so a team picked by name rather than by ID is
easy to get wrong here. Then type the address the bridge printed into the
app, and press **Go Live** before the stream.

**One thing blocks the device build today, and it is an account step.**
A build for a real watch stops at:

> *Unable to process request - PLA Update available: You currently don't
> have access to this membership resource. To resolve this issue, agree to
> the latest Program License Agreement in your developer account.*

Until that agreement is signed at developer.apple.com, Xcode cannot add the
HealthKit capability to the App ID, so the profile comes back without it
and the build fails on the missing `com.apple.developer.healthkit`
entitlement. Sign it, then Run again — automatic signing does the rest. The
simulator is unaffected: it strips entitlements and does not enforce them,
which is why everything above could be measured first.

**The entitlements file carries `com.apple.developer.healthkit` and
nothing else.** `com.apple.developer.healthkit.access` is clinical health
records, and Apple must approve it per team and bundle id before it can go
in a profile — an empty array is still a request for it, and the device
build fails on it. Reading heart rate does not need it.

## Measured, 2026-11-07

On Xcode 26.4, watchOS 26.4 simulator (Apple Watch Series 11 46mm), against
`heart/heart-bridge.py` and `overlays/fitness-friday/overlay.html`:

- **The whole chain runs.** Workout sample → `POST /hr` → bridge → SSE →
  the page went `live` and drew the number: the GAME band showed 61 with
  the heart beating at `--beat: 968ms`. Stop → the bridge logged *no
  reading for 15s* and the page went `lost`, showing `--`.
- **Readings arrive every 5.000 s**, handed over 1–2 s after the timestamp
  on them (`rx - at`, 430 ms to 2.2 s over a dozen samples). That is the
  delay ADR 0028 expected, measured.
- **ATS allows the plain-HTTP post to a LAN address.**
  `NSAllowsLocalNetworking` alone was enough for `http://192.168.0.102:4462`
  — an IP literal in a private range, not just loopback. No
  `NSAllowsArbitraryLoads` anywhere.
- **The build is clean**: no warnings, from scratch.

## Not measured, and it needs the real watch

- **Whether the watch reaches the PC on its own**, off the iPhone. The
  simulator shares the Mac's network stack, so it proves nothing about this
  — it is the one thing ADR 0028 flagged and the one thing still open. If it
  cannot, the fallback is an iPhone app relaying over WatchConnectivity to
  the same `POST /hr`; the PC side does not change.
- **Whether a reading really arrives with the wrist down**, over a stream's
  length, on battery.
- **What a four-hour session costs the watch's battery.**
- **Whether watchOS asks a local-network permission the way iOS 14 does.**
  `NSLocalNetworkUsageDescription` is in the plist in case it does.

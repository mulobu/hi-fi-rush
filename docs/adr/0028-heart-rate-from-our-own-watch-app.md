# 0028 — Heart rate comes from our own Apple Watch app, over HTTP to a bridge

- **Date:** 2026-11-04
- **Status:** Accepted. The PC side is built: `heart/heart-bridge.py` and the
  live readout in Fitness Friday's pages. On 2026-11-05 it was tested with
  the bridge's `--fake` feed, in the browser and in OBS on both canvases.
  The tests covered validation, going live, going lost, and reconnecting.
  **The watch app is not built.** It will be made on the user's MacBook, in
  a later session, against the contract below.

## Context

Fitness Friday draws a beating heart, an ECG and a BPM readout on GAME and
CAM ([0027](0027-fitness-friday-blueprint-sheet-and-word-sting.md)), all
fixed at 72. The user wants their Apple Watch's live heart rate there.

**What exists, researched 2026-11-04:**

- **Pulsoid:** a native Apple Watch app. Its widgets are free, but reading
  the raw number needs a personal token, and its docs say token issuing is
  a BRO (paid) feature.
- **HypeRate:** an Apple Watch app with a paid tier. Its API key is free
  for indie projects, but you have to request it, and users report keys
  that stopped working.
- **Health Data Server:** its overlay and desktop app are open source, but
  the watch app is closed and costs $4.99. It has a local mode. The last
  push was May 2025.
- **Bluetooth heart-rate tools** (pulse-overlay, HRWS): these read a
  standard Bluetooth monitor. An Apple Watch is not one by itself; it would
  need yet another app.

None of them would draw our heart; each would be a widget on top of the
design, or a paid token for the number. The user has a MacBook and chose to
build the watch app themselves.

**What shapes the protocol:**

- **watchOS allows HTTP, not WebSockets.** Apple's
  [TN3135](https://developer.apple.com/documentation/technotes/tn3135-low-level-networking-on-watchos)
  limits low-level networking, which includes `URLSessionWebSocketTask`
  and the Network framework, to audio streaming apps while they stream and
  to VoIP apps during a call. HTTP(S) through `URLSession` is open to every
  app. So the watch sends plain HTTP requests.
- **Readings come about every 5 s.** During an `HKWorkoutSession` with an
  `HKLiveWorkoutBuilder`, developers report about one heart-rate sample
  every 5 s, sometimes 5–10 s late, and no way to ask for more. That comes
  from forum reports; it is not an Apple figure.
- **Not verified:**
  - whether a watch on its own can reach a local network address without
    the iPhone;
  - what plain `http://` to a LAN address needs under App Transport
    Security. Expect an `NSAllowsLocalNetworking` exception.

  If the watch cannot reach the PC directly, the fallback is watch →
  iPhone app (WatchConnectivity) → the same HTTP request. Either way the
  PC side is identical.

## Decision

**The PC side is `heart/heart-bridge.py`.** It is standard library only,
on port **4462** (`ports.heart` in `core/contract.js`), and it listens on
every interface, because the watch is another device on the network.

| Request | What it does |
| --- | --- |
| `POST /hr` | Body `{"bpm": 72, "at": 1730000000000}`. `bpm` must be a number from 20 to 250. `at` is when it was measured, in ms since the epoch, and is optional. A bare number is also accepted. Answers 204; anything else gets 400 with the reason |
| `GET /events` | Server-Sent Events: one `hr` event per reading, data `{"bpm", "at", "rx"}`, where `rx` is the bridge's own receive time. A fresh reading is sent on connect, with a keepalive every 15 s. CORS `*`, because the pages are `file://` |
| `GET /status` | The last reading, its age, and how many pages are listening |
| `--fake` | A synthetic heart rate every 5 s, for testing without the watch |

**The pages read `/events`,** the way `chat/tts.html` reads the chat
bridge. `HEART` in `sheet.js` keeps one of three states on
`body[data-hr]`:

| State | When | What shows |
| --- | --- | --- |
| `design` | No reading yet this session | The drawn 72, as designed |
| `live` | The last reading is under 15 s old | The number, and the heart beating at that rate |
| `lost` | There were readings, and none for 15 s | `--`, dimmed. A number that is not live never shows |

**Staleness is judged by the page's own clock**, from when it received the
reading, never from the watch's `at`. Two clocks disagree, as the YouTube
chat timestamps already showed (root `CLAUDE.md` §2).

**The ECG keeps its drawn speed.** A real trace scrolls at a constant paper
speed, and changing the CSS animation's duration mid-run makes it jump.

**`start.py` starts the bridge** when the overlay's `overlay.json` has
`"heart": true`. Fitness Friday does; the other overlays don't.

**The watch app itself, for the MacBook session:**
- a watchOS app, with a companion iPhone app only if the watch cannot
  reach the PC on its own;
- it runs an `HKWorkoutSession` with an `HKLiveWorkoutBuilder`, which
  keeps the sensor on and the app alive with the screen down;
- it posts each heart-rate sample to `http://<PC address>:4462/hr`;
- it has a setting for the PC's address, which the bridge prints at
  startup.

It goes in `watch/` in this repo, so the app and the endpoint it posts to
change together, unless that session finds a reason not to.

## Consequences

- **No service, account, token or fee.** The data never leaves the house.
- **The watch and the PC must share a network**, or the iPhone relays.
- **The first run on Windows asks to allow Python through the firewall.**
  Allow it on Private networks. This is the one bridge that binds to every
  interface; the chat bridge stays on 127.0.0.1 exactly to avoid that
  prompt.
- **Anyone on the same network can post a number.** It can change only the
  readout, so there is validation and no key. Revisit if the stream is
  ever run off a shared network.
- **A workout session on the watch counts as a workout** in the user's
  Activity rings. This follows from the API and has not been seen yet.

## Rejected

- **Pulsoid:** the raw number needs a BRO token.
- **HypeRate:** the key has to be requested, the app has a paid tier, and
  keys have been reported dying.
- **Health Data Server:** a closed, paid watch app on a project that may
  be slowing.
- **WebSockets from the watch:** TN3135, above.
- **A third-party widget in a browser source:** it would sit on top of the
  design instead of driving it.

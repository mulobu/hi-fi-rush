# heart/

The live heart rate, from the user's Apple Watch to the overlay pages
([ADR 0028](../docs/adr/0028-heart-rate-from-our-own-watch-app.md)). Today
only Fitness Friday shows it.

```
Apple Watch app  --HTTP POST /hr-->  heart-bridge.py :4462  --SSE /events-->  overlay pages
(../watch/)                          (this folder)                           (HEART in sheet.js)
```

| | |
| --- | --- |
| `heart-bridge.py` | The bridge. Standard library only. `start.py` runs it for an overlay whose `overlay.json` has `"heart": true` |
| `--fake` | A synthetic heart rate every 5 s, for testing without the watch |
| `--host 127.0.0.1` | Local only: no firewall prompt, but the watch cannot reach it |

## For the watch app

The app is `watch/` ([ADR 0030](../docs/adr/0030-the-watch-app-is-standalone-and-drops-rather-than-queues.md)),
and it posts to the contract below. The notes after it are what shaped it,
kept here because this is the side that has to keep the promise.

The contract the app posts to:

```
POST http://<PC address>:4462/hr
Content-Type: application/json

{"bpm": 72, "at": 1730000000000}
```

- **The body:** `bpm` is 20–250. `at` is when it was measured, in ms since
  the epoch, and is optional.
- **The reply:** `204` on success; `400` with `{"error": ...}` otherwise.
- **The PC's address:** the bridge prints it at startup.

What shapes the app (ADR 0028 has the sources):

- **Post with `URLSession`.** watchOS allows plain HTTP. WebSockets and the
  Network framework are not allowed for a normal app (Apple TN3135).
- **Run an `HKWorkoutSession` with an `HKLiveWorkoutBuilder`.** That keeps
  the sensor on and the app alive with the screen down. Readings come
  about every 5 s.
- **`http://` to a LAN address will likely need an App Transport Security
  exception** (`NSAllowsLocalNetworking`).
- **If the watch cannot reach the PC on its own**, relay through an iPhone
  app (WatchConnectivity) to the same `POST /hr`.
- **Where it went:** `watch/`, a standalone watchOS app with no iPhone
  target. `watch/README.md` has what the simulator measured, and what
  still needs the real watch.

To test from any machine on the network without the watch:

```bash
curl -X POST http://<PC address>:4462/hr -H "Content-Type: application/json" -d '{"bpm": 88}'
```

The bridge runs on macOS as well (`python3 heart/heart-bridge.py --fake`).
That lets the watch app be built and tested against it on the Mac.

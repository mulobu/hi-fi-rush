# 0006 — Shared page code is plain scripts

- **Date:** 2026-11-01
- **Status:** Accepted, not built (step 6n in `CLAUDE.md` §7)

## Context

- **The two pages are mostly the same code.** `overlay.html` and
  `vertical.html` share 1,010 of their ~1,350 script lines, identical and in
  order (measured 2026-11-01 with a line diff). That is the OBS link —
  websocket client, auth, reconnect, scene detection — and the hole pipeline:
  masks, `mergeCuts`, `chooseWinners`, `fillTransform`, parking, `feed()`.
  Every overlay to come needs the same code.
- **The pages load as `file://`**, on purpose: a browser source never retries
  a page that failed its first load (§2, "`Tts` is `file://`").
- **Chromium refuses ES modules and `fetch()` from `file://`.**

## Decision

- **Shared code goes in `core/` as classic scripts**, loaded with
  `<script src="../../core/x.js">` and exposing globals. No modules, no bundler,
  no build step. Planned files:

  | File | Holds |
  | --- | --- |
  | `contract.js` | Scene and source names, ports |
  | `obs-link.js` | Websocket client, auth, reconnect, scene detection |
  | `holes.js` | Masks, `mergeCuts`, `chooseWinners`, `fillTransform`, parking, `feed()` |
  | `camera-pan.js` | The comic pan |
  | `hud.js` | The `?debug` readout |

- **Each overlay supplies only layout, art and a transition.**
  - The shared code hands the overlay the scene name.
  - The overlay animates and says how long it will take.
  - The shared code tracks the holes for that long, then parks unused sources.
- **The comic pan becomes `camera-pan.js`**, one transition among future ones
  (wipe, stinger, flip), rather than an assumption of the shared code.
- **`contract.js` is `window.X = {…}` around a strict-JSON body**, so Python
  reads the same file by stripping the prefix. One copy of every name, for
  pages and setup alike.

## Consequences

- A fix to the pipeline lands once, for every overlay and both canvases.
- The extraction is a pure refactor. It is checked the way the move was: the
  punch sets read back off OBS must equal the ones recorded in §2 and §5.

## Rejected

- **ES modules or a bundler.** `file://` blocks modules, and a build step is
  one more thing to forget before a stream.
- **Serving the pages over HTTP from a bridge.** A page that fails its first
  load never retries, so the overlay would depend on start order.

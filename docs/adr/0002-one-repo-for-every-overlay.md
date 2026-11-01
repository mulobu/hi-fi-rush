# 0002 — One repo for every overlay

- **Date:** 2026-11-01
- **Status:** Accepted, built (step 2 of [0008](0008-migrate-in-verified-steps.md))

## Context

Three shows on three days of the week, each wanting its own overlay. The scene
list is the same for all of them; design, animation and transitions differ.
The comic overlay was its own repo, `hi-fi-rush`, with everything at its root —
and most of that everything is not about the comic: OBS wiring, audio, the
deck, chat TTS, the mascot engine, the tools.

## Decision

`Overlays/` is the repo. `hi-fi-rush`'s history comes with it: `.git` moved up
and every file was moved with git's rename detection, so `git log --follow`
reaches back through the move.

```
Overlays/
├── CLAUDE.md, README.md, start.py      shared
├── tools/   obs-setup.py, cam-grade.py, hero-asset.py, obs-test.html
├── chat/    bridge, tts.html, blocklist, voices
├── mascot/  mascot.html, bridge/, sets/<name>/ (+ source/ originals)
├── assets/  socials/ (committed); luts/, workshop scratch (ignored)
├── docs/    OBS-SETUP.md, adr/, reference/
└── overlays/<name>/
    overlay.html, vertical.html, chat.css, mascot/placement*.json,
    obs/scenes.json, assets/, mockup.html, CLAUDE.md, README.md
```

- **Lookup is overlay first, then shared.** Pages use explicit relative paths
  (`../../assets/socials/…`); only the Python side may fall back from one to
  the other.
- **Mascot sets are shared, placement is not.** A character can appear in any
  overlay; where it stands is part of that overlay's layout. The cursor bridge
  therefore serves the repo root, but only `/mascot/` and
  `/overlays/<name>/mascot/` — everything else is 404, because the root also
  holds the blocklist, the venv and `.git`. `mascot.html?overlay=<name>` picks
  the placement folder.
- **The chat embed's CSS is the overlay's.** It styles the chat to sit on the
  chat panel's art, so it moved out of `obs-setup.py` (`CHAT_CSS`) into
  `overlays/<name>/chat.css`, byte-identical.
- **`tools/obs-setup.py` stays at a fixed path.** The deck's CLIP and GO LIVE
  buttons run it by absolute path, so after this move they never need
  repointing again.

## Consequences

- One copy of every piece of OBS knowledge, and one `CLAUDE.md` that loads for
  any work in the repo; each overlay's own `CLAUDE.md` loads when its files are
  touched.
- Things outside the repo held the old path and had to follow: five browser
  source URLs in OBS (`Overlay`, `OverlayV`, `Tts`, `Deer`, `DeerV`) and two
  Macro Deck buttons. Recorded in [0008](0008-migrate-in-verified-steps.md).
- The GitHub repo is still named `hi-fi-rush`. Renaming it is open; GitHub
  redirects the old URL.

## Rejected

- **A repo per overlay.** The shared code would be copied three times and drift
  — the pattern `overlay.html` and `vertical.html` already show, sharing ~1,000
  identical lines by copy.
- **Overlays at the top level, beside `chat/` and `tools/`.** No way to list the
  overlays by glob, and an overlay name could collide with a shared folder.

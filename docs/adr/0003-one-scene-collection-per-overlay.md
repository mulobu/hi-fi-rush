# 0003 — One scene collection per overlay; profiles stay per Restream setup

- **Date:** 2026-11-01
- **Status:** Accepted, built 2026-11-01 — see [0010](0010-building-and-choosing-an-overlays-collection.md); the live collection is renamed there

## Context

The ask was a new OBS profile per overlay, switched each show day, keeping the
existing profiles. What each one holds, checked against this machine's
`%APPDATA%\obs-studio` on 2026-11-01:

| | Profile (`basic/profiles/*`) | Scene collection (`basic/scenes/*.json`) |
| --- | --- | --- |
| Holds | canvas, fps, encoder, stream key / Restream setup, delay, replay buffer | scenes, sources, every filter (mic chain, ducks, `CAM OFF`), the global audio devices (`AuxAudioDevice1` is a top-level key), the vertical canvas and `VCOMIC` (`canvases`), transitions |
| Here | `vALO`, `COD`, `Untitled` — one per Restream setup (§2) | one: `Untitled` |

An overlay is everything in the right-hand column. A profile cannot hold one.

## Decision

- **An overlay is a scene collection**, named in its `overlay.json`.
- **Profiles are unchanged.** They stay one per Restream setup and decide which
  game goes out. Collection and profile are independent: any overlay with any
  profile.
- **`obs-setup.py --overlay <name>`** creates the collection if missing
  (`CreateSceneCollection`, which also switches to it) or switches to it
  (`SetCurrentSceneCollection`), then builds it. It refuses to build into a
  collection that is not the overlay's — today it assumes the active
  collection is the comic one, and with three that assumption would build
  `COMIC` into another show.
- **`start.py --overlay <name>`** launches OBS with its `--collection` flag; if
  OBS is already up it switches over the websocket.
- **Never while live.** A collection switch reloads every source, so it is
  refused while `outputs_live` reports anything, the same guard `do_profiles`
  uses.

Unlike profiles, creating a collection from a script is safe. `CreateProfile`
makes a profile wrong five ways (§2, "Duplicate, never New"); a new collection
is merely empty, and everything in it is what `obs-setup.py` already derives.

## Consequences

Per collection, and not carried by the script:

- **Desktop Audio → Disabled** is a dropdown, once per new collection. No
  request reaches it; `do_audio` already refuses per-app capture and warns
  until it is done.
- **The `Chat` embed URL** carries a token. Pasted per collection — or setup
  copies it from a sibling collection on disk, never storing it.
- **Hand-tuned values** — faders, a duck threshold nudged by ear, NV intensity —
  are written by setup only at creation, so a tweak in one show does not reach
  the others.
- **Not measured:** whether Restream's vertical plugin builds a canvas in a
  fresh collection. The canvas is saved inside the collection, but the
  plugin's `config.json` is global and remembers `current_scene: VCOMIC` by
  name. One throwaway collection answers it, offline.

## Rejected

- **A profile per overlay.** Profiles hold no scenes or sources; the existing
  profiles already mean "which Restream setup".
- **Every overlay in one collection.** One source namespace forces unique
  names per show — and then a deck per show — and every overlay's 7680 × 4320
  page would run in CEF at once.

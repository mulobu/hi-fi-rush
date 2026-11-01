# 0004 — One set of scene and source names for every overlay

- **Date:** 2026-11-01
- **Status:** Accepted, not built (written down once in `core/contract.js`,
  step 6n)

## Context

Every show uses the same list of scenes. Three things outside any overlay
address OBS by name:

- **Macro Deck** switches scenes and mutes inputs by name (`set-scene`,
  `set-input-mute`, `set-source-filter`).
- **Restream's vertical plugin** keeps its scene as `current_scene` in a
  `config.json` shared by every collection.
- **Every page and `obs-setup.py`** look sources up by name.

## Decision

Every scene collection uses identical names:

| What | Names |
| --- | --- |
| Trigger scenes | `START` `CHAT` `GAME` `CAM` `BRB` `END` |
| Host scenes | `COMIC`, `VCOMIC` |
| Sources | `Game` `Cam` `Chat` `Browser` `Overlay` `OverlayV` `Mascot` `MascotV` `Tts` `Discord` |
| Filters | `CAM OFF`, the mic chain, the ducks |
| Ports | 4455 obs-websocket · 4460 mascot bridge · 4461 chat bridge |

- Every overlay handles all six trigger scenes. Two may share a layout.
- A new source — a second camera, say — is added to this list once, and then
  any overlay may use it.
- The list is defined once, in `core/contract.js`, as `window.X = {…}` around a
  strict-JSON body: pages load it as a script and Python strips the prefix and
  parses the rest ([0006](0006-shared-page-code-is-plain-scripts.md)).

## Consequences

- One deck profile drives every show, unchanged.
- The host scenes stay `COMIC` / `VCOMIC` even in an overlay that is not a
  comic. The names are internal, and renaming them risks the vertical plugin
  failing to find a scene it remembers by name.
- `Mascot` / `MascotV` replace `Deer` / `DeerV`
  ([0005](0005-mascot-is-optional-and-generic.md)).

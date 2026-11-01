# 0005 — The mascot is optional, and its sources are `Mascot` / `MascotV`

- **Date:** 2026-11-01
- **Status:** Accepted, built and live 2026-11-01 — `Deer` / `DeerV` renamed in place by setup, all four browser sources active after

## Context

The mascot sources are named after the character, `Deer` and `DeerV`. Another
show may have a different character, or none. Every source name is shared by
all overlays ([0004](0004-one-contract-for-every-overlay.md)), so a
character's name has no place in that list.

## Decision

- **Rename the sources** `Deer` → `Mascot` and `DeerV` → `MascotV` in every
  collection. "deer" stays the name of the character: the set is
  `mascot/sets/deer/`, the URL keeps `?set=deer`.
- **Optional per overlay.** `overlay.json` carries `"mascot": { "set": "deer" }`,
  or no `mascot` key. Without one:
  - setup creates neither source;
  - `start.py` does not start the cursor bridge;
  - a `Mascot` already in that collection is reported as a stray, and
    `--prune` removes it like any other.
- **The live collection is renamed in place.** When setup finds `Deer` and no
  `Mascot`, it uses `SetInputName`. The uuid is kept, scene items follow, and
  nothing reloads — rather than creating a new source and leaving the old one
  behind as a stray.

## Consequences

- **The pages need nothing.** `overlay.html` and `vertical.html` never manage
  the mascot (§2: the two pages share one fact, the scene name, and no code).
- **The rename touches** `obs-setup.py` (`stack()`, `MANAGED`, `VERT_STACK`,
  `browser_settings`, the vertical loops, preflight), one line of `start.py`,
  and the docs.
- **Macro Deck is unaffected.** No button references `Deer` — checked against
  the live profile, 2026-11-01.
- **It lands in step 6o, not step 2.** Step 2 is a pure move, so anything that
  broke there could only be a path.

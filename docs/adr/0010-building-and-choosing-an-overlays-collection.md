# 0010 — Building an overlay's collection, and choosing the day's show

- **Date:** 2026-11-01
- **Status:** Accepted, built 2026-11-01. The live migration — `Untitled` →
  `Hi-Fi Rush`, `Deer` → `Mascot` — is not done yet; see Consequences

## Context

[0003](0003-one-scene-collection-per-overlay.md) made each overlay a scene
collection, and [0005](0005-mascot-is-optional-and-generic.md) made the
mascot optional and renamed it. Building that raised questions neither
answered:

- **Which overlay a run builds** when none is named.
- **What `--check` does** when the overlay's collection is not the active one.
- **How an existing collection gets its new name.**
- **How the day's show is picked** at stream time.

## Decision

**`tools/obs-setup.py`**

- **Choosing the overlay.** `--overlay NAME` builds `overlays/NAME`. Without
  it, the script builds the overlay whose `overlay.json` names the active
  collection, and refuses when the active collection belongs to no overlay,
  or to more than one. It never guesses.
- **Changing collection.** When the overlay's collection is not the active
  one, the script switches to it (`SetCurrentSceneCollection`) or creates it
  (`CreateSceneCollection`). It never does either while `outputs_live`
  reports anything. In `--check` it never does either, and exits 1 with
  "would switch to" or "would create".
- **The shared names come from `core/contract.js`.** The script reads its
  strict-JSON body: `TRIGGERS`, the host scenes, the ports, and every source
  name, through `SRC`.
- **The mascot is per overlay.** `stack()`, `managed()` and `vert_stack()`
  include `Mascot` / `MascotV` only when `overlay.json` has a `mascot`. The
  set and the overlay name go into its URL.
- **Old names are renamed in place.** A `Deer` / `DeerV` in a collection
  whose overlay keeps a mascot is renamed with `SetInputName`, before
  anything looks the new names up. Until that has happened `--check`
  reports the rename and stops, rather than report a missing `Mascot`.
- **`--no-profiles` builds the collection only.** A profile is a Restream
  setup, independent of the overlay, and visiting every profile changes
  things unrelated to building one.
- **`--export` takes `--overlay`.** The staleness check runs only when the
  exported collection is the active one: an inactive collection's file is
  current, since OBS writes it out on switching away.

**`start.py`**

- **`--overlay NAME`** launches OBS with `--collection "<its collection>"`,
  and **`--profile NAME`** with `--profile`.
- **An OBS that is already running is switched over the websocket**, using
  `obs-setup.py`'s client, and refused while live.
- **An overlay with no mascot gets no mascot bridge.**

**Renaming a collection** is a click: Scene Collection → Rename. No websocket
request does it. On disk, with OBS closed, it is the file plus its `name` plus
`user.ini`'s `SceneCollection` / `SceneCollectionFile`, and OBS's own file
name for "Hi-Fi Rush" is `HiFi_Rush.json`. OBS's `GetFileSafeName` turns
spaces into `_` and drops anything else not alphanumeric, the way profile
`zz-probe` became the folder `zzprobe` (§2).

## Consequences

- **Verified 2026-11-01**, against the running OBS (still on `Untitled`):
  - plain `--check` refuses, because `Untitled` belongs to no overlay;
  - `--overlay hi-fi-rush --check` reports "would create scene collection
    'Hi-Fi Rush'", which is why the rename has to come first;
  - `--overlay _template --check` reports "would create 'Overlay Template'";
  - an unknown overlay is refused;
  - `--export --overlay hi-fi-rush` writes the collection under the
    overlay's name.
- **Not done yet: the live migration.** It needs the collection renamed in
  OBS. Closing OBS to rename it on disk was refused by the session's
  permission check, rightly, since it was the user's running app. After the
  rename, one `obs-setup.py --overlay hi-fi-rush --vertical --no-profiles`
  renames `Deer` → `Mascot` and `DeerV` → `MascotV`.
- **Until then**, a plain `obs-setup.py` run refuses and names
  `--overlay`, and `start.py --overlay hi-fi-rush` would open OBS on a
  collection that does not exist. `start.py` without `--overlay` works as
  before.
- **`shows.json`** (day → overlay + profile) is not built. It waits for which
  show runs on which day; `--overlay` and `--profile` cover it until then.
- **The `Chat` source is 800 × 938 in every collection**, set by setup.
  Another overlay's chat hole crops it to its own shape. A per-overlay size is
  a small addition to `overlay.json` if one ever needs it.

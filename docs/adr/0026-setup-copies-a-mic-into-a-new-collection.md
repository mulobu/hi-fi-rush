# 0026 — Setup copies a mic into a collection that has none

- **Date:** 2026-11-04
- **Status:** Built; tested on the `Overlay Template` collection, which was
  then restored.

## Context

OBS keeps the global audio devices, Mic/Aux among them, per scene
collection. A collection created by `--overlay` starts with none (measured
2026-11-01).

No obs-websocket request sets one. `GetSpecialInputs` reads them, and
nothing writes them. Setup could only warn: "pick one under Settings →
Audio".

Tech Talks Tuesday and Money Talks Monday sat without a mic for that
reason. The user asked to copy Hi-Fi Rush's: "can we not copy mic from our
actually working with filters and all". It was copied by hand, by editing
each collection's file. Then: "can we also update our obs setup file so mic
is also setup?"

## Decision

- **`do_mic_copy` runs first,** before anything else reads the collection,
  because it reloads it. It acts only when the active collection has no
  `wasapi_input_capture` or `coreaudio_input_capture` input at all.
- **The donor** is `--mic-from NAME`. Without the flag, it is the other
  collection whose file saved a mic most recently, so the mic you last
  used.
- **What is copied** is the donor file's first `AuxAudioDevice*` entry:
  device, settings, filters and fader. It is written in as
  `AuxAudioDevice1`, with fresh uuids for the mic and each filter.
- **How:** OBS holds the active collection's file and rewrites it on the
  way out. Setup therefore:
  1. switches to the donor, which makes OBS save the target and let it go;
  2. backs the target file up as `<file>.before-mic`;
  3. edits the target file;
  4. switches back, so OBS loads it.
- **The mic chain and the ducks follow in the same run.**
  - `do_mic_device` repoints a device this machine no longer offers.
  - `do_mic_dynamics` asserts the order of `EQ`, `COMPRESS` and `LIMIT`.
  - `do_duck` keys `DUCK` off the new mic.
- **Never while live,** because switching collections reloads every
  source. Setup warns instead.
- **Never in `--check`.** It lists the copy as a change, and leaves out the
  "pick one in Settings" warning a planned copy makes untrue.
- **No donor** (a fresh machine, or no collection has a mic): the old
  warning stands.

## Consequences

- **Tested on `Overlay Template`** (no mic, colour placeholders) on
  2026-11-04, nothing live:
  - **The check run** listed the copy alone, from Tech Talks Tuesday, with
    `NV DENOISE`, `EQ`, `COMPRESS` and `LIMIT`.
  - **A bad `--mic-from`** named the three collections that have a mic.
  - **The real run** copied it. `mic1` read `Mic/Aux`, all four filters
    were on, and OBS logged the USB Condenser Microphone initialised.
  - **A second check run** found nothing to change.
  - **Afterwards,** OBS went back to Tech Talks Tuesday, whose check run
    still matched, and the template's file was restored from a copy taken
    before the test.
- **The donor's settings come over as they are.** Hi-Fi Rush's
  `NV DENOISE` is at 1.0 with VAD on. That is not the 0.7 / VAD off the root
  CLAUDE.md records, so every copy so far carries it too.
  `--denoise` asserts only the method, not intensity or VAD.
- **Two more files can appear** in OBS's `basic/scenes`: the `.before-mic`
  backup, and the `.tmp` used for an atomic write. Neither ends in `.json`,
  so neither is listed as a collection.
- **Editing OBS's own file is new for this script.** It is safe only because
  the target is never the active collection while the file is written. A
  setup run killed between the two switches leaves OBS on the donor, with
  the target either untouched or fully written (`os.replace`).

## Rejected

- **Building a mic from scratch in the file.** It would work on a machine
  with no other collection, but the source's saved shape would be
  hand-written and untested, and the user asked for the working mic, filters
  and all.
- **A `wasapi_input_capture` source inside COMIC,** made over the websocket
  as `Discord` is. Whether audio from a scene source reaches the vertical
  stream is not measured. A global device is in every mix.

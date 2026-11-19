# 0031 — Setup runs on macOS: Discord is Windows-only, and a new collection's file lands late

- **Date:** 2026-11-07
- **Status:** Built. Both faults were found by building the four overlays on
  the Mac (OBS on macOS 27.0, websocket 4455), where `--overlay
  money-talks-monday` created the collection and then exited without having
  built anything.

## Context

Every collection so far was built on the Windows streaming PC. The Mac had one
collection, `Untitled`, holding a pre-`0003` build of the comic page. Building
the four current overlays there hit two faults, both of which stop the run
part-way — after the scenes, sources and `Tts`, and before the mic chain,
`CAM OFF`, the transition filter, the Cut transition and the profile pass. A
half-built collection is worse than none, because `--check` then reports the
rest as missing and a second run dies in the same place.

**1. `Discord` cannot exist on macOS.** `do_audio` finds no
`wasapi_output_capture`, concludes per-app audio is safe, and creates `Discord`
as a `wasapi_process_output_capture`. Asked of this OBS, that kind is not
registered: macOS offers `coreaudio_output_capture` and `sck_audio_capture` and
no process loopback at all. `OBS.req` raises on a failed request and `Plan.do`
calls its function bare, so the run dies there.

**2. A collection created over the websocket has no file yet.** `do_mic_copy`
resolved the target's path *before* switching to the donor — and the switch is
the very thing that makes OBS write the target out. Measured: the file appeared
at the same minute as the failure, so OBS did write it, a moment after
`collection_path` had already raised `no collection named 'Money Talks Monday'`.
This is the first time the function has run against a genuinely fresh
collection; the three it is credited with were copied by hand before it existed
([0026](0026-setup-copies-a-mic-into-a-new-collection.md)).

## Decision

- **`Discord` is created only when this OBS registers its kind.** Otherwise
  setup warns, once, and carries on. The question is put to
  `GetInputKindList`, not to `sys.platform`: a kind the binary did not register
  is missing whatever the OS says. `do_duck` already skips `DUCK DISCORD` when
  its key is not an input, so nothing downstream needed changing.
- **Switch first, then look for the file.** `do_mic_copy` switches to the donor
  — which saves the target — and then resolves the target's path through
  `wait_for_collection_file`, which polls `collection_path` for up to 5 s and
  raises its error if the file never appears.

## Consequences

- **Setup completes on macOS**, and on any OBS build without NVIDIA, Aitum or
  obs-shaderfilter: everything missing is now a warning rather than an abort.
- **No Discord audio on the Mac.** Friends' voices reach a Mac stream only
  through a virtual device (BlackHole) or a capture of the whole output — which
  is the comb filter the per-app rule exists to avoid. The Mac is a preview
  machine, so this is a limit, not a problem to solve.
- **A fresh collection is built in one run again,** mic and all.
- **Never ask OBS for the macOS screen-capture display list over the
  websocket.** `GetInputPropertiesListPropertyItems` on a `screen_capture`
  input's `display_uuid` killed OBS 33.0.1 outright here (2026-11-07): the
  socket closed mid-request and the process was gone, with no crash file
  written. `type` enumerated fine; it is the ScreenCaptureKit content list that
  does it. Setup never asks for it, and nothing driving OBS from this repo
  should: pick the display in OBS's own properties dialog.
- **The 5 s is a guess, not a measurement.** The write landed well inside it
  here, once. If a slow disk ever misses the window, the error is
  `collection_path`'s own and the fix is to run setup again — the collection
  exists by then.

# 0032 — Setup names the plugins it cannot install

- **Date:** 2026-11-07
- **Status:** Built. Reported against the live `Tech Talks Tuesday` collection
  on the Mac: two entries, obs-shaderfilter (needed) and iOS Camera Source
  (optional), with the vertical canvas correctly absent because the plugin is
  installed and its canvas exists.

## Context

`tools/obs-setup.py` asserts everything the websocket can reach and reports
what it cannot. Plugins are the second kind: **no obs-websocket request
installs one**, and libobs binds a plugin at process start, so even a script
that copied the binary in could not finish the job without an OBS restart.
They sit beside disabling Desktop Audio, the NVIDIA SDK redistributable,
Browser Source Hardware Acceleration in `global.ini`, and selecting the
canvas in the vertical dock.

Until now each missing plugin was named only where its feature failed:
`--vertical` warned about the canvas plugin, and `do_transition_filter`
warned about obs-shaderfilter, twice, once per host scene. Building all four
overlays on the Mac showed the cost of that: you learn the vertical canvas
needs a plugin on the day you first pass `--vertical`, and that the
transition needs one only once a switch cuts instead of bending. The user,
asked whether setup should name them up front: "Yes, add it".

## Decision

**`do_plugins` runs beside `preflight`, on every run, and reports only.**
One block, listing each plugin this overlay can use that OBS has not loaded,
what it costs to go without, and where to get it.

| Plugin | Detected by | Needed when |
| --- | --- | --- |
| obs-shaderfilter | `shader_filter` in the filter kinds | the overlay's `overlay.json` names a `transition` |
| A vertical canvas plugin | `vertical_canvas()` finds a canvas | `--vertical`; listed as optional otherwise |
| iOS Camera Source | `ios_camera_source` in the input kinds | never — always optional |
| NVIDIA Audio Effects SDK | `nvidia_audiofx_filter` in the filter kinds | only mentioned with `--denoise` |

- **Each entry says whether the overlay needs it now.** A missing plugin is
  often a deliberate choice — no iPhone on this machine, no RTX card — and a
  warning that cannot tell the difference is one you learn to skip.
- **The detection is OBS's own kind list, not the filesystem.** A plugin
  installed but not loaded (wrong architecture, failed link, installed while
  OBS was running) is missing as far as the overlay is concerned, and the
  fix is the same: restart OBS.
- **The vertical entry cannot tell "no plugin" from "no canvas added",**
  because a canvas is the only thing the websocket can see. The line says
  both.
- **`do_transition_filter` keeps its per-scene warning** — it names the
  consequence for that canvas — but no longer repeats the install advice.
- **Nothing is installed or downloaded.** Asserting a scene graph you can
  read back is a different trust level from fetching an executable; a `.pkg`
  wanting admin rights is not a Python script's business.

## Consequences

- **A fresh machine learns the whole list on its first run**, before it goes
  looking feature by feature.
- **The URLs will rot.** They are in one dict, `PLUGIN_URLS`, for that
  reason.
- **The list is hand-maintained.** A plugin a future overlay depends on has
  to be added here; nothing derives it.
- **It says nothing about versions.** Aitum 1.6.4 and Restream's 1.2.0 are
  both "a vertical canvas plugin" to this check, though only Restream's
  answers the websocket vendor `--go-live` needs. That distinction lives in
  the URL line, not in the detection.

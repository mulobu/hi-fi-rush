# 0025 — Setup owns an overlay's transition filters

- **Date:** 2026-11-04
- **Status:** Built; tested against the live collection. Supersedes the
  manual filter steps in [0022](0022-tech-talks-tuesday-floor-tilt-grid.md)
  and [0024](0024-tech-talks-tuesday-vertical-page.md).

## Context

Tech Talks Tuesday's 3D grid runs as an obs-shaderfilter filter,
`Botanical Grid`, one on COMIC and one on VCOMIC. Both were made by hand
over the websocket. That had two costs:

- **A fresh machine or an imported collection had no transition.** The
  pages fell back to a cut.
- **Every shader edit meant recreating both filters by hand,** then
  refreshing both pages. The plugin compiles the file only when a filter is
  created; setting `shader_file_name` again recompiles nothing, and its
  Reload button is out of the websocket's reach.

The user, asked whether setup should create them: "yes add it".

## Decision

- **`overlay.json` names the transition.** The block is `"transition":
  {filter, shader, settings, vertical}`. Tech Talks Tuesday's:
  - `filter`: `Botanical Grid`, which must match `FILTER` in `fusion.js`;
  - `shader`: `grid-bend.shader`;
  - `settings`: `Duration` 1.8, written on both canvases;
  - `vertical`: `Grid_Columns` 54, for VCOMIC only.

  An overlay without the block gets no filter, so Hi-Fi Rush and Money
  Talks Monday are untouched.
- **`do_transition_filter` asserts it on each host scene.** COMIC is
  addressed by name. VCOMIC is addressed by `sourceUuid`, from inside
  `do_vertical`, because a vertical scene is "not found within the canvas
  Main" by name, filters included.
  - **Missing:** created off, at index 0. Only creation writes `settings`
    and `vertical`; after that, columns, relief and wave are taste.
  - **Pointing at another file** (an imported collection, a moved repo):
    recreated with what it held, never repointed, since repointing compiles
    nothing.
  - **Not at index 0:** moved there.
  - **A compile error:** warned, with the plugin's own message.
  - **Enabled state:** never touched. It belongs to the page.
  - **No `shader_filter` kind in OBS:** warned, naming where the plugin
    goes.
- **`--recompile` recreates both filters** after a shader edit, with their
  settings carried over. Neither a recreation nor `--recompile` runs while
  anything is live; setup warns instead.
- **A new filter shows nothing while it exists enabled.**
  `CreateSourceFilter` makes every filter enabled. Setup therefore creates
  it at `Progress` 0, where the shader passes the picture through untouched,
  switches it off, then sets `Progress` back to automatic.
- **The page finds a filter that appears later.** `GridFX.attach` retries
  every 5 s until the filter exists, so no reload is needed after setup
  makes it. The HUD notes the first failure only.

## Consequences

- **Tested against the live collection on 2026-11-04, nothing live:**
  - With the hand-made filters in place, a check run reported "scene
    collection matches".
  - Both filters were removed and both pages reloaded. A check run then
    listed exactly two additions, and the real run made them.
  - **Both pages found the new filters without a reload.** Three switches
    turned each filter on at 0.07 s and off at 1.91 s.
  - **Both render.** VCOMIC was captured as a mesh at 30% and as the
    edge-on line at 47%; COMIC as a mesh at 30%.
  - `--recompile` recreated both, VCOMIC keeping its 54 columns, and the
    next check run matched.
  - Six switches with both canvases transitioning: **0 of 866** frames
    skipped.
- **After a shader edit** the steps are `python tools/build-tuesday-grid.py`,
  then `python tools/obs-setup.py --vertical --recompile`. No page refresh
  is needed.
- **`--export` keeps working.** It already turns the repo path into
  `{{REPO}}`; on import the filter points at that token, and the next setup
  run recreates it on the real path.
- **The filter name lives in two places,** `overlay.json` and `fusion.js`:
  the page is `file://` and cannot read `overlay.json`. If they disagree,
  setup makes one filter and the page waits for another.

## Rejected

- **Repairing the path with `SetSourceFilterSettings`,** as the grade's LUT
  path is repaired. The plugin would hold the old compile, and the filter
  would look fixed while running stale code.
- **Refreshing `Overlay` and `OverlayV` from setup** after creating a
  filter. It resets the page's state (the countdown) and needs a step setup
  has never taken; a page that heals by itself matches how the vertical page
  rebinds its sources.

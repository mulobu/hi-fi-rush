# 0009 — Pages plug into `core/` through one `PAGE` object

- **Date:** 2026-11-01
- **Status:** Accepted, built 2026-11-01. Refines [0006](0006-shared-page-code-is-plain-scripts.md)

## Context

[0006](0006-shared-page-code-is-plain-scripts.md) put the shared page code in
`core/` without saying how a page and core divide the work.

Extracting it settled that. With comments and blank lines stripped,
`overlay.html` and `vertical.html` shared 730 of 789 code lines outside
`PANELS` and `artFor`. Every difference fell into one of these:

- **The page's own data:** page and canvas size, the vertical safe zones.
- **Which scene it drives:** `COMIC` by `sceneName`; `VCOMIC` by `sceneUuid`,
  which has to be resolved first.
- **What happens on connect, on close, on a short item list, and on a failed
  read:** the vertical page resolves, forgets, retries and re-resolves.
- **Two extra debug lines**, and the HUD's name.
- **Two spellings of SHA-256.**
- **`restScale` vs `scaleFor`.**
- **The `obsstudio` startup seed**, which only the horizontal page used.

## Decision

- **One hooks object.** Each page defines `PAGE` with `label`, `host`,
  `hostKey()`, `onIdentified()`, `onClosed()`, `onItemsMissing()`,
  `onItemsFailed()` and `hudState()`. Core calls these and nothing
  page-specific, so a third page needs no change in core.
- **Blocks moved verbatim** from `overlay.html`. The edits were only the
  hooks, the contract lookups, and turning load-time side effects into
  functions.
- **Three more files than 0006 listed**, along the lines the code already
  had: `base.js` (`params`, `DEBUG`), `socials.js` (handles from the
  contract, `socialsFor`) and `panel-page.js` (building the page from
  `PANELS`).
- **Nothing runs at load except `panel-page.js` building the DOM.** The
  page's last script is the boot sequence, so no call can reach a
  declaration that has not been evaluated. Before, one 2,000-line script
  leaned on hoisting, and comments warned about the temporal dead zone.
- **The horizontal SHA-256 is the one kept.** It returns the standard
  `ba7816bf…15ad` for `"abc"`, and both pages authenticate with it.
- **`restScale` is renamed `scaleFor`**, the vertical page's name, since
  `fitTagsToSafeArea` already used it.
- **`camera-pan.js` is the swappable part.** A page with a different
  transition replaces it with a file defining `current`, `transformFor(t)` and
  `goTo(t, {instant})`. The contract is in `core/README.md`.

## Consequences

- `overlay.html` 2,254 → 1,247 lines, `vertical.html` 2,358 → 1,476; `core/` is
  ~1,100. A pipeline fix lands once.
- **Debug-text-only changes:** the vertical page now says "host scene,
  ignored" when `COMIC` itself is put on program (it said "not a mapped
  scene"), flags unmapped scenes as warnings like the horizontal page, and
  says "plain browser" outside OBS.
- **Verified 2026-11-01 against OBS 32.2.2**, after reloading `Overlay` and
  `OverlayV`:
  - all twelve punch sets match `CLAUDE.md` §2 and §5;
  - the vertical GAME windows land at the documented 977 × 550 at y 200
    and y 778;
  - the vertical page's safe-area pass still raises the tags;
  - neither page logs a console error.

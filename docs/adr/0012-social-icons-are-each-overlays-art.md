# 0012 — Social icons are each overlay's art

- **Date:** 2026-11-02
- **Status:** Accepted, built

## Context

The second show, Money Talks Monday, is themed on a banknote. Its socials need
to look engraved, like the rest of the note. Socials were already partly per
overlay:

- **Placement, size and layout:** set in each panel's `socials` entry.
- **Styling:** each page's own CSS (`.socials`, `.cut`, `.handle`).
- **Handles:** shared, in `core/contract.js`. They are the brand's accounts,
  not a design.

The icon art was the one shared part. `core/socials.js` loaded it from the root
`assets/socials/` (ADR [0002](0002-one-repo-for-every-overlay.md)'s layout),
and those four SVGs are the comic's paper cut-outs: the files themselves say
"scissor-faceted paper, ink edge". Every new overlay would have shown comic
icons.

## Decision

- **Each overlay draws its own icons:** `overlays/<name>/assets/socials/<platform>.svg`,
  one per platform in the contract.
- **`socialsFor()` loads `assets/socials/<platform>.svg` relative to the page.**
  That is the same path the root folder had, read from the overlay's folder
  instead. Both of an overlay's pages share one set.
- **The comic's four SVGs moved, unchanged,** to `overlays/hi-fi-rush/assets/socials/`.
- **The root `assets/` is now only the workshop**, and all of it is ignored.
  The rule is `/assets/`, anchored to the root, because a bare `assets/`
  would match every overlay's `assets/` too.
- **The template carries no icons,** because it shows no socials. Its README
  says to draw them before giving a panel `socials`.

## Consequences

- A new overlay that adds `socials` without drawing icons shows Chromium's
  broken-image box with the platform name. The page does not fail silently.
- A new platform in the contract needs an icon in every overlay that shows
  socials.
- An overlay cannot borrow another's icons by path. To reuse them, copy the
  files.
- Supersedes only the `assets/ socials/ (committed)` line of
  [0002](0002-one-repo-for-every-overlay.md)'s layout. The rest of 0002 stands.

## Rejected

- **Icons shared, restyled with CSS.** CSS can recolour and filter a finished
  drawing, but it cannot turn a paper cut-out into an engraving.
- **A shared default set with a per-overlay override.** Overlay-first lookup
  is something only the Python side may do (0002). A `file://` page has no
  fallback when a file is missing, so the page would need to know which set
  to load anyway.

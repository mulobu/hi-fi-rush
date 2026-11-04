# 0023 — Tech Talks Tuesday: phosphor replaces pink

- **Date:** 2026-11-03
- **Status:** Built; in OBS. Supersedes [0020](0020-tech-talks-tuesday-pink-fusion.md)'s pink palette; its layout, type and ASCII flowers stay.

## Context

The user, on the pink fusion page: "find some better tech like colors, pink
is not good". Three candidates were drawn from palette research:

- **Phosphor.** Green-phosphor terminal. Green in the `#33ff33`–`#33ff66`
  range is the classic value, and `#4ade80` is the softer green that has
  become the terminal look. The grounds are tinted near-black, not pure
  black, as the phosphor references advise.
- **Cyber Lime.** Filmora's palette: charcoal navy `#111827`, lime
  `#d4ff1a`, aqua `#00e0b8`.
- **Midnight.** A developer-tools navy `#0d1b2a` with electric cyan
  `#22d3ee` and an iris violet `#8f96ff`.

Each was rendered on the real page (START and CHAT, headless Edge, its
flowers recoloured with it) and shown side by side. The user picked
**Phosphor**.

## Decision

- **The page.** Every colour in `tech.css` is now a variable on `:root`,
  and those defaults are phosphor:
  - ground `#0b110d` and footer band `#08100b`;
  - ink `#c9f7d6` and terminal green `#4ade80` for the accent and live dot;
  - specimen disc `#12301e` → `#0b1a11`, with green hairlines.

  The only hard-coded colours left are in the debug HUD.
- **The flowers.** `THEMES.phosphor` in `flowers.js` is the default theme:
  - sunflowers amber (`#ffb000` ramp);
  - tulips phosphor cyan (`#22d3ee` ramp);
  - foliage green (`#4ade80` ramp).
- **Theme switching.** A theme may carry `css`, which `fusion.js` writes
  onto `:root` at load. `?bg=pink`, `?bg=lime` and `?bg=midnight` still
  preview the others on the real page, pink with its original values.
- **The transition** takes the palette: the line glows `#4ade80` with a
  pale green core, and the ground around the floor is the page's
  `#0b110d`. These are `GLOW`, `GLOW_CORE` and `GROUND` in
  `grid-surface.shader`.

## Consequences

- **The vertical page is untouched.** `vertical.html` does not load these
  files.
- **On dark scenes the relief inverts.** Bright text rises out of the
  dark ground in the transition, where on pink the page rose and the text
  sank.
- **Verified in OBS:** all six scenes captured, punch sets unchanged, and
  a GAME → START switch captured with the green line.
- **The refactor fixed a fault.** The first variable pass had left
  `--disc-rim` and `--orbit` defined as themselves, which is invalid. It
  only showed on the default theme.

## Rejected

- **Cyber Lime** and **Midnight:** shown and not chosen.
- **Keeping pink for the flowers only:** the page and the flowers would
  disagree, so the tulips take the palette's second colour instead.

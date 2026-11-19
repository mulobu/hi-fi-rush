# Decision records

One file per decision, so that later we can see why something is the way it
is — and why it changed.

| # | Decision | Date | Status |
| --- | --- | --- | --- |
| [0001](0001-record-decisions-as-adrs.md) | Record decisions as ADRs | 2026-11-01 | Accepted |
| [0002](0002-one-repo-for-every-overlay.md) | One repo for every overlay | 2026-11-01 | Accepted, built |
| [0003](0003-one-scene-collection-per-overlay.md) | One scene collection per overlay; profiles stay per Restream setup | 2026-11-01 | Accepted, built, live |
| [0004](0004-one-contract-for-every-overlay.md) | One set of scene and source names for every overlay | 2026-11-01 | Accepted, built |
| [0005](0005-mascot-is-optional-and-generic.md) | The mascot is optional, and its sources are `Mascot` / `MascotV` | 2026-11-01 | Accepted, built, live |
| [0006](0006-shared-page-code-is-plain-scripts.md) | Shared page code is plain scripts | 2026-11-01 | Accepted, built |
| [0007](0007-holes-are-each-overlays-design.md) | Holes are each overlay's design; the pipeline's rules are shared | 2026-11-01 | Accepted |
| [0008](0008-migrate-in-verified-steps.md) | Migrate in verified steps | 2026-11-01 | Accepted; steps 1–5 verified |
| [0009](0009-pages-plug-into-core-through-page-hooks.md) | Pages plug into `core/` through one `PAGE` object | 2026-11-01 | Accepted, built |
| [0010](0010-building-and-choosing-an-overlays-collection.md) | Building an overlay's collection, and choosing the day's show | 2026-11-01 | Accepted, built, live |
| [0011](0011-new-overlays-start-from-the-template.md) | New overlays start from `overlays/_template/` | 2026-11-01 | Accepted, built, verified in OBS |
| [0012](0012-social-icons-are-each-overlays-art.md) | Social icons are each overlay's art | 2026-11-02 | Accepted, built |
| [0013](0013-money-talks-monday-smash-replaces-the-pan.md) | Money Talks Monday: the smash replaces the pan | 2026-11-02 | Accepted; both pages built, in OBS |
| [0014](0014-cam-is-the-iphone-camera.md) | `Cam` is the iPhone camera, and cam cutouts are 16:9 | 2026-11-02 | Accepted, built |
| [0015](0015-chat-source-sized-per-overlay.md) | The `Chat` source is sized per overlay | 2026-11-02 | Accepted, built |
| [0016](0016-tech-talks-tuesday-glitch-replaces-the-pan.md) | Tech Talks Tuesday: a text-mode screen, and the glitch replaces the pan | 2026-11-02 | Superseded by 0017 |
| [0017](0017-tech-talks-tuesday-stitch-look-replaces-text-mode.md) | Tech Talks Tuesday: the stitch look replaces text mode | 2026-11-03 | Superseded by 0018 |
| [0018](0018-tech-talks-tuesday-terminal-garden.md) | Tech Talks Tuesday: the terminal garden, and a CRT for the switch | 2026-11-03 | Accepted, built; horizontal only, in OBS |
| [0019](0019-tech-talks-tuesday-botanical-palette.md) | Tech Talks Tuesday: restrained botanical palette and clustered flowers | 2026-11-03 | Built; awaiting visual review; revises 0018's art direction |
| [0020](0020-tech-talks-tuesday-pink-fusion.md) | Tech Talks Tuesday: modern pink framing, ASCII flowers, video grid deformation | 2026-11-03 | Built; pink palette superseded by 0023 |
| [0021](0021-tech-talks-tuesday-shared-grid-surface.md) | Tech Talks Tuesday: shared shader, travelling fold and retained picture colour | 2026-11-03 | Surface, timing and colour superseded by 0022; shared-body build stands |
| [0022](0022-tech-talks-tuesday-floor-tilt-grid.md) | Tech Talks Tuesday: the grid waves, tilts back into a floor and cuts on a line | 2026-11-03 | Built; browser and OBS verified with a game running; 0/866 skipped frames |
| [0023](0023-tech-talks-tuesday-phosphor-palette.md) | Tech Talks Tuesday: phosphor replaces pink | 2026-11-03 | Built; in OBS, chosen by the user from three |
| [0024](0024-tech-talks-tuesday-vertical-page.md) | Tech Talks Tuesday: the vertical page shares the fusion engine | 2026-11-04 | Built; in OBS on VCOMIC, read back; 0/866 skipped with both canvases; hand-made filters superseded by 0025 |
| [0025](0025-setup-owns-the-transition-filters.md) | Setup owns an overlay's transition filters | 2026-11-04 | Built; tested against the live collection, `--recompile` included |
| [0026](0026-setup-copies-a-mic-into-a-new-collection.md) | Setup copies a mic into a collection that has none | 2026-11-04 | Built; tested on `Overlay Template`, then restored |
| [0027](0027-fitness-friday-blueprint-sheet-and-word-sting.md) | Fitness Friday: a blueprint sheet, and the word sting replaces the pan | 2026-11-04 | Built; both pages in OBS 2026-11-05, punch sets read back |
| [0028](0028-heart-rate-from-our-own-watch-app.md) | Heart rate comes from our own Apple Watch app, over HTTP to a bridge | 2026-11-04 | Accepted; both sides built — the watch app is 0030 |
| [0029](0029-setup-copies-the-hardware-sources.md) | Setup copies Game, Cam, Browser and Chat's url into a collection that has them unset | 2026-11-05 | Built; tested on `Fitness Friday` by blanking and restoring |
| [0030](0030-the-watch-app-is-standalone-and-drops-rather-than-queues.md) | The watch app is standalone, discards its workout, and drops a reading rather than queueing it | 2026-11-07 | Built; whole chain driven on the watchOS simulator; never run on the real watch |
| [0031](0031-setup-runs-on-macos.md) | Setup runs on macOS: `Discord` only where OBS registers its kind, and a new collection's file is waited for | 2026-11-07 | Built; both faults found building the four overlays on the Mac |
| [0032](0032-setup-names-the-plugins-it-cannot-install.md) | Setup names every plugin the overlay can use that OBS has not loaded, and installs none | 2026-11-07 | Built; reported against the live Tech Talks Tuesday collection |
| [0032](0032-the-ecg-follows-the-rate-at-a-constant-paper-speed.md) | The ECG follows the heart rate, by spacing the beats, not by scrolling faster | 2026-11-07 | Built; driven on both pages at 58 and 150 bpm; revises 0028 |
| [0033](0033-neon-nights-sunset-page-and-the-cruise.md) | Neon Nights: a sunset page cut by a CSS clip-path, and the cruise replaces the pan | 2026-11-19 | Built; both pages render all six scenes in the browser; not yet in OBS |

Decisions taken before 2026-11-01 are in the table in `CLAUDE.md` §3, with
their reasoning in §2. They are not back-filled here.

## Writing one

- **Name:** `NNNN-short-title.md`, the next number. Numbers are never reused or
  renumbered.
- **When:** in the same change as the decision — a new rule, a reversal, or a
  choice between real options. Not for a fix that changes no rule.
- **Changing your mind:** write a new ADR that supersedes the old one. In the
  old one, change only its Status line, to `Superseded by NNNN (date)`. The
  rest stays as written, because what we believed then is the point.
- **Measured or not:** say which. "Not measured" is an honest status; a guess
  written as a fact is not.
- **Scope:** an overlay-only decision goes here too, with the overlay named in
  the title.

```markdown
# NNNN — Title

- **Date:** YYYY-MM-DD
- **Status:** Proposed | Accepted | Accepted, not built | Superseded by NNNN (date)

## Context
What forced a decision. Facts, with how each was established.

## Decision
What we do, stated so it can be checked.

## Consequences
What this costs, what it makes easy, what it leaves open.

## Rejected
The alternatives and why each lost. Optional.
```

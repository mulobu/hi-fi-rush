# Decision records

One file per decision, so that later we can see why something is the way it
is — and why it changed.

| # | Decision | Date | Status |
| --- | --- | --- | --- |
| [0001](0001-record-decisions-as-adrs.md) | Record decisions as ADRs | 2026-11-01 | Accepted |
| [0002](0002-one-repo-for-every-overlay.md) | One repo for every overlay | 2026-11-01 | Accepted, built |
| [0003](0003-one-scene-collection-per-overlay.md) | One scene collection per overlay; profiles stay per Restream setup | 2026-11-01 | Accepted, not built |
| [0004](0004-one-contract-for-every-overlay.md) | One set of scene and source names for every overlay | 2026-11-01 | Accepted, not built |
| [0005](0005-mascot-is-optional-and-generic.md) | The mascot is optional, and its sources are `Mascot` / `MascotV` | 2026-11-01 | Accepted, not built |
| [0006](0006-shared-page-code-is-plain-scripts.md) | Shared page code is plain scripts | 2026-11-01 | Accepted, built |
| [0007](0007-holes-are-each-overlays-design.md) | Holes are each overlay's design; the pipeline's rules are shared | 2026-11-01 | Accepted |
| [0008](0008-migrate-in-verified-steps.md) | Migrate in verified steps | 2026-11-01 | Accepted, step 2 done |
| [0009](0009-pages-plug-into-core-through-page-hooks.md) | Pages plug into `core/` through one `PAGE` object | 2026-11-01 | Accepted, built |

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

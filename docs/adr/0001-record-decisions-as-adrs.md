# 0001 — Record decisions as ADRs

- **Date:** 2026-11-01
- **Status:** Accepted

## Context

Until now every decision lived in `CLAUDE.md`: a one-line row in the §3 table,
with the reasoning somewhere in §2's prose and the date, when there was one,
inside a sentence. That worked for one overlay built in one stretch. With three
shows, each with its own overlay, decisions will be revisited months apart and
by different sessions, and the question will be "why did we change this?" —
which a table row that has been edited in place cannot answer, because the old
reasoning is gone.

## Decision

Every decision from 2026-11-01 on gets its own dated file in `docs/adr/`,
written in the same change as the decision. Format, naming and the
supersede rule are in [README.md](README.md). A decision is never edited
after the fact: changing it means a new ADR that supersedes the old one, whose
Status line alone is updated.

## Consequences

- `CLAUDE.md` §3 stays as the one-glance summary; ADRs are the record. Decisions
  taken before 2026-11-01 are not back-filled — §2 and §3 already hold them.
- The working agreement (`CLAUDE.md` §9) now says so, so a session that only
  reads `CLAUDE.md` still knows to write one.
- Overlay-only decisions go here too, with the overlay named in the title,
  rather than in a directory per overlay — one place to look.

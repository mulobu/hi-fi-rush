# 0008 — Migrate in verified steps

- **Date:** 2026-11-01
- **Status:** Accepted. Steps 2–3 done and verified 2026-11-01; 4–5 built, their OBS half pending — [0010](0010-building-and-choosing-an-overlays-collection.md), [0011](0011-new-overlays-start-from-the-template.md)

## Context

The comic overlay is live, streamed on most days, and its OBS side is tuned by
measurement (§2). The move to several overlays touches every path it has, and
the user's one condition was that nothing breaks.

## Decision

Five steps. Each one stops for confirmation (`CLAUDE.md` §9) and is verified
against OBS, not assumed:

| Step | What | Build order |
| --- | --- | --- |
| 1 | Commit pending work; back up OBS's collection and the deck profile | — |
| 2 | Restructure into one repo, no behaviour change ([0002](0002-one-repo-for-every-overlay.md)) | 6m |
| 3 | Extract `core/` from the two pages ([0006](0006-shared-page-code-is-plain-scripts.md)) | 6n |
| 4 | `overlay.json`, `--overlay`, a collection per overlay, `Mascot` / `MascotV`; measure the vertical canvas in a fresh collection ([0003](0003-one-scene-collection-per-overlay.md)–[0005](0005-mascot-is-optional-and-generic.md)) | 6o |
| 5 | `overlays/_template/`, then the second show | 6p |

**The check for every step:**

- `obs-setup.py --check --vertical` reports nothing new.
- The punch sets read back off OBS match the ones recorded in §2 and §5.
- Screenshots of `COMIC` and `VCOMIC` look right.

## Consequences — the record of steps 1 and 2, 2026-11-01

**Commits**, on branch `monorepo`:

- "chat: read YouTube chat directly when Restream drops it" — the pending work.
- "restructure: Overlays monorepo…" — moves only, so history follows.
- "restructure: point the code at the new layout".
- This documentation.

**Backups:**

- `%APPDATA%\obs-studio\backup-monorepo-20261101-1742\` — the collection and its
  `.bak`, `user.ini`, the vertical plugin's `config.json`.
- `%APPDATA%\MacroDeck\backup-monorepo-20261101-1742\` — the deck profile.

**Repointed outside the repo.** OBS and Macro Deck were started while the files
were moving, so both were repointed through their own APIs rather than on disk:

- **OBS:** the five URLs, set with `SetInputSettings` (`url` only).
- **Macro Deck:** the two buttons, set with `PUT /api/widgets`. Read back, they
  differ only by the path; Macro Deck re-serialises the data, but once parsed
  it is identical.

**Verified against the running OBS:**

- `--check --vertical`: no browser-source, scene or stack change. It reports
  only three things that predate the move:
  - `DelayEnable` is off in profiles `COD` and `Untitled`;
  - `Cam` is an `ios_camera_source`;
  - the vertical canvas stores `ffmpeg_svt_av1` as its encoder (inert).
- **Every non-URL setting is identical.** All browser-source settings,
  including the 660-character chat CSS, match byte for byte.
- **Punch sets, read back after stepping through every scene:**
  - Horizontal — `START` Cam+Game · `CHAT` Cam+Chat · `GAME` Cam+Game · `CAM`
    Cam · `BRB` Cam+Game · `END` Cam+Game. All six match §2.
  - Vertical — `START` Cam+Chat · `CHAT` Cam+Chat+Game · `GAME` Cam+Game ·
    `CAM` Cam · `BRB` nothing · `END` Cam. All six match §5.
- **All five browser sources are active.** Screenshots show the comic art, the
  socials icons from `assets/socials/`, and the deer on `GAME` from
  `mascot/sets/deer/`.
- **The bridges started from the new paths.** The moved `chat/.venv` loads
  Piper, the blocklist reads 634 entries, and Restream chat connected. The
  mascot bridge returns 200 for its own files and 404 for everything else,
  `..` and `%2e%2e` included.
- **The deck's command runs from the new path.** Checked with `--help`; GO
  LIVE was not pressed, since that starts a real stream.

**Left for later, on purpose:**

- **Renaming the collection `Untitled` → `Hi-Fi Rush`** moves to step 4,
  where the name starts to matter.
- **`overlays/hi-fi-rush/obs/scenes.json` still predates 2026-10-25.** It
  needs a re-export after OBS next quits cleanly, so the export carries the
  new URLs.

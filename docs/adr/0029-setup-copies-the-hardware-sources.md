# 0029 — Setup copies the hardware sources into a collection that has them unset

- **Date:** 2026-11-05
- **Status:** Built. Tested on the live `Fitness Friday` collection:
  - `Game`, `Cam` and `Chat`'s url were blanked;
  - `--check` planned the three copies from Money Talks Monday, and a real
    run made them;
  - all three came back identical to a backup taken first;
  - a second `--check` reported the collection matching.

  The squaring-on-add change at the end has not been seen on a fresh build.

## Context

`tools/obs-setup.py` creates `Game`, `Cam`, `Browser` and `Chat` in a new
collection, but cannot know which window, which phone or which chat widget
this machine uses.

- **By hand each time:** every collection built so far (Money Talks
  Monday, Tech Talks Tuesday, Fitness Friday) needed the settings copied
  from another collection over the websocket. Without it the windows are
  black and the chat is empty, and nothing errors.
- **Five collections on a fresh PC** would mean four rounds of the same
  clicks.

The mic was the same problem and is solved by copying it from another
collection's file ([0026](0026-setup-copies-a-mic-into-a-new-collection.md)).
These four are easier. They are ordinary inputs, so `SetInputSettings`
reaches them, and no collection switch or reload is needed.

**Measured on this machine,** in all four real collections, each source
holds the same few keys:
- `Game`: `capture_mode`, `window`, and `capture_audio`;
- `Cam` (`ios_camera_source`): `mode` and `usb_device`;
- `Browser`: setup's own window settings and `capture_audio`;
- `Chat`: `url`, plus the size, css and flags setup derives from the
  overlay.

## Decision

**Setup fills a source only when it is unset**, meaning its settings hold
nothing beyond what setup itself writes:

| Source | Unset when | What is copied |
| --- | --- | --- |
| `Game` | Nothing but `capture_audio` | Everything except `capture_audio`, which `do_audio` owns |
| `Cam` | Empty | Everything |
| `Browser` | Still setup's default Chrome window | Everything except `capture_audio`. Only from a donor with a different window, and silently skipped when none has one, because the default works |
| `Chat` | `url` empty or `about:blank` | The `url` only. The size and css are derived from the overlay |

- **The donor, per source,** is the other collection that saved that
  source set up most recently, of the same input kind. `--sources-from
  NAME` names one instead.
- **It is read from the donor's saved file.** OBS saves a collection when
  you switch away from it.
- **A source already set up is never touched**, so a deliberate choice
  survives every run.
- **Colour placeholders** (`--placeholders`) are left alone.
- **The Chat url carries the chat embed's token**, so it is copied but
  never printed: the report says "copy its url from X".
- **With nothing to copy**, setup warns once per source: pick it in OBS,
  and collections built after this one copy it from here.

**Also fixed while testing:** a fresh build added `COMIC` to each trigger
scene but left squaring it to the canvas for a second run. It is now
squared as it is added. Harmless before, because `COMIC` is the canvas's
size, but a fresh build now finishes in one run.

## Consequences

- **A fresh PC points its hardware once.** Build the first collection, set
  `Game`, `Cam` and `Chat` there, and every collection built after copies
  them. A collection built before that is filled on its next run.
- **The other way round is not covered.** Change a window or a chat widget
  later in one collection, and the others keep their own: a set-up source
  is never overwritten.
- **A Game deliberately left on its defaults** (any fullscreen app, no
  window) looks unset, and is filled from the donor. Set any value on it to
  keep it.
- **The copy follows the donor's file,** which can lag what OBS shows for
  the active collection. Only other collections are read, and switching
  away from one saves it.

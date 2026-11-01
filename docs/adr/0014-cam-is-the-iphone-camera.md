# 0014 — `Cam` is the iPhone camera, and cam cutouts are 16:9

- **Date:** 2026-11-02
- **Status:** Accepted, built

## Context

`tools/obs-setup.py` created `Cam` as a Video Capture Device (`dshow_input`)
in every new collection. This machine's camera is an iPhone, through the iOS
Camera Source plugin, and Hi-Fi Rush's `Cam` was an `ios_camera_source` made
by hand.

Building Money Talks Monday's collection, setup made the wrong kind. Its
`Cam` had to be carried over from Hi-Fi Rush before setup ran. Read back off
OBS, the iPhone delivers **3840 × 2160**.

The user's review of the first build, the same day: the cam cutouts "cut most
of the cam". They were a 400 × 297 notch (4:3), a 1200 × 900 window (4:3) and
a 500 px circle. Each is cropped to its own shape before it is stretched
(`fillTransform`), so a 16:9 camera lost a quarter of its width in the 4:3
holes and nearly half in the circle.

## Decision

- **`Cam` is an `ios_camera_source` in every collection** setup creates on
  Windows, "for now", in the user's words. If the plugin is missing, setup
  falls back to a Video Capture Device and says so. A `Cam` of another kind is
  left alone with a warning, as before.
- **Cam cutouts are 16:9**, the camera's own shape, so it is never cropped.
  Bands and dividers may lap a few pixels over an edge to hide a seam, but a
  hole is never another shape. Money Talks Monday's are 528 × 297,
  1280 × 720, 704 × 396 and the full frame.

## Consequences

- **A new collection still needs the phone picked once** in `Cam`'s
  properties. Whether the plugin finds it by itself is not measured.
- **A 16:9 cam hole is a constraint on every layout.** Where the space left
  over is not 16:9, art fills the difference: on CHAT the footer rises under
  the cam.
- **The comic's cam holes are not checked against this.** It predates the
  rule.
- **Back to a webcam** means changing `CAM_KIND`, and re-checking the cutouts
  if it is not 16:9.

# Overlay template

The starting point for a new show's overlay. A plain, working overlay: six
16:9 panels in a 3 × 2 grid, one per scene, with every kind of hole —
a bare full-panel game with an inset cam, chat beside cam, a full cam, and a
BRB with none. Its vertical page is six 9:16 panels with the face-top /
game-below stack. No mascot.

## Make a new overlay

1. Copy this folder to `overlays/<name>/`.
2. In `overlay.json`, set `name` and `collection` — the OBS scene collection
   this overlay will live in. Add `"mascot": { "set": "deer" }` and a
   `mascot/` folder with `placement.json` and `placement-vertical.json` if it
   has one (copy them from `overlays/hi-fi-rush/mascot/` and re-author).
3. Design: `PANELS`, `artFor`, the CSS. Keep each panel's border at 15px.
   `chat.css` styles the chat embed to sit on your chat panel. The template
   shows no socials and carries no icons: before giving a panel `socials`,
   draw `assets/socials/<platform>.svg` for each platform in the contract.
4. Build its collection — created on the first run, never while live:

   ```bash
   py -3 tools/obs-setup.py --overlay <name> --vertical --no-profiles
   ```

   A new collection starts with **no microphone**: pick yours under OBS →
   Settings → Audio → Mic/Auxiliary Audio, then run the same command again so
   the mic chain and the ducks go on it. Point `Game`, `Cam` and `Browser` at
   your hardware as for any machine (root README, step 5).

5. Run the show:

   ```bash
   py -3 start.py --overlay <name>
   ```

6. Fill in `CLAUDE.md`, and record any decision in `docs/adr/`.

Preview without OBS: serve the repo root (`python -m http.server 8765`) and
open `/overlays/<name>/overlay.html?debug=1`; keys 1–6 pan.

## What you get for free, and what you must keep

Everything that talks to OBS is `core/` — see [core/README.md](../../core/README.md)
for what a page must define. The rules every overlay inherits are in
[ADR 0007](../../docs/adr/0007-holes-are-each-overlays-design.md): one hole per
source at a time, holes may nest but not partly overlap, the page is exactly
the canvas size. The scene and source names are the shared ones
([core/contract.js](../../core/contract.js)), so the deck works unchanged.

The `Chat` source is 800 × 938 unless `overlay.json` sets `"chat":
{"width": W, "height": H}`, and it is cropped to each hole's shape. Size it to
your chat hole and nothing is cropped
([ADR 0015](../../docs/adr/0015-chat-source-sized-per-overlay.md)).

`Cam` is the iPhone, 3840 × 2160: draw every cam hole 16:9, or the camera is
cropped ([ADR 0014](../../docs/adr/0014-cam-is-the-iphone-camera.md)).

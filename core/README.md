# core/

The page code every overlay shares: the link to OBS, the hole pipeline, the
page of panels and the camera that pans across it. Plain scripts, not
modules — the pages load as `file://` and Chromium refuses modules there
([ADR 0006](../docs/adr/0006-shared-page-code-is-plain-scripts.md)). Top-level
`const`s and functions in plain scripts share one global scope, which is how
these files and the page see each other.

| File | Holds |
| --- | --- |
| `contract.js` | `OVERLAY_CONTRACT`: scene, host, source names, ports, social handles. Also read as JSON by `tools/obs-setup.py` and `start.py` |
| `base.js` | `params`, `DEBUG` |
| `socials.js` | `SOCIALS`, `SOCIAL_NAMES` (from the contract), `socialsFor()` |
| `panel-page.js` | Builds the page from `PANELS`: skirts, panels, holes, their page-space geometry; the `#countdown` ticker |
| `obs-link.js` | Scene detection (`applyScene`, `listenObsStudio`, `seedFromObsStudio`) and the obs-websocket client (`connect`, `request`) |
| `holes.js` | Hole/source state, masks and `applyPunch`, tracking, and placing OBS sources: `loadItemIds`, `pushRects`, `syncVisibility` |
| `camera-pan.js` | The comic pan: `transformFor`, `goTo`. One transition; see "Another transition" |
| `hud.js` | The `?debug=1` readout, `startHud()` |

## Load order

```html
<script src="../../core/contract.js"></script>
<script src="../../core/base.js"></script>
<script> /* the page's config and hooks — below */ </script>
<script src="../../core/socials.js"></script>
<script src="../../core/panel-page.js"></script>
<script src="../../core/obs-link.js"></script>
<script src="../../core/holes.js"></script>
<script src="../../core/camera-pan.js"></script>
<script src="../../core/hud.js"></script>
<script> /* boot — below */ </script>
```

`panel-page.js` builds the DOM as it loads, so the page's config has to come
before it. Every other core file only declares things. Nothing may *run*
until the boot script, which comes after every core file — so no call can
reach a declaration that has not been evaluated yet.

## What the page defines

Before `socials.js`:

| Name | What |
| --- | --- |
| `PAGE_W`, `PAGE_H` | The page, in page px |
| `CANVAS_W`, `CANVAS_H` | The OBS canvas this page renders for — 1920 × 1080 or 1080 × 1920. The browser source is exactly this size |
| `PANELS` | Panels: `id`, `key`, `cls`, `x`, `y`, `w`, `h`, `rot`, `fit`, `tag`, `holes[]` (`src`, `x`, `y`, `w`, `h` in % of the panel's content box, `label`, `c`, optional `bare`), optional `socials`, `speedlines` |
| `SCENE_MAP` | Trigger scene name → panel id. Every scene in `OVERLAY_CONTRACT.scenes` should map |
| `scaleFor(p)` | A panel's resting scale |
| `artFor(p)` | The panel's art, as HTML. Tag an element `over` to lift it above the video |
| `PAGE` | The hooks, below |

`PAGE` is how the page tells core which scene it drives and what to do when
the connection changes:

| Hook | Horizontal (`overlay.html`) | Vertical (`vertical.html`) |
| --- | --- | --- |
| `label` | `"overlay"` | `"vertical"` |
| `host` | `COMIC` | `VCOMIC` |
| `hostKey()` | `{sceneName: "COMIC"}` | `{sceneUuid}` once resolved, else `null` — core waits |
| `onIdentified()` | `loadItemIds()` | resolve canvas and scene, which then binds |
| `onClosed()` | — | forget the scene uuid |
| `onItemsMissing()` | — | rebind in 3 s |
| `onItemsFailed()` | — | re-resolve in 4 s |
| `hudState()` | `""` | canvas and scene lines |

The DOM it expects: `#viewport` › `#shaker` › `#page`, and `#hud` with
`#hudState`, `#hudRects`, `#hudLog`. `--pan-ms` on `:root`. The classes
`panel-page.js` writes — `.panel`, `.under`, `.hole`, `.fake-source`,
`.panel-tag`, `.over`, `.page-under`, `.skirt-*`, `.socials` — are the page's
to style.

## Boot

```js
applyPunch(-1);          // nothing live yet — page fully opaque
listenObsStudio();
seedFromObsStudio(0);    // horizontal only; vertical relies on the websocket
connect();
startHud();
```

## Another transition

`camera-pan.js` is the only file that decides how the page moves. A page that
wants a different transition loads its own file in its place. That file must
define:

- `current` — the panel on air;
- `transformFor(t)` — the page's *resting* transform for panel `t`. `holes.js`
  uses it to decide which holes win their sources before the move starts;
- `goTo(t, {instant})` — which must call `applyPunch(Number(t))` and
  `startTracking(ms)` for as long as the page is moving, so the OBS sources
  follow their holes.

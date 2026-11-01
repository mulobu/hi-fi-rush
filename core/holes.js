/* core/holes.js -- punches the holes and moves OBS sources into them
   Shared by every overlay page. Plain script, not a module: pages load as
   file:// and Chromium refuses modules there (docs/adr/0006). What a page
   must define before loading this, and the load order, are in
   core/README.md. */

      /* Hole and source state. Declared before any function that reads it
         can run: nothing here is called until the page's boot script. */
      let punched = new Set();
      const itemIds = new Map(); /* sourceName -> sceneItemId */
      const srcSize = new Map(); /* sourceName -> {w, h} in source pixels */
      const itemOn = new Map(); /* sourceName -> enabled, as OBS last reported */
      const managed = new Set(holeEls.map((h) => h.src));

      /* The browser stands in for the game. `Browser` is a window capture
         with no hole of its own: while it is UNMUTED it fills whatever hole
         Game would have filled, and Game parks. Mute is the switch because it
         already is one for the audio, and the deck and OBS's mixer can both
         flip it. Muted, missing or unknown, the game shows — the browser
         never goes on air on a guess. Not in `managed`: a host scene without Browser is
         complete, and must not keep a rebind loop spinning. CLAUDE.md §2. */
      const BROWSER = OVERLAY_CONTRACT.sources.browser;
      let browserLive = false;
      const feed = (src) =>
        src === "Game" && browserLive && itemIds.has(BROWSER) ? BROWSER : src;

      /* ================================================================
   HOLE PUNCH — masks generated from the same PANELS config.

   CSS transparency cannot reach through an ancestor's background, so
   two things paint behind every hole and both have to be cut: the
   page (gutter + halftone) and the panel's own art layer, .under.

   Nothing else is masked. The .hole element keeps its inked border and
   hard drop shadow, the panel keeps its border, radius and shadow, and
   the speedlines and tag keep sitting on top — all of which now land
   over live video instead of over a placeholder fill.

   The cut is ONE path per mask with fill-rule="evenodd". Separate
   <rect> elements each fill on their own and cut nothing, and an SVG
   <mask> element does not resolve its own url(#id) once the SVG is a
   data-URI image. Both render, both are silently wrong.
   ================================================================ */

      const rotPt = (px, py, cx, cy, deg) => {
        const a = (deg * Math.PI) / 180,
          c = Math.cos(a),
          s = Math.sin(a),
          dx = px - cx,
          dy = py - cy;
        return [cx + dx * c - dy * s, cy + dx * s + dy * c];
      };

      /* Corners rotated by hand: a quad carries the panel tilt exactly, where
         an axis-aligned rect would leave slivers at the corners. deg 0 for
         panel-local masks, which are already square to their own box. */
      const quad = (x, y, w, h, cx, cy, deg) =>
        "M" +
        [
          [x, y],
          [x + w, y],
          [x + w, y + h],
          [x, y + h],
        ]
          .map(([px, py]) =>
            rotPt(px, py, cx, cy, deg)
              .map((n) => n.toFixed(1))
              .join(" "),
          )
          .join("L") +
        "Z";

      /* One opaque ground with the cuts punched out of it, as a mask image. */
      function applyMask(el, X, Y, W, H, cuts) {
        const d = `M${X} ${Y}H${X + W}V${Y + H}H${X}Z` + cuts;
        const svg =
          `<svg xmlns="http://www.w3.org/2000/svg" width="${W}" height="${H}" ` +
          `viewBox="${X} ${Y} ${W} ${H}">` +
          `<path fill="#000" fill-rule="evenodd" d="${d}"/></svg>`;
        const uri = `url("data:image/svg+xml;utf8,${encodeURIComponent(svg)}")`;
        Object.assign(el.style, {
          maskImage: uri,
          webkitMaskImage: uri,
          maskSize: `${W}px ${H}px`,
          webkitMaskSize: `${W}px ${H}px`,
          maskPosition: `${X}px ${Y}px`,
          webkitMaskPosition: `${X}px ${Y}px`,
          maskRepeat: "no-repeat",
          webkitMaskRepeat: "no-repeat",
          /* mask-clip defaults to border-box. Every mask here is authored in
             its element's own box so the default would do, but a cut whose
             rounding lands a hair outside would be clipped away silently. */
          maskClip: "no-clip",
          webkitMaskClip: "no-clip",
        });
      }

      /* Corners of a panel-local rect after the panel's own tilt, page-space. */
      function pageCorners(r, cx, cy, deg) {
        return [
          [r.x, r.y],
          [r.x + r.w, r.y],
          [r.x + r.w, r.y + r.h],
          [r.x, r.y + r.h],
        ].map(([x, y]) => rotPt(x, y, cx, cy, deg));
      }

      /* Where every hole lands once a pan to `id` has settled. Pure math on the
         target transform, so the punch set is decided up front instead of
         being chased frame by frame. */
      function restingRects(id) {
        const m = new DOMMatrix(transformFor(String(id)));
        return holeEls.map((h) => {
          const pts = pageCorners(h.page, h.cx, h.cy, h.rot).map(([x, y]) =>
            m.transformPoint(new DOMPoint(x, y)),
          );
          const xs = pts.map((q) => q.x),
            ys = pts.map((q) => q.y);
          const x = Math.min(...xs),
            y = Math.min(...ys);
          const w = Math.max(...xs) - x,
            hh = Math.max(...ys) - y;
          const vx = Math.max(0, Math.min(CANVAS_W, x + w) - Math.max(0, x));
          const vy = Math.max(0, Math.min(CANVAS_H, y + hh) - Math.max(0, y));
          return { hole: h, onScreen: vx * vy };
        });
      }

      /* One OBS item per source, so a source can only be in one hole at a time
         — Cam is referenced by four panels. The panel on air wins; failing
         that, whichever hole shows the most of itself takes it. That is what
         lets a neighbour bleeding into frame show real video instead of a
         placeholder, while never leaving two holes fighting over one item. */
      function chooseWinners(id) {
        const best = new Map();
        restingRects(id).forEach((r) => {
          if (!r.onScreen) return;
          const live = r.hole.panelId === id;
          const cur = best.get(r.hole.src);
          if (
            !cur ||
            (live && !cur.live) ||
            (live === cur.live && r.onScreen > cur.onScreen)
          )
            best.set(r.hole.src, { hole: r.hole, live, onScreen: r.onScreen });
        });
        return new Set([...best.values()].map((v) => v.hole));
      }

      /* fill-rule evenodd counts crossings, so a cut that lies INSIDE another
         cut flips that region back to opaque. The game panel hits this every
         time: its `bare` Game hole is the whole panel, and the Cam hole sits
         inside it — winding 3, odd, and the webcam window paints solid panel
         art over live video. Since the union of A ⊇ B is just A, dropping the
         contained cut is exact, and it is the only overlap the layout can
         produce: holes within a panel are authored side by side, and panels
         never overlap each other. Partial overlap would still flip, so it is
         called out loudly rather than rendered wrong in silence. */
      const contains = (a, b) =>
        b.x >= a.x &&
        b.y >= a.y &&
        b.x + b.w <= a.x + a.w &&
        b.y + b.h <= a.y + a.h;

      function mergeCuts(holes) {
        const kept = holes.filter(
          (h) => !holes.some((g) => g !== h && contains(g.local, h.local)),
        );
        if (DEBUG)
          kept.forEach((h, i) =>
            kept.slice(i + 1).forEach((g) => {
              const o =
                h.local.x < g.local.x + g.local.w &&
                g.local.x < h.local.x + h.local.w &&
                h.local.y < g.local.y + g.local.h &&
                g.local.y < h.local.y + h.local.h;
              if (o) hud(`cuts overlap: ${h.key} / ${g.key}`, true);
            }),
          );
        return kept;
      }

      /* Only winning holes are cut. Everything else keeps its art, so no hole
         is ever transparent with nothing behind it. Rebuilt per scene change —
         two small data URIs, once per pan. */
      function applyPunch(id) {
        punched = id >= 0 ? chooseWinners(id) : new Set();
        holeEls.forEach((h) =>
          h.el.classList.toggle("punched", punched.has(h)),
        );

        let pageCuts = "";
        PANELS.forEach((p) => {
          const under = panelEls[p.id].querySelector(".under");
          if (!under) return;
          const mine = mergeCuts(
            holeEls.filter((h) => h.panelId === p.id && punched.has(h)),
          );
          if (!mine.length) {
            under.style.maskImage = "none";
            under.style.webkitMaskImage = "none";
            return;
          }
          let panelCuts = "";
          mine.forEach((h) => {
            panelCuts += quad(
              h.local.x,
              h.local.y,
              h.local.w,
              h.local.h,
              0,
              0,
              0,
            );
            /* Same hole in .page-under's box, which is the page itself —
               the skirt is a separate, unmasked element, so page-space
               coordinates go straight in. */
            pageCuts += quad(
              h.pageInner.x,
              h.pageInner.y,
              h.pageInner.w,
              h.pageInner.h,
              h.cx,
              h.cy,
              h.rot,
            );
          });
          applyMask(under, 0, 0, mine[0].panelW, mine[0].panelH, panelCuts);
        });

        applyMask(pageUnder, 0, 0, PAGE_W, PAGE_H, pageCuts);
        syncVisibility();
      }

      /* ================================================================
   HOLE RECTS — one row per hole, already in OBS canvas coordinates.

   Tracking runs only while the page is moving, then stops dead. Idle
   cost is zero; there is no timer ticking between pans. Step 6 pushes
   these to OBS from inside track().
   ================================================================ */
      function holeRects() {
        const vp = frameEl.getBoundingClientRect();
        return holeEls.map((h) => {
          const r = h.el.getBoundingClientRect();
          const x = r.left - vp.left,
            y = r.top - vp.top;
          return {
            hole: h,
            src: h.src,
            key: h.key,
            x,
            y,
            w: r.width,
            h: r.height,
            visible:
              x < CANVAS_W &&
              y < CANVAS_H &&
              x + r.width > 0 &&
              y + r.height > 0,
          };
        });
      }

      let trackRAF = 0,
        trackUntil = 0;

      function track() {
        const rects = holeRects();
        if (DEBUG) paintRects(rects);
        pushRects(rects);
        if (performance.now() < trackUntil)
          trackRAF = requestAnimationFrame(track);
        else trackRAF = 0;
      }

      /* Extends the window, never shortens it. The short 120ms nudges — a
         reconnect, or the per-scene size refresh — can land in the middle of
         a pan, and cutting the pan's own window short leaves every source
         frozen at whatever half-way rect it had reached. */
      function startTracking(ms) {
        trackUntil = Math.max(trackUntil, performance.now() + ms);
        /* Pushed this frame, not the next. applyPunch has already cut the new
           holes, so waiting a frame leaves each newly punched hole showing
           whatever is behind it — since unused sources park off-canvas, that
           is bare canvas. track() schedules its own successor. */
        if (!trackRAF) track();
      }

      /* ================================================================
   SOURCE PLACEMENT

   Transforms address items by id, so the name -> id map is fetched
   once and cached. Sources are addressed inside the page's host scene
   (PAGE.hostKey: COMIC by name, VCOMIC by uuid) even though a trigger
   scene is what's on program; that nesting was verified in step 3.

   Only the LIVE panel's holes may drive a source. Cam is referenced by
   four panels but is one item in COMIC, so two holes claiming it
   mid-pan would fight over the same transform.
   ================================================================ */
      function loadItemIds({ quiet = false } = {}) {
        const key = PAGE.hostKey();
        if (!key) return; /* host scene not resolved yet */
        request("GetSceneItemList", key)
          .then((r) => {
            itemIds.clear();
            itemOn.clear();
            r.sceneItems.forEach((i) => {
              itemIds.set(i.sourceName, i.sceneItemId);
              itemOn.set(i.sourceName, i.sceneItemEnabled !== false);
              /* Source pixel size, needed to compute the fill crop below. A
                 source that has not produced a frame yet reports 0 — left out
                 so pushRects falls back until it has. */
              const t = i.sceneItemTransform || {};
              if (t.sourceWidth > 0 && t.sourceHeight > 0)
                srcSize.set(i.sourceName, {
                  w: t.sourceWidth,
                  h: t.sourceHeight,
                });
            });
            const missing = [...managed].filter((n) => !itemIds.has(n));
            if (missing.length || !quiet)
              hud(
                missing.length
                  ? `sources missing from ${PAGE.host}: ${missing.join(", ")}`
                  : `sources bound: ${[...managed].join(", ")}`,
                missing.length > 0,
              );
            if (missing.length) PAGE.onItemsMissing();
            syncVisibility();
            startTracking(120); /* place them once, without waiting for a pan */
          })
          .catch(() => {
            hud(`cannot read ${PAGE.host} item list`, true);
            PAGE.onItemsFailed();
          });
      }

      /* No pan: the same hole changes feed. The item list is re-read rather
         than just re-pushed, because Browser may have been created after this
         page bound and its size is what the crop needs; loadItemIds then
         parks the loser and places the winner. */
      function setBrowserLive(live) {
        if (live === browserLive) return;
        browserLive = live;
        hud(`browser ${live ? "on air" : "off air"}`);
        if (wsReady) loadItemIds({ quiet: true });
      }

      function sendBatch(requests) {
        ws.send(
          JSON.stringify({
            op: 8,
            d: {
              requestId: "b" + ++reqId,
              haltOnFailure: false,
              executionType: 0,
              requests,
            },
          }),
        );
      }

      /* Fill a WxH opening from a sw x sh source without distortion, by
         cropping the source to the opening's aspect and then stretching.

         SCALE_OUTER would do the same fit, but it renders the whole frame and
         lets the excess spill outside the bounds box. The mask hides spill
         that lands on comic art — and does nothing about spill that lands in
         ANOTHER punched hole. On CHAT that put the chat browser's overspill
         straight across the webcam bleeding in from the cam panel, filling
         half that window with the wrong source. Cropping first means an item
         paints nothing outside its own opening, ever. */
      function fillTransform(r, s) {
        const t = {
          positionX: r.x,
          positionY: r.y,
          alignment: 5 /* top-left, so position IS the rect corner */,
          rotation: 0,
          boundsAlignment: 0,
          boundsWidth: Math.max(1, r.w),
          boundsHeight: Math.max(1, r.h),
        };

        /* No frame yet, so no size to crop against. SCALE_OUTER still fills
           the opening; it just spills until the size is known. */
        if (!s) {
          t.boundsType = "OBS_BOUNDS_SCALE_OUTER";
          /* A crop left over from the last time this source DID have a size
             would still apply, and SCALE_OUTER would fit the cropped frame —
             zoomed in on a slice of it. */
          t.cropLeft = t.cropRight = t.cropTop = t.cropBottom = 0;
          return t;
        }

        const want = Math.max(1, r.w) / Math.max(1, r.h);
        let cx = 0,
          cy = 0;
        if (s.w / s.h > want) cx = Math.round((s.w - s.h * want) / 2);
        else cy = Math.round((s.h - s.w / want) / 2);

        /* OBS rejects a crop that leaves nothing, and a 1px rounding error at
           an extreme aspect would do exactly that. */
        cx = Math.min(cx, Math.floor((s.w - 2) / 2));
        cy = Math.min(cy, Math.floor((s.h - 2) / 2));

        t.boundsType = "OBS_BOUNDS_STRETCH";
        t.cropLeft = t.cropRight = Math.max(0, cx);
        t.cropTop = t.cropBottom = Math.max(0, cy);
        return t;
      }

      function pushRects(rects) {
        const key = PAGE.hostKey();
        if (!wsReady || !key || !itemIds.size) return;
        const reqs = [];
        rects.forEach((r) => {
          if (!punched.has(r.hole)) return;
          const src = feed(r.src);
          const id = itemIds.get(src);
          if (!id) return;
          reqs.push({
            requestType: "SetSceneItemTransform",
            requestData: {
              ...key,
              sceneItemId: id,
              sceneItemTransform: fillTransform(r, srcSize.get(src)),
            },
          });
        });
        if (reqs.length) sendBatch(reqs);
      }

      /* Sources the live panel does not use are parked wholly outside the
         canvas, not switched off.

         Disabling the item deactivates the source, and reactivating it is not
         free: a game capture has to re-hook its target and a capture device
         has to reopen the device, which is anywhere from a few hundred ms to
         a couple of seconds of black the next time that hole is punched.
         CHAT is the only view that drops Game — its camera starts past
         x=3490 and the game panel ends at 3464 — so every switch out of chat
         paid for a re-hook. CAM drops it too. That is the black leaving chat;
         the skirt above is the black arriving.

         Parked items stay hooked, keep feeding Source Record, and still
         cannot show through a hole they do not own: top-left alignment at
         canvas + 200 puts every pixel off-canvas. Enable is only sent for an
         item actually seen disabled, so a source switched off by hand comes
         back once instead of being fought over on every pan. Only sources
         this overlay owns are touched — anything else in the host scene,
         Overlay included, is left alone. */
      const PARK = {
        positionX: CANVAS_W + 200,
        positionY: CANVAS_H + 200,
        alignment: 5,
        rotation: 0,
        boundsType: "OBS_BOUNDS_STRETCH",
        boundsAlignment: 0,
        boundsWidth: 16,
        boundsHeight: 9,
      };

      function syncVisibility() {
        const key = PAGE.hostKey();
        if (!wsReady || !key || !itemIds.size) return;
        const used = new Set([...punched].map((h) => feed(h.src)));
        const reqs = [];
        itemIds.forEach((id, name) => {
          if (!managed.has(name) && name !== BROWSER) return;
          if (itemOn.get(name) === false) {
            reqs.push({
              requestType: "SetSceneItemEnabled",
              requestData: {
                ...key,
                sceneItemId: id,
                sceneItemEnabled: true,
              },
            });
            itemOn.set(name, true);
          }
          if (!used.has(name))
            reqs.push({
              requestType: "SetSceneItemTransform",
              requestData: {
                ...key,
                sceneItemId: id,
                sceneItemTransform: PARK,
              },
            });
        });
        if (reqs.length) sendBatch(reqs);
      }

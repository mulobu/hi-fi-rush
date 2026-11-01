/* core/vertical.js -- what any page on the vertical canvas needs
   Shared by every overlay's vertical page: the platform safe zones and the
   pass that keeps panel tags out of them, finding the vertical canvas and its
   host scene by uuid, and the PAGE hooks that drive that scene. Plain
   script; load it after base.js and before the page's own config
   (core/README.md). */

      /* Platform chrome, in canvas px. The union of TikTok's 140 / 324 / 164
         and YouTube Shorts' 120 / 300 / 96 — the vertical output goes to both
         through Restream, which fans one 1080 x 1920 encode out unchanged, so
         the strictest of the two governs every platform.

         A picture may run under the right rail; the action is centred and a
         covered corner of game capture costs nothing. Type may not. So the
         windows keep their full 977px width and only TEXT is held inside
         SAFE_RIGHT. SAFE_PAD is slack against a device with a taller notch. */
      const SAFE_TOP = 140,
        SAFE_BOTTOM = 324,
        SAFE_RIGHT = 164,
        SAFE_PAD = 12;

      /* ================================================================
   OBS WIRING — vertical canvas

   Two differences from the horizontal overlay, and both matter.

   1. SCENE SOURCE. The websocket is PRIMARY here, not the backup.
      window.obsstudio's behaviour inside an Aitum canvas is unmeasured,
      and what this page needs is the MAIN canvas's program scene so one
      Stream Deck press moves both pages. CurrentProgramSceneChanged
      carries exactly that. obsstudio is still wired up underneath: if it
      reports a vertical scene name it simply isn't in SCENE_MAP and is
      ignored, so it costs nothing and covers us if it does report the
      trigger scene.

   2. TRANSFORM TARGET. Every scene request goes to the vertical canvas
      by sceneUuid. Measured on OBS 32.2.2 / obs-websocket 5.7.4:
      canvasName is SILENTLY IGNORED — GetSceneList {canvasName: "Aitum
      Vertical"} returns Main's scene list with no error — and vertical
      scenes cannot be reached by sceneName at all, because name lookup
      resolves within Main only. So the uuid is discovered from
      GetCanvasList on every connect and never cached to disk; it is
      random per scene collection. See CLAUDE.md §2.
   ================================================================ */
      /* Scenes UPPERCASE, sources TitleCase — OBS shares one namespace across
         canvases too, so the vertical scene cannot be called COMIC. */
      const VERT_SCENE =
        params.get("scene") || OVERLAY_CONTRACT.host.vertical;
      /* Which canvas to drive. Default is "the one that isn't Main"; naming it
         matters only if you ever run more than one extra canvas. */
      const VERT_CANVAS = params.get("canvas") || "";

      let vertCanvasUuid = null,
        vertSceneUuid = null;

      /* Find the vertical canvas and the scene this overlay lives in, then
         bind the source items inside it. Retried on a timer rather than given
         up on: OBS can identify the websocket before the Aitum canvas or its
         scene exist — a fresh install, or a collection being set up — and the
         page should heal when they appear rather than needing a reload. */
      let resolveTimer = 0;
      function resolveVerticalScene() {
        clearTimeout(resolveTimer);
        if (!wsReady) return;
        request("GetCanvasList")
          .then((r) => {
            const cs = r.canvases || [];
            const pick = VERT_CANVAS
              ? cs.find((c) => c.canvasName === VERT_CANVAS)
              : cs.find(
                  /* A canvas outlives the plugin that drove it — it is saved
                     in the scene collection — and an orphan reports a null
                     base size. Skip it, or the pick lands on a dead canvas. */
                  (c) =>
                    !(c.canvasFlags && c.canvasFlags.MAIN) &&
                    c.canvasVideoSettings &&
                    c.canvasVideoSettings.baseWidth,
                );
            if (!pick)
              throw new Error(
                VERT_CANVAS
                  ? `no canvas named ${VERT_CANVAS}`
                  : "no non-Main canvas — is the vertical canvas added?",
              );
            vertCanvasUuid = pick.canvasUuid;
            hud(`canvas: ${pick.canvasName}`);
            /* canvasUuid, never canvasName — the name is silently ignored and
               would hand back Main's scenes. */
            return request("GetSceneList", { canvasUuid: vertCanvasUuid });
          })
          .then((r) => {
            const sc = (r.scenes || []).find((s) => s.sceneName === VERT_SCENE);
            if (!sc)
              throw new Error(
                `no scene ${VERT_SCENE} on the vertical canvas — run ` +
                  `tools/obs-setup.py --vertical`,
              );
            vertSceneUuid = sc.sceneUuid;
            hud(`scene: ${VERT_SCENE}`);
            loadItemIds();
          })
          .catch((e) => {
            vertSceneUuid = null;
            hud(`vertical: ${e.message}`, true);
            resolveTimer = setTimeout(resolveVerticalScene, 4000);
          });
      }

      /* The PAGE hooks every vertical page uses (core/README.md): drive the
         vertical host scene by uuid, resolved per connect. A page's boot
         script writes `const PAGE = verticalPage("name");`. */
      function verticalPage(label) {
        return {
          label,
          host: VERT_SCENE,
          hostKey: () => (vertSceneUuid ? { sceneUuid: vertSceneUuid } : null),
          /* Canvas and scene first; resolveVerticalScene binds the items once
             it has the uuid. */
          onIdentified: () => resolveVerticalScene(),
          onClosed: () => {
            vertSceneUuid = null;
          },
          /* Rebind if the scene is not fully populated yet. The horizontal
             overlay can assume COMIC is complete before it loads, because
             COMIC is on program the moment OBS starts. This page cannot:
             obs-setup --vertical creates OverlayV as the FIRST item in a new
             VCOMIC and adds Game / Cam / Chat after it, so a boot in that
             window binds an item list with none of them in it — and without
             this, nothing would rebind until the next scene change, leaving
             the vertical canvas showing comic art over empty holes. */
          onItemsMissing: () =>
            setTimeout(() => loadItemIds({ quiet: true }), 3000),
          /* The scene was renamed or removed under us. Re-resolve. */
          onItemsFailed: () => {
            vertSceneUuid = null;
            resolveTimer = setTimeout(resolveVerticalScene, 4000);
          },
          hudState: () =>
            `canvas  ${vertCanvasUuid ? vertCanvasUuid.slice(0, 8) : "—"}\n` +
            `vscene  ${vertSceneUuid ? VERT_SCENE : "unresolved"}\n`,
        };
      }

      /* ================================================================
   SAFE-ZONE PASS — measured off the built page, not modelled.

   §4's signature element is the panel tag, and it sat below the platform
   caption bar on five of six vertical scenes: game +297 canvas px, chat
   +269, end +119, brb +118, cam +17. The tag is authored once, in panel
   coordinates, at bottom: 32px — but every panel lands at its own fit
   scale, so no single number clears the line on all six, and six
   hand-tuned numbers rot the first time a panel moves.

   So it is read back off the page the way the punch sets are: apply each
   panel's resting transform, measure that panel's own tag, and raise it
   by exactly the overflow converted back into page px. The scale comes
   from scaleFor(), never from the measured rect — every panel is tilted,
   and a rotated AABB is taller than the box it encloses.

   Runs on document.fonts.ready: a Bangers tag measured against the
   fallback stack is the wrong height. Touches nothing the pan or the
   punch reads, so it is safe to land late.
   ================================================================ */
      function fitTagsToSafeArea() {
        const vpBox = frameEl.getBoundingClientRect();
        const prevTransform = pageEl.style.transform;
        const limit = CANVAS_H - SAFE_BOTTOM - SAFE_PAD;
        pageEl.style.transition = "none";

        PANELS.forEach((p) => {
          const tag = panelEls[p.id].querySelector(".panel-tag");
          if (!tag) return;
          pageEl.style.transform = transformFor(String(p.id));
          void pageEl.offsetWidth;
          const r = tag.getBoundingClientRect();
          const over = r.top - vpBox.top + r.height - limit;
          if (over <= 0) return;
          const base = parseFloat(getComputedStyle(tag).bottom) || 0;
          tag.style.bottom = base + over / scaleFor(p) + "px";
        });

        pageEl.style.transform = prevTransform;
        void pageEl.offsetWidth;
        pageEl.style.transition = "";
      }

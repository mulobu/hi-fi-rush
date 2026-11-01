/* core/camera-pan.js -- the comic pan: one transition, swappable
   Shared by every overlay page. Plain script, not a module: pages load as
   file:// and Chromium refuses modules there (docs/adr/0006). What a page
   must define before loading this, and the load order, are in
   core/README.md. */

      /* ================================================================
   PAN MATH
     translate(viewport centre)
     rotate(-panel tilt)      -> panel squares up to the frame
     scale(fit)
     translate(-panel centre)
   ================================================================ */
      let current = null;
      function transformFor(t) {
        if (t === "page") {
          const s = Math.min(CANVAS_W / PAGE_W, CANVAS_H / PAGE_H) * 0.94;
          return `translate(${CANVAS_W / 2}px,${CANVAS_H / 2}px) scale(${s}) translate(${-PAGE_W / 2}px,${-PAGE_H / 2}px)`;
        }
        const p = PANELS.find((v) => v.id === Number(t));
        const s = scaleFor(p);
        const cx = p.x + p.w / 2,
          cy = p.y + p.h / 2;
        return `translate(${CANVAS_W / 2}px,${CANVAS_H / 2}px) rotate(${-p.rot}deg) scale(${s}) translate(${-cx}px,${-cy}px)`;
      }

      const shaker = document.getElementById("shaker");
      let shakeTimer;

      const PAN_MS = parseFloat(
        getComputedStyle(document.documentElement).getPropertyValue("--pan-ms"),
      );

      /* instant:true lands on the panel with no travel — used once, when the
         overlay learns which scene was already live at launch. Panning in
         from nowhere on OBS startup would look like a glitch. */
      function goTo(t, { instant = false } = {}) {
        current = t;
        applyPunch(Number(t));
        Object.entries(panelEls).forEach(([id, el]) =>
          el.classList.toggle("is-live", id === String(t)),
        );

        clearTimeout(shakeTimer);

        if (instant) {
          pageEl.style.transition = "none";
          pageEl.style.transform = transformFor(t);
          void pageEl.offsetWidth;
          pageEl.style.transition = "";
          startTracking(120);
          return;
        }

        pageEl.style.transform = transformFor(t);
        startTracking(PAN_MS + 260); /* pan, plus the shake settling after it */

        shakeTimer = setTimeout(() => {
          shaker.classList.remove("shake");
          void shaker.offsetWidth;
          shaker.classList.add("shake");
        }, 810);
      }

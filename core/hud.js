/* core/hud.js -- the ?debug=1 readout
   Shared by every overlay page. Plain script, not a module: pages load as
   file:// and Chromium refuses modules there (docs/adr/0006). What a page
   must define before loading this, and the load order, are in
   core/README.md. */

      /* ================================================================
   DEBUG HUD — ?debug=1
   ================================================================ */
      const hudEl = document.getElementById("hud"),
        hudState = document.getElementById("hudState"),
        hudRects = document.getElementById("hudRects"),
        hudLog = document.getElementById("hudLog");
      const hudLines = [];

      function hud(msg, warn) {
        if (!DEBUG) return;
        const t = new Date().toTimeString().slice(0, 8);
        hudLines.push(
          `<span class="${warn ? "warn" : ""}">${t}  ${msg}</span>`,
        );
        while (hudLines.length > 8) hudLines.shift();
        hudLog.innerHTML = hudLines.join("\n");
        paintState();
      }

      function paintState() {
        hudState.textContent =
          `scene   ${currentScene || "—"}\n` +
          `panel   ${current || "—"}\n` +
          `socket  ${wsReady ? "identified" : "down"}\n` +
          PAGE.hudState() +
          `items   ${itemIds.size ? [...itemIds.keys()].join(" ") : "—"}\n` +
          `obsapi  ${window.obsstudio ? "present" : "absent"}\n`;
      }

      function paintRects(rects) {
        hudRects.innerHTML =
          "\n" +
          rects
            .map(
              (r) =>
                `<span class="${r.visible ? "" : "off"}">` +
                `${r.key.padEnd(12)}` +
                `x:${r.x.toFixed(0).padStart(6)} y:${r.y.toFixed(0).padStart(6)} ` +
                `w:${r.w.toFixed(0).padStart(5)} h:${r.h.toFixed(0).padStart(5)} ` +
                `${r.visible ? "SEND" : "skip"}</span>`,
            )
            .join("\n") +
          "\n";
      }

      function startHud() {
        if (!DEBUG) return;
        hudEl.removeAttribute("hidden");
        paintState();
        hud(
          `${PAGE.label} up — ${window.obsstudio ? "inside OBS" : "plain browser"}`,
        );
        /* Keys 1-9 for testing outside OBS. There is no keyboard in a
           browser source, so this is dead weight on a live overlay. */
        document.addEventListener("keydown", (e) => {
          const n = Number(e.key);
          if (n >= 1 && n <= PANELS.length) goTo(String(n));
        });
      }

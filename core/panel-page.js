/* core/panel-page.js -- builds the page of panels and their holes
   Shared by every overlay page. Plain script, not a module: pages load as
   file:// and Chromium refuses modules there (docs/adr/0006). What a page
   must define before loading this, and the load order, are in
   core/README.md. */

      /* ================================================================
   BUILD
   ================================================================ */
      /* frameEl, not `viewport` — Chrome/CEF already define window.viewport,
         which shadows id-based global lookup and yields a platform object
         with no getBoundingClientRect. */
      const frameEl = document.getElementById("viewport"),
        pageEl = document.getElementById("page"),
        panelEls = {},
        holeEls = [];

      ["skirt-n", "skirt-s", "skirt-w", "skirt-e"].forEach((c) => {
        const b = document.createElement("div");
        b.className = c;
        pageEl.appendChild(b);
      });

      const pageUnder = document.createElement("div");
      pageUnder.className = "page-under";
      pageEl.appendChild(pageUnder);

      PANELS.forEach((p) => {
        const el = document.createElement("div");
        el.className = `panel ${p.cls}`;
        el.dataset.id = p.id;
        Object.assign(el.style, {
          left: p.x + "px",
          top: p.y + "px",
          width: p.w + "px",
          height: p.h + "px",
          transform: `rotate(${p.rot}deg)`,
        });

        const holesHTML = (p.holes || [])
          .map(
            (h, i) =>
              `<div class="hole${h.bare ? " bare" : ""}" data-hole="${p.key}:${i}"
       style="left:${h.x}%;top:${h.y}%;width:${h.w}%;height:${h.h}%">
       <div class="fake-source" style="--src:${h.c}">
         <span class="src-label">${h.label}</span></div>
     </div>`,
          )
          .join("");

        /* Order is the whole trick: .under is masked, everything after it is
           not. Holes keep their inked borders and hard shadows, and the
           speedlines and tag stay on top of the video. */
        const panelSocials =
          p.socials && !p.socials.page ? socialsFor(p, "over", p.socials.at) : "";
        el.innerHTML =
          `<div class="under">${artFor(p)}${panelSocials}` +
          (p.speedlines ? '<div class="speedlines"></div>' : "") +
          `</div>` +
          holesHTML +
          `<span class="panel-tag">${p.tag}</span>`;

        /* Art marked `over` is lifted out of the masked layer so it reads on
           top of the video instead of being covered by it. */
        el.querySelectorAll(".under .over").forEach((n) => el.appendChild(n));

        pageEl.appendChild(el);
        panelEls[p.id] = el;
        /* Gutter-placed socials ride the page, outside every mask. */
        if (p.socials && p.socials.page)
          pageEl.insertAdjacentHTML(
            "beforeend",
            socialsFor(
              p,
              "",
              `left:${p.socials.page.x}px;top:${p.socials.page.y}px`,
            ),
          );
        (p.holes || []).forEach((h, i) =>
          holeEls.push({
            src: h.src,
            key: `${p.key}:${h.src}`,
            panelId: p.id,
            el: el.querySelector(`[data-hole="${p.key}:${i}"]`),
          }),
        );
      });

      /* The panel's own background has to move into .under, or it paints
         behind the hole and no mask on .under can help. Copied as longhands
         so per-panel gradients and sizing survive verbatim. */
      PANELS.forEach((p) => {
        const el = panelEls[p.id],
          under = el.querySelector(".under");
        if (!under) return;
        const cs = getComputedStyle(el);
        Object.assign(under.style, {
          backgroundColor: cs.backgroundColor,
          backgroundImage: cs.backgroundImage,
          backgroundSize: cs.backgroundSize,
          backgroundPosition: cs.backgroundPosition,
          backgroundRepeat: cs.backgroundRepeat,
        });
        el.style.background = "none";
      });

      const PANEL_BORDER = 15; /* matches .panel border-width */

      /* Page-space geometry per hole, from the same config the DOM is built
         from. Lets us work out where every hole WILL be once a pan lands,
         before it starts, without measuring the DOM mid-flight. */
      (() => {
        const probe = pageEl.querySelector(".hole:not(.bare)");
        const HB = probe
          ? parseFloat(getComputedStyle(probe).borderTopWidth)
          : 11;
        let k = 0;
        PANELS.forEach((p) => {
          const cx = p.x + p.w / 2,
            cy = p.y + p.h / 2;
          const iw = p.w - 2 * PANEL_BORDER,
            ih = p.h - 2 * PANEL_BORDER;
          (p.holes || []).forEach((h) => {
            const b = h.bare ? 0 : HB;
            const lx = (iw * h.x) / 100,
              ly = (ih * h.y) / 100,
              lw = (iw * h.w) / 100,
              lh = (ih * h.h) / 100;
            Object.assign(holeEls[k++], {
              rot: p.rot,
              cx,
              cy,
              panelW: iw,
              panelH: ih,
              /* content box, panel-local — cuts the .under mask */
              local: { x: lx + b, y: ly + b, w: lw - 2 * b, h: lh - 2 * b },
              /* border box, page-space — what OBS is told to fill */
              page: {
                x: p.x + PANEL_BORDER + lx,
                y: p.y + PANEL_BORDER + ly,
                w: lw,
                h: lh,
              },
              /* content box, page-space — cuts the .page-under mask */
              pageInner: {
                x: p.x + PANEL_BORDER + lx + b,
                y: p.y + PANEL_BORDER + ly + b,
                w: lw - 2 * b,
                h: lh - 2 * b,
              },
            });
          });
        });
      })();

      /* Countdown on the standby panel */
      let secs = 300;
      setInterval(() => {
        const c = document.getElementById("countdown");
        if (!c) return;
        secs = secs > 0 ? secs - 1 : 300;
        c.textContent = `${String(Math.floor(secs / 60)).padStart(2, "0")}:${String(secs % 60).padStart(2, "0")}`;
      }, 1000);

/* core/socials.js -- the socials cut-outs, from the shared handles
   Shared by every overlay page. Plain script, not a module: pages load as
   file:// and Chromium refuses modules there (docs/adr/0006). What a page
   must define before loading this, and the load order, are in
   core/README.md. */

      /* Platforms that share a handle share a label. The handles are the
         brand's, not an overlay's: core/contract.js. */
      const SOCIALS = OVERLAY_CONTRACT.socials;
      const SOCIAL_NAMES = OVERLAY_CONTRACT.socialNames;

      function socialsFor(p, cls, style) {
        const s = p.socials,
          u = (s.size || 1) / scaleFor(p);
        return (
          `<div class="socials ${s.layout || "stack"} ${cls}" style="--u:${u.toFixed(4)};${style}">` +
          SOCIALS.map(
            (g, i) =>
              (s.layout === "pair" && i === 0 ? `<div class="soc-line">` : "") +
              `<div class="soc-row">` +
              g.on
                .map(
                  (n) =>
                    `<img class="cut" src="../../assets/socials/${n}.svg" alt="${SOCIAL_NAMES[n]}">`,
                )
                .join("") +
              `<span class="handle"><span>${g.handle}</span></span></div>` +
              (s.layout === "pair" && i === 1 ? `</div>` : ""),
          ).join("") +
          `</div>`
        );
      }

/* overlays/money-talks-monday/art.js -- the art both pages draw alike
   Plates, socials, the coin's face, and where the note's rosette lands.
   Plain script, loaded before each page's config; nothing here runs until
   a page asks, so SOCIALS (core/socials.js, loaded later) is read at call
   time. Each page composes these in its own frameArt(). */

      /* Where the rosette lands in the note as drawn: NOTE.rosette is a
         fraction of the image file, and a page may draw the file turned
         a quarter anticlockwise (rotate: -90), as the vertical page does
         while there is no portrait art. */
      const rosetteIn = (note) =>
        note.rotate === -90
          ? [note.rosette[1], 1 - note.rosette[0]]
          : note.rosette;

      /* Handles set like the new series' serial numbers: each character
         bigger than the last. */
      const serial = (text) =>
        [...text]
          .map(
            (ch, i, a) =>
              `<span class="ch" style="--i:${i};font-size:${(0.78 + (0.44 * i) / Math.max(1, a.length - 1)).toFixed(3)}em">${ch}</span>`,
          )
          .join("");

      const socialsRow = (cls) =>
        `<div class="soc ${cls}">` +
        SOCIALS.map(
          (g) =>
            `<div class="soc-item">` +
            g.on
              .map(
                (n) =>
                  `<img src="assets/socials/${n}.svg" alt="${SOCIAL_NAMES[n]}">`,
              )
              .join("") +
            `<span class="handle">${serial(g.handle)}</span></div>`,
        ).join("") +
        `</div>`;

      /* The serial number is the date the stream started: MTM DDMMYY. */
      const SERIAL = (() => {
        const d = new Date(),
          p = (n) => String(n).padStart(2, "0");
        return `MTM ${p(d.getDate())}${p(d.getMonth() + 1)}${String(d.getFullYear()).slice(2)}`;
      })();

      /* The socials as a stacked number panel, for an open scene. */
      const socialsStack = (cls) =>
        `<div class="plate socstack ${cls}">${socialsRow("stack")}</div>`;

      /* The socials on two centred lines — the first two handles, then the
         rest — so they can be set big on a narrow canvas. */
      const socialsPair = (cls) => {
        const one = (g) =>
          `<div class="soc-item">` +
          g.on
            .map((n) => `<img src="assets/socials/${n}.svg" alt="${SOCIAL_NAMES[n]}">`)
            .join("") +
          `<span class="handle">${serial(g.handle)}</span></div>`;
        return (
          `<div class="plate socpair ${cls}">` +
          `<div class="soc">${SOCIALS.slice(0, 2).map(one).join("")}</div>` +
          `<div class="soc">${SOCIALS.slice(2).map(one).join("")}</div></div>`
        );
      };

      const titlePlate = (cls) =>
        `<div class="plate title ${cls}"><b>MONEY TALKS</b><span><em>₹</em>MONDAY</span></div>`;

      const strapPlate = () =>
        `<div class="plate strap"><b>The Deep Effect</b>` +
        `<span>Money Talks Monday</span></div>`;

      /* The closed scenes' words, one cartouche each; smash.js shows the
         one for the scene on air. */
      const closedCarts = () =>
        `<div class="plate cart" data-k="start">` +
        `<div class="caps">Bank of Money Talks</div>` +
        `<div class="big">Starting<br>Soon</div>` +
        `<div class="count" id="countdown">05:00</div>` +
        `<div class="sn">No. ${SERIAL}</div></div>` +
        `<div class="plate cart" data-k="brb">` +
        `<div class="caps">I promise</div>` +
        `<div class="big">to be<br>right back</div>` +
        `<div class="deva">मैं धारक को अभी वापस आने<br>का वचन देता हूँ</div></div>` +
        `<div class="plate cart" data-k="end">` +
        `<div class="caps">Thanks for watching</div>` +
        `<div class="big">See you<br>next Monday</div>` +
        `<div class="sn">No. ${SERIAL}</div></div>`;

      const serialsPlate = () =>
        `<div class="plate serials">${socialsRow("stack")}</div>`;

      /* One coin face. `n` keeps the rim's path id unique: three coins (two
         are motion ghosts), two faces each. */
      function coinFace(n, front) {
        const id = `rim${n}${front ? "f" : "b"}`;
        return (
          `<div class="face ${front ? "front" : "back"}">` +
          `<div class="ground"></div>` +
          `<div class="portrait-wrap"><img class="portrait" src="assets/gandhi.png" alt=""></div>` +
          `<svg class="rim" viewBox="0 0 500 500">` +
          `<path id="${id}" fill="none" d="M32,250a218,218 0 1,1 436,0a218,218 0 1,1 -436,0"/>` +
          `<circle cx="250" cy="250" r="245" fill="none" stroke="#6d0a35" stroke-width="7"/>` +
          `<circle cx="250" cy="250" r="238" fill="none" stroke="#be1860" stroke-width="1.6" stroke-dasharray="2 5"/>` +
          `<circle cx="250" cy="250" r="207" fill="none" stroke="#6d0a35" stroke-width="5"/>` +
          `<text><textPath href="#${id}" textLength="1350" lengthAdjust="spacing">` +
          `BANK OF MONEY TALKS ✦ MONEY TALKS MONDAY ✦</textPath></text></svg>` +
          (front ? `<div class="shine"></div>` : "") +
          `</div>`
        );
      }

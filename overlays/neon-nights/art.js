/* overlays/neon-nights/art.js -- the Neon Nights art, drawn in code
   Plain script, not a module (docs/adr/0006). Loaded before cruise.js, which
   is where the page and the transition live. Nothing here runs by itself:
   every function returns a string of HTML or SVG for a scene's html().

   Everything on this page is generated. There is no art file in assets/ but
   the four social icons -- the sun, the palms, the skyline, the car, the
   radar and the ornaments are all paths computed here, which is why the
   whole overlay is ~40 KB of text and scales to the vertical canvas with no
   second set of images (docs/adr/0033).

   Coordinates are the CANVAS's: every builder takes a box in canvas px and
   returns an absolutely positioned element with its own viewBox, so a shape
   is authored once and placed at any size on either page. */
const ART = (() => {
  const r1 = (v) => Math.round(v * 10) / 10;
  const P = (v) => `${r1(v)}px`;
  /* A fixed-seed LCG. The skyline and the star field want variety, not
     surprise: the same page must draw the same city on every load, or a
     reconnect in the middle of a stream would redraw the skyline. */
  function rng(seed) {
    let s = seed >>> 0;
    return () => ((s = (s * 1664525 + 1013904223) >>> 0) / 4294967296);
  }
  /* The wrapper every builder returns: its own viewBox, placed in canvas px.
     `over` lifts it above the video (it is not inside the cut layer). */
  const art = (box, vb, inner, cls = "") =>
    `<svg class="art ${cls}" viewBox="0 0 ${vb[0]} ${vb[1]}" preserveAspectRatio="none"` +
    ` style="left:${P(box.x)};top:${P(box.y)};width:${P(box.w)};height:${P(box.h)}">${inner}</svg>`;

  /* ================================================================
     THE SUN -- the slatted disc every 80s sunset poster has.

     The slats are a MASK, not sky-coloured bars: the sky behind the sun is a
     gradient and a bar painted "the sky colour" is only ever right at one
     height. Masked out, the real sky shows through and the sun sits in it
     whatever is behind. Their heights grow downward and their gaps shrink,
     which is what makes the disc read as sinking rather than striped.
     ================================================================ */
  function sun({ x, y, r, cls = "", id = "sun" }) {
    const S = 2 * r,
      c = r,
      slats = 11;
    let bars = "";
    for (let i = 0; i < slats; i++) {
      const t = i / (slats - 1);
      const top = c + r * (0.12 + 0.80 * t * t * 0.9 + 0.08 * t);
      const h = r * (0.014 + 0.085 * t * t + 0.012 * t);
      if (top > S) break;
      bars += `<rect x="-2" y="${r1(top)}" width="${S + 4}" height="${r1(h)}"/>`;
    }
    return art(
      { x: x - r, y: y - r, w: S, h: S },
      [S, S],
      `<defs>
        <linearGradient id="${id}-g" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stop-color="#fff2a8"/>
          <stop offset=".18" stop-color="#ffd93d"/>
          <stop offset=".48" stop-color="#ff8a3d"/>
          <stop offset=".78" stop-color="#ff2d95"/>
          <stop offset="1" stop-color="#c81a7e"/>
        </linearGradient>
        <radialGradient id="${id}-h" cx=".5" cy=".5" r=".5">
          <stop offset=".52" stop-color="#ff6ab5" stop-opacity=".55"/>
          <stop offset=".78" stop-color="#ff2d95" stop-opacity=".16"/>
          <stop offset="1" stop-color="#ff2d95" stop-opacity="0"/>
        </radialGradient>
        <mask id="${id}-m">
          <circle cx="${c}" cy="${c}" r="${r1(r * 0.86)}" fill="#fff"/>
          <g fill="#000">${bars}</g>
        </mask>
      </defs>
      <circle cx="${c}" cy="${c}" r="${c}" fill="url(#${id}-h)"/>
      <g mask="url(#${id}-m)">
        <circle cx="${c}" cy="${c}" r="${r1(r * 0.86)}" fill="url(#${id}-g)"/>
        <circle cx="${c}" cy="${c}" r="${r1(r * 0.86)}" fill="none" stroke="#fff6d0" stroke-width="${r1(r * 0.022)}" stroke-opacity=".8"/>
      </g>`,
      "v-sun " + cls,
    );
  }

  /* ================================================================
     A PALM -- trunk and fronds, computed. A silhouette with a magenta rim on
     the sun side, which is what sells a sunset: the shape is nearly black and
     the edge is lit.

     Drawn 400 x 1000 and placed with preserveAspectRatio="none", so a box
     that is not 2 : 5 squashes the fronds flat. Every caller keeps h = 2.5w.
     The crown sits at 26% of the height: that, not the top edge, is where a
     palm reads from.
     ================================================================ */
  function palm({ x, y, w, h, lean = 0.08, flip = false, cls = "", seed = 7 }) {
    const W = 400,
      H = 1000,
      rand = rng(seed);
    const bx = W * 0.5,
      cy = H * 0.26,
      cx = bx + W * lean * 3,
      tw = W * 0.055;
    /* The trunk: a tapered curve, drawn as one filled outline so it narrows
       toward the crown the way a stroke cannot. */
    const trunk =
      `M${r1(bx - tw)} ${H}` +
      `C${r1(bx - tw * 0.85)} ${r1(H * 0.6)} ${r1(cx - tw * 0.55)} ${r1(cy + H * 0.14)} ${r1(cx - tw * 0.3)} ${r1(cy)}` +
      `L${r1(cx + tw * 0.3)} ${r1(cy)}` +
      `C${r1(cx + tw * 0.62)} ${r1(cy + H * 0.14)} ${r1(bx + tw * 0.95)} ${r1(H * 0.6)} ${r1(bx + tw * 1.1)} ${H}Z`;
    /* Rings up the trunk: the scars a palm actually has, and the only thing
       that stops it reading as a pole. */
    let rings = "";
    for (let i = 0; i < 13; i++) {
      const t = i / 13,
        ry = H - (H - cy) * t * 0.92 - 18,
        rw = tw * (1.05 - 0.5 * t);
      rings += `<path d="M${r1(bx - rw + (cx - bx) * t)} ${r1(ry)}q${r1(rw)} ${r1(10 - 4 * t)} ${r1(2 * rw)} 0" />`;
    }
    /* Fronds: a pointed leaf each, out from the crown and drooping. The two
       control points sit either side of the rib, so the leaf has a belly. */
    const FR = 9;
    let fronds = "";
    for (let i = 0; i < FR; i++) {
      const a = (-172 + (i * 160) / (FR - 1) + (rand() - 0.5) * 9) * (Math.PI / 180);
      const len = W * (0.52 + rand() * 0.24),
        droop = len * (0.42 + rand() * 0.3);
      const tx = cx + Math.cos(a) * len,
        ty = cy + Math.sin(a) * len * 0.72 + droop * 0.5;
      const mx = cx + Math.cos(a) * len * 0.5,
        my = cy + Math.sin(a) * len * 0.42;
      const bw = len * 0.17;
      const nx = -Math.sin(a) * bw,
        ny = Math.cos(a) * bw;
      fronds +=
        `<path d="M${r1(cx)} ${r1(cy)}Q${r1(mx + nx)} ${r1(my + ny)} ${r1(tx)} ${r1(ty)}` +
        `Q${r1(mx - nx * 0.7)} ${r1(my - ny * 0.7 + bw * 0.5)} ${r1(cx)} ${r1(cy)}Z"/>`;
    }
    /* Coconuts, because the crown is otherwise a hole in the shape. */
    const nuts = `<circle cx="${r1(cx - 14)}" cy="${r1(cy + 16)}" r="11"/><circle cx="${r1(cx + 12)}" cy="${r1(cy + 24)}" r="9"/><circle cx="${r1(cx + 1)}" cy="${r1(cy + 6)}" r="10"/>`;
    return art(
      { x, y, w, h },
      [W, H],
      `<g class="v-palm-sway">
        <g fill="#140428">${fronds}${nuts}</g>
        <g fill="none" stroke="#ff2d95" stroke-opacity=".5" stroke-width="3">${fronds}</g>
      </g>
      <path d="${trunk}" fill="#140428"/>
      <path d="${trunk}" fill="none" stroke="#ff2d95" stroke-opacity=".42" stroke-width="3"/>
      <g fill="none" stroke="#2a0a4a" stroke-width="3.4" stroke-linecap="round">${rings}</g>`,
      "v-palm " + (flip ? "flip " : "") + cls,
    );
  }

  /* ================================================================
     THE SKYLINE -- art deco Miami in silhouette, lit windows in it. Blocks
     are stepped, a few carry a spire, and every window strip is on the same
     grid so the city reads as one plane rather than as separate towers.
     ================================================================ */
  function skyline({ x, y, w, h, seed = 21, cls = "" }) {
    const W = 1600,
      H = 400,
      rand = rng(seed);
    let blocks = "",
      wins = "",
      neon = "";
    let bx = -40;
    while (bx < W + 40) {
      const bw = 52 + rand() * 118,
        bh = 86 + rand() * (H - 150);
      /* A stepped crown on the taller blocks: deco, not a glass box. Each
         step insets `ins` a side and rises 16, up the left, across, and back
         down the right, so the crown is symmetrical by construction. */
      const steps = bh > 250 ? 3 : bh > 155 ? 2 : 0,
        ins = bw * 0.08,
        top = H - bh;
      let d = `M${r1(bx)} ${H}V${r1(top + steps * 16)}`;
      for (let s = 0; s < steps; s++) d += `h${r1(ins)}v-16`;
      d += `H${r1(bx + bw - steps * ins)}`;
      for (let s = 0; s < steps; s++) d += `v16h${r1(ins)}`;
      d += `V${H}Z`;
      blocks += `<path d="${d}"/>`;
      if (bh > 250 && rand() > 0.45) {
        const sx = bx + bw / 2;
        blocks += `<path d="M${r1(sx - 4)} ${r1(top)}L${r1(sx)} ${r1(top - 46 - rand() * 40)}L${r1(sx + 4)} ${r1(top)}Z"/>`;
      }
      /* Windows on a shared 13 x 15 grid, lit at about one in three. */
      for (let gy = top + 18; gy < H - 10; gy += 15) {
        for (let gx = bx + 7; gx < bx + bw - 9; gx += 13) {
          if (rand() > 0.68) wins += `<rect x="${r1(gx)}" y="${r1(gy)}" width="5" height="7"/>`;
        }
      }
      /* One deco neon band per few blocks: the stripe every Ocean Drive
         hotel has along its cornice. */
      if (bw > 90 && rand() > 0.5)
        neon += `<rect x="${r1(bx + 4)}" y="${r1(top + 10 + rand() * 30)}" width="${r1(bw - 8)}" height="3" rx="1.5"/>`;
      bx += bw + 3 + rand() * 9;
    }
    return art(
      { x, y, w, h },
      [W, H],
      `<g fill="#190630">${blocks}</g>
       <g fill="#ffd93d" fill-opacity=".72">${wins}</g>
       <g fill="#16e0ff" fill-opacity=".8" class="v-flicker">${neon}</g>`,
      "v-skyline " + cls,
    );
  }

  /* ================================================================
     THE CAR -- an 80s wedge coupe, side on, tail lights lit. Used on BRB,
     where it drives, and small on END.
     ================================================================ */
  function car({ x, y, w, h, cls = "" }) {
    const W = 420,
      H = 150;
    const body =
      `M14 104C12 92 20 84 32 81L128 71L186 36C200 28 216 24 232 24H300C318 24 334 30 346 42L372 68L394 74C406 78 412 86 412 98V112H14Z`;
    const glass = `M150 68L202 42C212 37 222 34 234 34H296C310 34 322 39 331 48L352 68Z`;
    return art(
      { x, y, w, h },
      [W, H],
      `<defs>
        <linearGradient id="car-g" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stop-color="#2a0a4a"/><stop offset=".55" stop-color="#190630"/><stop offset="1" stop-color="#0d0320"/>
        </linearGradient>
      </defs>
      <ellipse cx="210" cy="126" rx="190" ry="11" fill="#ff2d95" fill-opacity=".2"/>
      <path d="${body}" fill="url(#car-g)"/>
      <path d="${body}" fill="none" stroke="#ff6ab5" stroke-opacity=".75" stroke-width="3"/>
      <path d="${glass}" fill="#16e0ff" fill-opacity=".2" stroke="#16e0ff" stroke-opacity=".6" stroke-width="2.4"/>
      <path d="M34 92h352" stroke="#ff2d95" stroke-opacity=".45" stroke-width="2"/>
      <g class="v-tail"><rect x="16" y="82" width="26" height="12" rx="4" fill="#ff2d95"/><rect x="16" y="82" width="26" height="12" rx="4" fill="none" stroke="#ff9ed2" stroke-width="2"/></g>
      <rect x="386" y="76" width="22" height="10" rx="4" fill="#fff6d0"/>
      <g fill="#0d0320" stroke="#ff6ab5" stroke-opacity=".7" stroke-width="3">
        <circle cx="104" cy="110" r="25"/><circle cx="330" cy="110" r="25"/>
      </g>
      <g fill="#16e0ff" fill-opacity=".55"><circle cx="104" cy="110" r="9"/><circle cx="330" cy="110" r="9"/></g>`,
      "v-car " + cls,
    );
  }

  /* ================================================================
     THE RADAR -- the HUD dial, bottom corner of GAME. HTML, not SVG: the
     sweep is a conic gradient and the grid two repeating ones, so the whole
     thing is four elements and one rotation.
     ================================================================ */
  function radar({ x, y, size, cls = "" }) {
    return (
      `<div class="radar ${cls}" style="left:${P(x)};top:${P(y)};width:${P(size)};height:${P(size)}">` +
      `<div class="rd-face"><div class="rd-grid"></div><div class="rd-sweep"></div>` +
      `<i class="rd-blip" style="left:68%;top:30%"></i><i class="rd-blip b2" style="left:28%;top:63%"></i>` +
      `<i class="rd-me"></i></div><div class="rd-ring"></div></div>`
    );
  }

  /* The wanted stars. Decorative -- nothing on the stream feeds them -- so
     they are drawn as the show's own mark rather than a readout that lies:
     `lit` of them are on, and the last lit one pulses. */
  function stars({ x, y, size, n = 5, lit = 2, cls = "" }) {
    const pt = (cx, cy, R) => {
      let d = "";
      for (let i = 0; i < 10; i++) {
        const a = (-90 + i * 36) * (Math.PI / 180),
          rr = i % 2 ? R * 0.42 : R;
        d += (i ? "L" : "M") + r1(cx + Math.cos(a) * rr) + " " + r1(cy + Math.sin(a) * rr);
      }
      return d + "Z";
    };
    const gap = size * 1.08;
    let g = "";
    for (let i = 0; i < n; i++)
      g += `<path class="${i < lit ? (i === lit - 1 ? "on pulse" : "on") : "off"}" d="${pt(size / 2 + i * gap, size / 2, size / 2)}"/>`;
    return art({ x, y, w: gap * (n - 1) + size, h: size }, [gap * (n - 1) + size, size], g, "v-stars " + cls);
  }

  /* A deco sunburst fan: the ornament behind a card's headline. */
  function burst({ x, y, w, h, rays = 26, cls = "" }) {
    const W = 1000,
      H = 500;
    let g = "";
    for (let i = 0; i < rays; i++) {
      const a0 = (-180 + (i * 180) / rays) * (Math.PI / 180),
        a1 = (-180 + ((i + 0.46) * 180) / rays) * (Math.PI / 180);
      g += `<path d="M500 ${H}L${r1(500 + Math.cos(a0) * 1200)} ${r1(H + Math.sin(a0) * 1200)}L${r1(500 + Math.cos(a1) * 1200)} ${r1(H + Math.sin(a1) * 1200)}Z"/>`;
    }
    return art({ x, y, w, h }, [W, H], `<g fill="#ff2d95" fill-opacity=".13">${g}</g>`, "v-burst " + cls);
  }

  /* The perspective floor: a plane laid back under the horizon, its lines
     running toward the viewer. HTML, so the scroll is one background-position
     animation instead of 60 re-laid paths a second. */
  function floor({ y, h, cls = "" }) {
    return `<div class="floor ${cls}" style="top:${P(y)};height:${P(h)}"><div class="fl-plane"></div></div>`;
  }

  /* A star field above the horizon, fixed by seed. */
  function stardust({ x, y, w, h, n = 90, seed = 5, cls = "" }) {
    const rand = rng(seed);
    let g = "";
    for (let i = 0; i < n; i++)
      g += `<circle cx="${r1(rand() * 1000)}" cy="${r1(Math.pow(rand(), 1.6) * 500)}" r="${r1(0.6 + rand() * 1.5)}" fill-opacity="${r1(0.25 + rand() * 0.6)}"/>`;
    return art({ x, y, w, h }, [1000, 500], `<g fill="#fff">${g}</g>`, "v-stardust " + cls);
  }

  return { sun, palm, skyline, car, radar, stars, burst, floor, stardust };
})();

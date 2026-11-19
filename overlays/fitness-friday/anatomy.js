/* overlays/fitness-friday/anatomy.js -- the blueprint plates
   Every anatomical drawing on the sheet: the body, the brain, the heart, the
   lungs and the hand, as yellow line work, plus the ECG trace. Plain script,
   not a module (docs/adr/0006). Both pages load it; nothing here knows the
   canvas.

   The procedural parts -- the brain's folds, the bronchial tree, the
   coronary twigs, the carpals -- come from a seeded generator, so every load
   draws the same plate.

   A plate is { name, vb:[x0, y0, W, H], layers, labels, texts, origin }:
     layers  [{cls, d, move, clip}] in local units, drawn in order. `move`
             puts a layer on the plate's animated layer (the beat, the
             breath, the wave); `clip` clips it to the plate's `clip` path.
     labels  [{key, name, at:[x,y], b:[x,y]}] -- a balloon at b with a
             leader to at, for the parts list.
     texts   [{x, y, t, px, anchor, rot}] -- px is screen size, not local.
   renderPlate(plate, box, opts) turns one into HTML at a canvas box. */

const ANATOMY = (() => {
  const f = (n) => Math.round(n * 10) / 10;
  const lerp = (a, b, k) => a + (b - a) * k;
  function rng(seed) {
    return () => {
      seed = (seed + 0x6d2b79f5) | 0;
      let t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
      t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }
  const mir = (pts, cx) => pts.map((p) => [2 * cx - p[0], p[1], p[2]]);

  /* ---- curves ------------------------------------------------------ */
  /* Catmull-Rom through pts, as cubic Béziers. A point [x, y, 1] is a
     corner: the curve arrives at it and leaves it straight. */
  function segs(pts, closed) {
    const n = pts.length,
      P = (i) => (closed ? pts[((i % n) + n) % n] : pts[Math.max(0, Math.min(n - 1, i))]),
      out = [];
    for (let i = 0; i < (closed ? n : n - 1); i++) {
      const p0 = P(i - 1),
        p1 = P(i),
        p2 = P(i + 1),
        p3 = P(i + 2);
      const c1 = p1[2] ? p1 : [p1[0] + (p2[0] - p0[0]) / 6, p1[1] + (p2[1] - p0[1]) / 6];
      const c2 = p2[2] ? p2 : [p2[0] - (p3[0] - p1[0]) / 6, p2[1] - (p3[1] - p1[1]) / 6];
      out.push([p1, c1, c2, p2]);
    }
    return out;
  }
  function smooth(pts, closed) {
    return (
      `M${f(pts[0][0])} ${f(pts[0][1])}` +
      segs(pts, closed)
        .map(([, a, b, p]) => `C${f(a[0])} ${f(a[1])} ${f(b[0])} ${f(b[1])} ${f(p[0])} ${f(p[1])}`)
        .join("") +
      (closed ? "Z" : "")
    );
  }
  /* The same curve, sampled: for tubes, offsets and inside tests. */
  function dense(pts, closed, k = 10) {
    const out = [];
    segs(pts, closed).forEach(([p, a, b, q]) => {
      for (let j = 0; j < k; j++) {
        const t = j / k,
          u = 1 - t;
        out.push([
          u * u * u * p[0] + 3 * u * u * t * a[0] + 3 * u * t * t * b[0] + t * t * t * q[0],
          u * u * u * p[1] + 3 * u * u * t * a[1] + 3 * u * t * t * b[1] + t * t * t * q[1],
        ]);
      }
    });
    if (!closed) out.push(pts[pts.length - 1].slice(0, 2));
    return out;
  }
  const poly = (pts, closed) =>
    "M" + pts.map((p) => `${f(p[0])} ${f(p[1])}`).join("L") + (closed ? "Z" : "");
  const circ = (x, y, r) =>
    `M${f(x - r)} ${f(y)}a${f(r)} ${f(r)} 0 1 0 ${f(2 * r)} 0a${f(r)} ${f(r)} 0 1 0 ${f(-2 * r)} 0`;
  const ellipse = (x, y, rx, ry) =>
    `M${f(x - rx)} ${f(y)}a${f(rx)} ${f(ry)} 0 1 0 ${f(2 * rx)} 0a${f(rx)} ${f(ry)} 0 1 0 ${f(-2 * rx)} 0`;
  /* A joint marker: a ring with a cross through it. */
  const joint = (x, y, r) =>
    circ(x, y, r) + `M${f(x - r * 1.7)} ${f(y)}H${f(x + r * 1.7)}M${f(x)} ${f(y - r * 1.7)}V${f(y + r * 1.7)}`;

  function inside(pg, [x, y]) {
    let c = false;
    for (let i = 0, j = pg.length - 1; i < pg.length; j = i++) {
      const [xi, yi] = pg[i],
        [xj, yj] = pg[j];
      if (yi > y !== yj > y && x < ((xj - xi) * (y - yi)) / (yj - yi) + xi) c = !c;
    }
    return c;
  }
  function distSeg(p, a, b) {
    const dx = b[0] - a[0],
      dy = b[1] - a[1],
      l = dx * dx + dy * dy;
    let t = l ? ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / l : 0;
    t = Math.max(0, Math.min(1, t));
    return Math.hypot(p[0] - a[0] - t * dx, p[1] - a[1] - t * dy);
  }
  function distPoly(p, pl, closed) {
    let m = Infinity;
    for (let i = 1; i < pl.length; i++) m = Math.min(m, distSeg(p, pl[i - 1], pl[i]));
    if (closed) m = Math.min(m, distSeg(p, pl[pl.length - 1], pl[0]));
    return m;
  }
  function normals(pts) {
    return pts.map((p, i) => {
      const a = pts[Math.max(0, i - 1)],
        b = pts[Math.min(pts.length - 1, i + 1)];
      const dx = b[0] - a[0],
        dy = b[1] - a[1],
        l = Math.hypot(dx, dy) || 1;
      return [-dy / l, dx / l];
    });
  }

  /* A vessel: a closed tube round a centreline, w0 wide at its start and w1
     at its end. Its cut ends are drawn as ellipses, the way a section is. */
  function vessel(center, w0, w1, { end = true, start = false } = {}) {
    const c = dense(center, false, 12),
      n = normals(c),
      L = c.length - 1;
    const side = (sg) =>
      c.map((p, i) => {
        const w = lerp(w0, w1, i / L) / 2;
        return [p[0] + n[i][0] * w * sg, p[1] + n[i][1] * w * sg];
      });
    const ell = (p, nn, w) => {
      const pts = [];
      for (let k = 0; k < 18; k++) {
        const t = (k / 18) * Math.PI * 2,
          a = (Math.cos(t) * w) / 2,
          b = Math.sin(t) * w * 0.2;
        pts.push([p[0] + nn[0] * a + nn[1] * b, p[1] + nn[1] * a - nn[0] * b]);
      }
      return poly(pts, true);
    };
    return {
      d: poly(side(1).concat(side(-1).reverse()), true),
      ends: (end ? ell(c[L], n[L], w1) : "") + (start ? ell(c[0], n[0], w0) : ""),
      line: c,
    };
  }

  /* A long bone from a to b: heads wa and wb wide, shaft between. */
  function bone(a, b, wa, wb, shaft) {
    const dx = b[0] - a[0],
      dy = b[1] - a[1],
      L = Math.hypot(dx, dy),
      ux = dx / L,
      uy = dy / L;
    const P = (d, s) => [a[0] + ux * d - uy * s, a[1] + uy * d + ux * s];
    const A = wa / 2,
      B = wb / 2,
      m = shaft / 2;
    return smooth(
      [
        P(-A * 0.3, -A * 0.6), P(-A * 0.42, 0), P(-A * 0.3, A * 0.6),
        P(A * 0.55, A), P(L * 0.34, m), P(L * 0.66, m), P(L - B * 0.55, B),
        P(L + B * 0.3, B * 0.6), P(L + B * 0.42, 0), P(L + B * 0.3, -B * 0.6),
        P(L - B * 0.55, -B), P(L * 0.66, -m), P(L * 0.34, -m), P(A * 0.55, -A),
      ],
      true,
    );
  }
  /* Its marrow line, for the long bones. */
  function marrow(a, b, inset = 0.22) {
    return `M${f(lerp(a[0], b[0], inset))} ${f(lerp(a[1], b[1], inset))}L${f(lerp(a[0], b[0], 1 - inset))} ${f(lerp(a[1], b[1], 1 - inset))}`;
  }
  /* A carpal: a rounded, slightly irregular pebble. */
  function pebble(x, y, rx, ry, rot, r) {
    const pts = [],
      c = Math.cos(rot),
      s = Math.sin(rot);
    for (let k = 0; k < 9; k++) {
      const t = (k / 9) * Math.PI * 2,
        j = 0.86 + r() * 0.24,
        px = Math.cos(t) * rx * j,
        py = Math.sin(t) * ry * j;
      pts.push([x + px * c - py * s, y + px * s + py * c]);
    }
    return smooth(pts, true);
  }

  /* Short curved twigs along a vessel: coronary branches, nerve endings. */
  function twigs(line, keep, r, { every = 26, len = [14, 34], ang = 0.95, side = 0 } = {}) {
    let d = "",
      acc = 0,
      flip = r() < 0.5 ? 1 : -1;
    for (let i = 1; i < line.length; i++) {
      acc += Math.hypot(line[i][0] - line[i - 1][0], line[i][1] - line[i - 1][1]);
      if (acc < every) continue;
      acc = 0;
      const [x, y] = line[i],
        [px, py] = line[i - 1],
        t = Math.atan2(y - py, x - px);
      flip = side || -flip;
      const a = t + flip * (ang + (r() - 0.5) * 0.5),
        l = lerp(len[0], len[1], r());
      const e = [x + Math.cos(a) * l, y + Math.sin(a) * l],
        m = [x + Math.cos(a - flip * 0.35) * l * 0.55, y + Math.sin(a - flip * 0.35) * l * 0.55];
      if (!keep(e)) continue;
      d += `M${f(x)} ${f(y)}Q${f(m[0])} ${f(m[1])} ${f(e[0])} ${f(e[1])}`;
    }
    return d;
  }

  /* ================================================================
     THE BODY -- front view, anatomical position, eight heads tall.
     Drawn on its right half (the viewer's right) and mirrored about x 200.
     ================================================================ */
  function body() {
    const CX = 200;
    const R = [
      [200, 22], [226, 26], [244, 40], [253, 62], [255, 86], [253, 103], [256, 109], [257, 121],
      [252, 131], [244, 140], [236, 150], [229, 161], [227, 173], [231, 185],
      [254, 192], [281, 200], [303, 206], [321, 214], [333, 232], [337, 258], [337, 286], [339, 312],
      [343, 342], [347, 372], [351, 396], [358, 420], [364, 448], [366, 478], [365, 506], [364, 520],
      [371, 532], [382, 551], [388, 573], [383, 586], [374, 580], [372, 597], [372, 618],
      [366, 636], [356, 646], [346, 644], [338, 630], [334, 604], [334, 574], [337, 548], [340, 524],
      [338, 500], [333, 470], [326, 442], [318, 418], [312, 398], [306, 370], [300, 336], [294, 306],
      [287, 277, 1],
      [283, 300], [279, 330], [273, 360], [267, 386], [265, 404], [270, 432], [280, 462], [288, 494],
      [292, 524], [292, 560], [289, 600], [284, 640], [280, 680], [276, 720], [274, 752], [277, 778],
      [283, 808], [285, 840], [281, 872], [274, 904], [268, 936], [264, 958], [266, 972],
      [275, 985], [277, 997], [267, 1005], [247, 1007], [232, 1003], [226, 990],
      [228, 968], [226, 946], [222, 914], [217, 876], [215, 840], [216, 806], [214, 776], [211, 748],
      [210, 712], [208, 670], [206, 626], [204, 580], [202, 545], [200, 532, 1],
    ];
    const outline = R.concat(mir(R.slice(1, -1), CX).reverse());
    /* Inner contours, right side; each is mirrored. */
    const lines = [
      [[243, 139], [224, 152], [200, 157]], // jaw
      [[244, 140], [228, 160], [210, 181]], // sternocleidomastoid
      [[206, 185], [232, 187], [262, 193], [296, 203]], // clavicle
      [[202, 196], [204, 240], [211, 270], [236, 286], [264, 280], [283, 262], [298, 236], [304, 216]], // pectoral
      [[296, 205], [303, 233], [312, 268], [322, 300], [331, 317]], // deltoid
      [[331, 318], [338, 350], [341, 382]], // biceps
      [[312, 300], [318, 336], [322, 372]],
      [[348, 404], [355, 440], [357, 482]], // brachioradialis
      [[326, 430], [340, 470], [351, 506]], // flexors
      [[271, 300], [262, 307]], [[269, 320], [259, 327]], [[267, 341], [257, 347]], // serratus
      [[228, 287], [234, 320], [236, 360], [232, 400], [222, 440], [208, 470], [201, 482]], // rectus
      [[200, 318], [218, 315], [233, 318]], [[200, 352], [220, 349], [236, 354]], [[200, 388], [218, 387], [234, 392]],
      [[265, 404], [254, 436], [236, 466], [214, 494], [204, 513]], // iliac
      [[262, 520], [256, 580], [250, 640], [244, 700], [240, 730]], // rectus femoris
      [[288, 560], [282, 620], [272, 680], [262, 722]], // vastus lateralis
      [[216, 640], [218, 690], [228, 724], [244, 736]], // vastus medialis
      [[282, 474], [262, 540], [240, 610], [222, 680], [214, 726]], // sartorius
      [[240, 774], [238, 830], [236, 890], [238, 950]], // tibia
      [[276, 790], [272, 840], [262, 892]], // peroneal
      [[222, 792], [226, 832], [230, 872]], // gastrocnemius
      [[352, 611], [354, 641]], [[361, 612], [362, 638]], [[344, 609], [345, 640]], // fingers
    ];
    const inner = lines.map((l) => smooth(l, false) + smooth(mir(l, CX), false)).join("");
    const navel = circ(200, 398, 3.2);
    const knees = ellipse(242, 748, 14, 17) + ellipse(158, 748, 14, 17);

    /* Construction: centre line, head units, height, joint markers. */
    const top = 22,
      sole = 1007,
      unit = (sole - top) / 8;
    let ruler = `M478 ${top}V${sole}`;
    const texts = [];
    for (let k = 0; k <= 8; k++) {
      const y = top + k * unit;
      ruler += `M468 ${f(y)}H488`;
      if (k < 8) ruler += `M473 ${f(y + unit / 2)}H483`;
      texts.push({ x: 496, y: y + 5, t: String(k), px: 13, anchor: "start" });
    }
    const heads = Array.from({ length: 9 }, (_, k) => `M150 ${f(top + k * unit)}H250`).join("");
    const dim =
      `M-78 ${top}V${sole}M-84 ${top + 12}L-78 ${top}L-72 ${top + 12}M-84 ${sole - 12}L-78 ${sole}L-72 ${sole - 12}` +
      `M-90 ${top}H190M-90 ${sole}H226`;
    texts.push({ x: -88, y: (top + sole) / 2, t: "1 800 MM", px: 13, anchor: "middle", rot: -90 });
    const J = [[305, 224], [331, 398], [352, 522], [272, 498], [242, 750], [246, 966]];
    const joints = J.concat(mir(J, CX)).map(([x, y]) => joint(x, y, 8)).join("");

    return {
      name: "body",
      vb: [-110, 0, 630, 1030],
      layers: [
        { cls: "k-dash", d: heads },
        { cls: "k-solid", d: smooth(outline, true) },
        { cls: "k-line", d: inner + navel + knees },
        { cls: "k-center", d: `M200 0V1030` },
        { cls: "k-fine", d: joints },
        { cls: "k-dim", d: ruler + dim },
      ],
      texts,
      labels: [
        { key: "A", name: "DELTOIDEUS", at: [333, 256], b: [432, 228] },
        { key: "B", name: "PECTORALIS MAJOR", at: [150, 250], b: [-34, 250] },
        { key: "C", name: "BICEPS BRACHII", at: [334, 344], b: [432, 340] },
        { key: "D", name: "RECTUS ABDOMINIS", at: [182, 352], b: [-34, 352] },
        { key: "E", name: "OBLIQUUS EXTERNUS", at: [148, 438], b: [-34, 446] },
        { key: "F", name: "QUADRICEPS FEMORIS", at: [266, 624], b: [432, 620] },
        { key: "G", name: "SARTORIUS", at: [160, 610], b: [-34, 610] },
        { key: "H", name: "TIBIALIS ANTERIOR", at: [244, 860], b: [432, 860] },
        { key: "I", name: "STERNOCLEIDOMASTOID", at: [175, 162], b: [-34, 146] },
        { key: "J", name: "PATELLA", at: [158, 748], b: [-34, 760] },
      ],
    };
  }

  /* ================================================================
     THE HEART -- anterior view, apex to the viewer's right. Its great
     vessels are tubes with cut ends; the coronaries run over it with
     seeded twigs, and a light wireframe gives it volume.
     ================================================================ */
  function heart() {
    const r = rng(11);
    const B = [
      [118, 170], [97, 190], [81, 222], [74, 262], [80, 300], [98, 332], [130, 354], [176, 374],
      [226, 394], [270, 410], [298, 420], [318, 406], [334, 374], [343, 330], [341, 286], [331, 248],
      [316, 224], [300, 214], [272, 214], [250, 210], [222, 224], [196, 214], [172, 202], [148, 184],
    ];
    const bodyLine = dense(B, true, 8);
    const keep = (p) => inside(bodyLine, p) && distPoly(p, bodyLine, true) > 6;

    const svc = vessel([[128, 26], [127, 90], [126, 150], [124, 186]], 34, 34, { end: false, start: true });
    const ivc = vessel([[100, 318], [98, 352], [97, 380]], 30, 28);
    const rpa = vessel([[238, 150], [214, 143], [192, 140]], 22, 20);
    const bct = vessel([[208, 80], [203, 50], [198, 20]], 20, 17);
    const lcc = vessel([[239, 66], [241, 38], [243, 10]], 13, 12);
    const lsa = vessel([[265, 66], [271, 38], [278, 10]], 15, 13);
    const aorta = vessel(
      [[190, 216], [184, 172], [184, 128], [196, 92], [222, 69], [256, 61], [288, 71], [306, 97], [313, 134], [314, 196]],
      46, 38, { end: false },
    );
    const pt = vessel([[226, 232], [231, 198], [243, 162], [266, 141], [302, 132], [348, 136]], 46, 21);

    const rca = dense([[176, 222], [152, 234], [124, 254], [104, 290], [106, 326], [138, 352]], false);
    const lad = dense([[246, 226], [256, 252], [262, 284], [268, 322], [278, 362], [290, 398], [297, 414]], false);
    const lcx = dense([[252, 222], [284, 226], [312, 234], [334, 250], [342, 276]], false);
    const d1 = dense([[262, 270], [284, 284], [306, 302], [326, 322]], false);
    const d2 = dense([[271, 332], [292, 348], [314, 368]], false);
    const marg = dense([[116, 334], [168, 359], [218, 379], [258, 397]], false);
    const vein = dense([[258, 230], [267, 256], [272, 288], [278, 326], [287, 364]], false);
    const coronaries = [rca, lad, lcx, d1, d2, marg].map((l) => poly(l)).join("");
    const branches =
      twigs(lad, keep, r, { every: 16, len: [16, 40] }) +
      twigs(rca, keep, r, { every: 18, side: 1, len: [16, 38] }) +
      twigs(marg, keep, r, { every: 18, side: -1 }) +
      twigs(d1, keep, r, { every: 16 }) +
      twigs(d2, keep, r, { every: 15 }) +
      twigs(lcx, keep, r, { every: 18, side: 1 });

    let wire = "";
    for (let k = 1; k <= 9; k++)
      wire += `M50 ${170 + k * 26}Q210 ${222 + k * 34} 370 ${148 + k * 28}`;
    for (let k = 0; k <= 6; k++) wire += `M${80 + k * 42} 170Q${120 + k * 36} 330 298 430`;

    const ra = [[118, 192], [134, 178], [156, 176], [176, 186], [190, 204], [186, 216], [172, 214], [160, 222], [146, 220], [134, 226], [122, 214]];
    const la = [[300, 196], [318, 184], [338, 186], [352, 200], [350, 218], [340, 228], [326, 236], [312, 232], [302, 220]];
    const solid = (v) => [{ cls: "k-solid", d: v.d, move: 1 }, { cls: "k-line", d: v.ends, move: 1 }];
    return {
      name: "heart",
      vb: [0, -14, 420, 450],
      clip: smooth(B, true),
      origin: [215, 300],
      layers: [
        { cls: "k-dash", d: rpa.d + rpa.ends, move: 1 },
        ...solid(svc),
        ...solid(ivc),
        { cls: "k-solid", d: smooth(B, true), move: 1 },
        { cls: "k-ghost", d: wire, clip: 1, move: 1 },
        { cls: "k-dash", d: poly(vein), move: 1 },
        { cls: "k-bold", d: coronaries, move: 1 },
        { cls: "k-line", d: branches, move: 1 },
        ...solid(bct),
        ...solid(lcc),
        ...solid(lsa),
        { cls: "k-solid", d: aorta.d, move: 1 },
        { cls: "k-ghost", d: smooth([[178, 120], [186, 92], [210, 74]], false), move: 1 },
        ...solid(pt),
        { cls: "k-ghost", d: smooth([[236, 214], [240, 188], [252, 162]], false), move: 1 },
        { cls: "k-solid", d: smooth(ra, true), move: 1 },
        { cls: "k-solid", d: smooth(la, true), move: 1 },
        { cls: "k-fine", d: smooth([[132, 206], [152, 198], [172, 204]], false) + smooth([[312, 210], [330, 204], [342, 212]], false), move: 1 },
      ],
      labels: [
        { key: "A", name: "AORTA", at: [306, 104], b: [396, 82] },
        { key: "B", name: "TRUNCUS PULMONALIS", at: [240, 178], b: [396, 160] },
        { key: "C", name: "VENA CAVA SUPERIOR", at: [127, 86], b: [24, 64] },
        { key: "D", name: "ATRIUM DEXTRUM", at: [90, 262], b: [24, 252] },
        { key: "E", name: "VENTRICULUS DEXTER", at: [186, 322], b: [24, 344] },
        { key: "F", name: "A. CORONARIA", at: [262, 284], b: [398, 250] },
        { key: "G", name: "VENTRICULUS SINISTER", at: [318, 326], b: [398, 330] },
        { key: "H", name: "APEX CORDIS", at: [297, 417], b: [386, 418] },
      ],
    };
  }

  /* ================================================================
     THE BRAIN -- lateral view, facing left. The folds are a labyrinth
     grown by an activator-inhibitor rule (two blurs, a sign step,
     renormalise), steered so the major sulci are valleys with gyri on
     both sides, then traced with marching squares and clipped to the
     cerebrum.
     ================================================================ */
  function folds(outline, sulci, { W, H, cell = 3.6, seed = 7, iters = 40, level = 0 }) {
    const nx = Math.ceil(W / cell) + 1,
      ny = Math.ceil(H / cell) + 1,
      N = nx * ny,
      r = rng(seed);
    let v = new Float32Array(N);
    for (let i = 0; i < N; i++) v[i] = r() * 2 - 1;
    const mask = new Uint8Array(N),
      near = new Float32Array(N).fill(1e9);
    for (let j = 0; j < ny; j++)
      for (let i = 0; i < nx; i++) {
        const p = [i * cell, j * cell],
          k = j * nx + i;
        if (!inside(outline, p) && distPoly(p, outline, true) > 2 * cell) continue;
        mask[k] = 1;
        for (const s of sulci) near[k] = Math.min(near[k], distPoly(p, s));
      }
    const tmp = new Float32Array(N),
      a = new Float32Array(N),
      b = new Float32Array(N);
    const box = (src, dst, rad, horiz) => {
      const len = horiz ? nx : ny,
        lines = horiz ? ny : nx;
      for (let l = 0; l < lines; l++) {
        const at = (q) => (horiz ? l * nx + q : q * nx + l);
        let s = 0;
        for (let q = -rad; q <= rad; q++) s += src[at(Math.max(0, Math.min(len - 1, q)))];
        for (let q = 0; q < len; q++) {
          dst[at(q)] = s / (2 * rad + 1);
          s += src[at(Math.min(len - 1, q + rad + 1))] - src[at(Math.max(0, q - rad))];
        }
      }
    };
    const blur = (src, dst, rad) => {
      box(src, tmp, rad, true);
      box(tmp, dst, rad, false);
      box(dst, tmp, rad, true);
      box(tmp, dst, rad, false);
    };
    for (let it = 0; it < iters; it++) {
      blur(v, a, 1);
      blur(v, b, 2);
      let mean = 0;
      for (let i = 0; i < N; i++) {
        v[i] += 0.07 * Math.sign(a[i] - b[i]);
        if (near[i] < 1.4 * cell) v[i] = -1.2;
        else if (near[i] < 3.4 * cell) v[i] = Math.max(v[i], 0.7);
        mean += v[i];
      }
      mean /= N;
      let mx = 1e-6;
      for (let i = 0; i < N; i++) mx = Math.max(mx, Math.abs(v[i] - mean));
      for (let i = 0; i < N; i++) v[i] = (v[i] - mean) / mx;
    }
    blur(v, a, 1);
    const val = a;

    /* Marching squares at `level`, joined into polylines. Edge ids: a
       horizontal edge (i,j)-(i+1,j) is j*nx+i, a vertical one N+j*nx+i. */
    const pos = new Map(),
      adj = new Map();
    const point = (id) => {
      if (pos.has(id)) return pos.get(id);
      const vert = id >= N,
        k = vert ? id - N : id,
        i = k % nx,
        j = (k / nx) | 0;
      const v0 = val[k],
        v1 = vert ? val[k + nx] : val[k + 1],
        t = (level - v0) / (v1 - v0 || 1e-6);
      const p = vert ? [i * cell, (j + t) * cell] : [(i + t) * cell, j * cell];
      pos.set(id, p);
      return p;
    };
    const link = (x, y) => {
      if (!adj.has(x)) adj.set(x, []);
      if (!adj.has(y)) adj.set(y, []);
      adj.get(x).push(y);
      adj.get(y).push(x);
    };
    for (let j = 0; j < ny - 1; j++)
      for (let i = 0; i < nx - 1; i++) {
        const k = j * nx + i;
        if (!(mask[k] && mask[k + 1] && mask[k + nx] && mask[k + nx + 1])) continue;
        const A = val[k] > level,
          Bv = val[k + 1] > level,
          C = val[k + nx + 1] > level,
          D = val[k + nx] > level;
        const idx = (A << 3) | (Bv << 2) | (C << 1) | D;
        if (idx === 0 || idx === 15) continue;
        const T = k,
          Rt = N + k + 1,
          Bt = k + nx,
          Lt = N + k;
        const mid = (val[k] + val[k + 1] + val[k + nx] + val[k + nx + 1]) / 4 > level;
        switch (idx) {
          case 1: case 14: link(Lt, Bt); break;
          case 2: case 13: link(Bt, Rt); break;
          case 3: case 12: link(Lt, Rt); break;
          case 4: case 11: link(T, Rt); break;
          case 6: case 9: link(T, Bt); break;
          case 7: case 8: link(T, Lt); break;
          case 5: if (mid) { link(T, Lt); link(Bt, Rt); } else { link(T, Rt); link(Lt, Bt); } break;
          case 10: if (mid) { link(T, Rt); link(Lt, Bt); } else { link(T, Lt); link(Bt, Rt); } break;
        }
      }
    const used = new Set(),
      out = [];
    const trace = (s) => {
      const line = [s];
      used.add(s);
      let cur = s;
      for (;;) {
        const nxt = adj.get(cur).find((q) => !used.has(q));
        if (nxt === undefined) break;
        line.push(nxt);
        used.add(nxt);
        cur = nxt;
      }
      const closed = line.length > 2 && adj.get(cur).includes(s);
      if (line.length < 4) return;
      /* One Chaikin pass rounds off the grid's corners. */
      let pts = line.map(point);
      const ch = [];
      const n = pts.length;
      for (let q = 0; q < (closed ? n : n - 1); q++) {
        const p = pts[q],
          o = pts[(q + 1) % n];
        ch.push([p[0] * 0.75 + o[0] * 0.25, p[1] * 0.75 + o[1] * 0.25], [p[0] * 0.25 + o[0] * 0.75, p[1] * 0.25 + o[1] * 0.75]);
      }
      out.push(poly(closed ? ch : [pts[0], ...ch, pts[n - 1]], closed));
    };
    for (const [k, nb] of adj) if (nb.length === 1 && !used.has(k)) trace(k);
    for (const [k] of adj) if (!used.has(k)) trace(k);
    return out.join("");
  }

  function brain(tune = {}) {
    const C = [
      [58, 262], [42, 226], [44, 180], [62, 132], [98, 86], [150, 50], [218, 28], [296, 20], [374, 28],
      [446, 54], [506, 96], [548, 148], [570, 200], [568, 244], [552, 276], [520, 292], [474, 298],
      [430, 296], [404, 304], [384, 322], [350, 342], [300, 354], [250, 352], [208, 338], [180, 316],
      [164, 288], [176, 272, 1], [140, 276], [100, 276], [70, 270],
    ];
    const outline = dense(C, true, 8);
    const sylvian = dense([[176, 272], [220, 258], [270, 244], [318, 226], [352, 208], [368, 192], [372, 178]], false);
    const central = dense([[318, 22], [312, 50], [302, 80], [298, 110], [284, 140], [276, 170], [264, 198], [258, 226]], false);
    const temporal = dense([[204, 302], [258, 292], [318, 274], [376, 252], [418, 240]], false);
    const parieto = dense([[470, 58], [474, 88], [466, 118]], false);
    const cb = [[404, 318], [430, 304], [480, 300], [530, 298], [556, 300], [568, 318], [562, 346], [540, 372], [500, 388], [456, 390], [424, 378], [406, 356], [400, 336]];
    let folia = "";
    for (let k = 0; k < 17; k++) {
      const y = 306 + k * 5.4;
      folia += `M396 ${f(y + 24 - k * 0.6)}Q484 ${f(y - 16 + k * 2.2)} 574 ${f(y + 8)}`;
    }
    const stem = [[380, 326], [362, 346], [356, 372], [362, 396], [366, 440], [400, 440], [404, 410], [412, 384], [416, 356], [410, 334]];
    const gyri = folds(outline, [sylvian, central, temporal, parieto], { W: 600, H: 400, ...tune });
    return {
      name: "brain",
      vb: [0, 0, 600, 444],
      clip: smooth(C, true),
      cbClip: smooth(cb, true),
      layers: [
        { cls: "k-solid", d: smooth(stem, true) },
        { cls: "k-ghost", d: "M368 360Q388 352 412 362M366 392Q386 384 406 392" },
        { cls: "k-solid", d: smooth(cb, true) },
        { cls: "k-fine", d: folia, clip: "cb" },
        { cls: "k-solid", d: smooth(C, true) },
        { cls: "k-fine", d: gyri, clip: 1 },
        { cls: "k-bold", d: poly(sylvian) + poly(central) },
        { cls: "k-line", d: poly(temporal) + poly(parieto) },
        { cls: "k-bold", d: smooth(C, true) },
      ],
      labels: [
        { key: "A", name: "LOBUS FRONTALIS", at: [120, 160], b: [40, 60] },
        { key: "B", name: "LOBUS PARIETALIS", at: [390, 110], b: [520, 30] },
        { key: "C", name: "LOBUS OCCIPITALIS", at: [530, 220], b: [590, 160] },
        { key: "D", name: "LOBUS TEMPORALIS", at: [260, 318], b: [200, 410] },
        { key: "E", name: "CEREBELLUM", at: [500, 352], b: [580, 420] },
        { key: "F", name: "TRUNCUS ENCEPHALI", at: [386, 420], b: [320, 432] },
      ],
    };
  }

  /* ================================================================
     THE LUNGS -- anterior view: trachea with its rings, the main
     bronchi, two lungs (the left with its cardiac notch), their fissures,
     and a seeded bronchial tree grown inside each, ending in alveoli.
     ================================================================ */
  function lungs() {
    const r = rng(23);
    const RL = [
      [188, 58], [160, 72], [130, 104], [106, 150], [88, 206], [74, 268], [64, 330], [60, 388], [66, 428],
      [84, 442], [120, 432], [160, 416], [196, 408], [222, 414], [236, 404], [238, 370], [234, 320],
      [228, 272], [222, 244], [216, 226], [214, 200], [222, 170], [224, 130], [214, 92], [202, 68],
    ];
    const LL = [
      [332, 58], [360, 72], [390, 104], [414, 150], [432, 206], [446, 268], [456, 330], [460, 388],
      [454, 428], [436, 442], [400, 434], [364, 420], [330, 414], [308, 418], [296, 404], [300, 386],
      [314, 366], [319, 342], [312, 316], [298, 296], [292, 272], [298, 244], [304, 226], [306, 200],
      [298, 170], [296, 130], [306, 92], [318, 68],
    ];
    const rl = dense(RL, true, 8),
      ll = dense(LL, true, 8);
    const levels = [[], [], [], [], [], [], [], [], []],
      alveoli = [];
    function grow(p, ang, len, depth, lung) {
      let e,
        ok = false;
      for (let t = 0; t < 4 && !ok; t++) {
        e = [p[0] + Math.cos(ang) * len, p[1] + Math.sin(ang) * len];
        ok = inside(lung, e) && distPoly(e, lung, true) > 7;
        if (!ok) len *= 0.68;
      }
      if (!ok) return;
      const bend = (r() - 0.5) * len * 0.3;
      const m = [(p[0] + e[0]) / 2 - Math.sin(ang) * bend, (p[1] + e[1]) / 2 + Math.cos(ang) * bend];
      levels[depth].push(`M${f(p[0])} ${f(p[1])}Q${f(m[0])} ${f(m[1])} ${f(e[0])} ${f(e[1])}`);
      if (depth === 0) {
        alveoli.push(circ(e[0], e[1], 2.6));
        return;
      }
      const s = 0.3 + r() * 0.24;
      grow(e, ang - s * (0.7 + r() * 0.6), len * (0.72 + r() * 0.12), depth - 1, lung);
      grow(e, ang + s * (0.7 + r() * 0.6), len * (0.72 + r() * 0.12), depth - 1, lung);
    }
    const D = Math.PI / 180;
    grow([204, 204], -150 * D, 34, 6, rl); // right upper lobe
    grow([198, 238], 152 * D, 34, 6, rl); // right middle lobe
    grow([198, 238], 102 * D, 50, 7, rl); // right lower lobe
    grow([206, 214], -112 * D, 30, 5, rl);
    grow([330, 212], -36 * D, 36, 6, ll); // left upper lobe
    grow([334, 232], 52 * D, 32, 6, ll); // lingula
    grow([334, 232], 80 * D, 50, 7, ll); // left lower lobe
    grow([324, 210], -78 * D, 30, 5, ll);

    const trachea = vessel([[260, -12], [260, 60], [260, 150]], 36, 34, { end: false, start: true });
    let rings = "";
    for (let y = 0; y <= 132; y += 12) rings += `M243 ${y}Q260 ${y + 6} 277 ${y}`;
    const rb = vessel([[254, 146], [232, 172], [212, 196], [202, 214]], 26, 18, { end: false });
    const lb = vessel([[266, 146], [292, 166], [316, 190], [332, 214]], 24, 17, { end: false });
    const inter = vessel([[204, 206], [200, 222], [198, 240]], 17, 14, { end: false });
    const heartBehind = smooth([[236, 300], [270, 286], [318, 300], [346, 340], [350, 390], [320, 428], [270, 444], [232, 424], [222, 370]], true);
    let ribs = "";
    for (let k = 0; k < 9; k++) {
      const y = 84 + k * 40;
      ribs += `M248 ${y}Q150 ${y - 14} ${46 + k * 2} ${y + 46}M272 ${y}Q370 ${y - 14} ${474 - k * 2} ${y + 46}`;
    }
    const w = (cls, ds) => ({ cls, d: ds.join(""), move: 1 });
    return {
      name: "lungs",
      vb: [10, -24, 500, 500],
      origin: [260, 60],
      layers: [
        { cls: "k-ghost", d: ribs },
        { cls: "k-dash", d: heartBehind },
        { cls: "k-dash", d: "M44 452Q150 398 260 436Q370 398 476 452" },
        { cls: "k-solid", d: smooth(RL, true), move: 1 },
        { cls: "k-solid", d: smooth(LL, true), move: 1 },
        { cls: "k-line", d: smooth([[92, 236], [140, 240], [190, 246], [222, 250]], false), move: 1 },
        { cls: "k-line", d: smooth([[100, 178], [130, 260], [170, 350], [200, 408]], false), move: 1 },
        { cls: "k-line", d: smooth([[420, 172], [392, 262], [356, 350], [330, 414]], false), move: 1 },
        w("k-hair", [...levels[0], ...levels[1], ...alveoli]),
        w("k-fine", [...levels[2], ...levels[3]]),
        w("k-line", [...levels[4], ...levels[5]]),
        w("k-bold", [...levels[6], ...levels[7], ...levels[8]]),
        { cls: "k-solid", d: inter.d, move: 1 },
        { cls: "k-solid", d: rb.d, move: 1 },
        { cls: "k-solid", d: lb.d, move: 1 },
        { cls: "k-solid", d: trachea.d, move: 1 },
        { cls: "k-line", d: trachea.ends + rings, move: 1 },
      ],
      labels: [
        { key: "A", name: "TRACHEA", at: [260, 40], b: [180, 6] },
        { key: "B", name: "BRONCHUS PRINCIPALIS", at: [300, 176], b: [372, 24] },
        { key: "C", name: "LOBUS SUPERIOR", at: [150, 140], b: [40, 90] },
        { key: "D", name: "LOBUS MEDIUS", at: [140, 290], b: [30, 270] },
        { key: "E", name: "LOBUS INFERIOR", at: [400, 360], b: [490, 330] },
        { key: "F", name: "DIAPHRAGMA", at: [380, 422], b: [480, 470] },
      ],
    };
  }

  /* ================================================================
     THE HAND -- palm view, raised, fingers spread: phalanges and
     metacarpals as long bones, eight seeded carpal pebbles, and the
     radius and ulna. The hand waves about the wrist; the forearm stays.
     ================================================================ */
  function hand() {
    const r = rng(5);
    const fingers = [
      // [metacarpal base, head], phalanges..., widths [mc, p1, p2, p3]
      { pts: [[136, 304], [104, 252], [100, 246], [80, 204], [77, 198], [66, 170]], w: [17, 14, 11] },
      { pts: [[156, 300], [146, 196], [145, 190], [138, 132], [137, 126], [133, 92], [132, 87], [130, 64]], w: [15, 13, 11, 9] },
      { pts: [[176, 300], [176, 188], [176, 182], [177, 118], [177, 112], [178, 74], [178, 69], [179, 44]], w: [16, 14, 11, 9] },
      { pts: [[194, 302], [204, 196], [205, 190], [214, 130], [215, 124], [221, 90], [222, 85], [226, 62]], w: [15, 13, 11, 9] },
      { pts: [[208, 306], [228, 212], [230, 206], [246, 160], [247, 154], [255, 128], [256, 123], [261, 104]], w: [14, 12, 10, 8] },
    ];
    let bones = "",
      marrows = "";
    fingers.forEach((g) => {
      for (let i = 0; i + 1 < g.pts.length; i += 2) {
        const w = g.w[i / 2],
          a = g.pts[i],
          b = g.pts[i + 1];
        bones += bone(a, b, w * 1.15, w, w * 0.62);
        if (i < 4) marrows += marrow(a, b);
      }
    });
    const carpals = [
      [147, 339, 16, 10, -0.5], [171, 343, 13, 10, 0], [194, 339, 11, 9, 0.2], [210, 328, 7, 7, 0],
      [135, 317, 12, 9, -0.7], [155, 313, 10, 8, 0], [176, 315, 11, 13, 0], [198, 313, 12, 11, 0.3],
    ]
      .map(([x, y, rx, ry, rot]) => pebble(x, y, rx, ry, rot, r))
      .join("");
    const radius = bone([152, 358], [142, 500], 54, 26, 19);
    const ulna = bone([206, 360], [215, 500], 26, 22, 14);
    return {
      name: "hand",
      vb: [26, 30, 300, 474],
      origin: [176, 360],
      layers: [
        { cls: "k-solid", d: radius + ulna },
        { cls: "k-fine", d: marrow([152, 358], [142, 500], 0.2) + marrow([206, 360], [215, 500], 0.2) },
        { cls: "k-solid", d: bones, move: 1 },
        { cls: "k-fine", d: marrows, move: 1 },
        { cls: "k-solid", d: carpals, move: 1 },
        { cls: "k-center", d: "M176 30V480" },
      ],
      labels: [
        { key: "A", name: "PHALANGES DISTALES", at: [179, 52], b: [100, 44] },
        { key: "B", name: "PHALANGES MEDIAE", at: [221, 104], b: [300, 70] },
        { key: "C", name: "OSSA METACARPI", at: [204, 250], b: [300, 238] },
        { key: "D", name: "OSSA CARPI", at: [196, 320], b: [300, 326] },
        { key: "E", name: "RADIUS", at: [144, 430], b: [60, 420] },
        { key: "F", name: "ULNA", at: [212, 430], b: [300, 430] },
      ],
    };
  }

  /* ---- the ECG trace ------------------------------------------------
     A real lead-II complex: P, the PR segment, QRS, the ST segment, T,
     then diastole until the next beat.

     The intervals are in SECONDS, not in fractions of the beat, because
     that is what a heart does. A QRS is ~90 ms at 50 bpm and ~90 ms at
     160; what a faster heart shortens is the rest between beats, and the
     QT, which follows Bazett (QT = QTc x sqrt(RR)). Drawn as fractions of
     the beat -- which is what this did until 2026-11-07 -- the whole
     complex stretches and squashes with the rate, and no heart has ever
     done that.

     `rr` is one beat's width in px and `speed` the paper speed in px/s,
     so seconds and px are the same measurement twice. `amp` is the height
     of R; everything else is a fraction of it, in lead-II proportions.
     -------------------------------------------------------------------- */
  const QTC = 0.4,          // s: Bazett's constant, a healthy adult
    P_D = 0.09,             // s: the P wave
    PR_D = 0.07,            // s: the flat PR segment after it
    QRS_D = 0.09;           // s: Q, R and S together

  function ecg(beats, rr, amp, y0, speed) {
    const RR = rr / speed;
    /* QT cannot outrun the beat it sits in: at a sprint the complex takes
       nearly the whole cycle and diastole is what is left. */
    const QT = Math.min(QTC * Math.sqrt(RR), RR * 0.78),
      tail = Math.max(0.06, QT - QRS_D),
      ST_D = tail * 0.35,
      T_D = tail * 0.65,
      span = P_D + PR_D + QRS_D + ST_D + T_D,
      /* Above ~190 bpm even that does not fit; squeeze the lot rather
         than let one beat draw over the next. */
      k = span > RR * 0.94 ? (RR * 0.94) / span : 1;
    const pts = [];
    for (let b = 0; b < beats; b++) {
      const x0 = b * rr,
        put = (t, y) => pts.push([x0 + t * k * speed, y0 - y * amp]);
      put(0, 0);
      /* P: low and round, the atria filling. */
      for (let i = 1; i < 7; i++) put((P_D * i) / 6, 0.15 * Math.sin((i / 6) * Math.PI));
      put(P_D, 0);
      put(P_D + PR_D, 0);
      /* QRS: three straight limbs, because it is a spike and not a curve. */
      const q = P_D + PR_D;
      put(q + QRS_D * 0.22, -0.1);
      put(q + QRS_D * 0.45, 1);
      put(q + QRS_D * 0.72, -0.25);
      put(q + QRS_D, 0);
      const st = q + QRS_D;
      put(st + ST_D, 0);
      /* T: asymmetric -- a slow climb and a quicker fall, so the peak
         sits about 60% of the way through. */
      for (let i = 1; i < 11; i++) {
        const u = i / 10;
        put(st + ST_D + T_D * u, 0.28 * Math.sin(Math.pow(u, 1.35) * Math.PI));
      }
      /* Diastole: flat to the next beat. This is the part the rate
         actually moves. */
      pts.push([x0 + rr, y0]);
    }
    return poly(pts);
  }

  return { body, heart, brain, lungs, hand, ecg, circ };
})();

/* ================================================================
   RENDER -- a plate into HTML at a canvas box, contained and centred
   (opts.ax / opts.ay move it inside the box). Strokes keep their screen
   width at any scale (vector-effect), so every plate draws with one line
   weight. Animated layers go into their own SVG in a div the CSS moves,
   so a heartbeat is a composited transform rather than a repaint.
     opts.anim     the class that moves the animated layer
     opts.balloons false hides the callouts
     opts.lite     drops the finest line work, for small copies
   ================================================================ */
let PLATE_UID = 0;
function renderPlate(pl, box, opts = {}) {
  const [x0, y0, W, H] = pl.vb;
  const s = Math.min(box.w / W, box.h / H),
    w = W * s,
    h = H * s;
  const x = box.x + (box.w - w) * (opts.ax ?? 0.5),
    y = box.y + (box.h - h) * (opts.ay ?? 0.5);
  const id = `${pl.name}-${++PLATE_UID}`;
  const fine = /k-(hair|ghost)/;
  const keep = (l) => !(opts.lite && fine.test(l.cls));
  const path = (l) =>
    `<path class="${l.cls}" d="${l.d}"${l.clip ? ` clip-path="url(#${id}-${l.clip === 1 ? "c" : l.clip})"` : ""}/>`;
  const defs =
    `<defs>${pl.clip ? `<clipPath id="${id}-c"><path d="${pl.clip}"/></clipPath>` : ""}` +
    `${pl.cbClip ? `<clipPath id="${id}-cb"><path d="${pl.cbClip}"/></clipPath>` : ""}</defs>`;
  const svg = (ls, extra = "") =>
    `<svg class="plate-art" viewBox="${x0} ${y0} ${W} ${H}" width="${w.toFixed(1)}" height="${h.toFixed(1)}">${defs}${ls.filter(keep).map(path).join("")}${extra}</svg>`;
  const texts = (pl.texts || [])
    .map(
      (t) =>
        `<text x="${t.x}" y="${t.y}" font-size="${(t.px / s).toFixed(2)}" text-anchor="${t.anchor || "start"}"${t.rot ? ` transform="rotate(${t.rot} ${t.x} ${t.y})"` : ""}>${t.t}</text>`,
    )
    .join("");
  const still = pl.layers.filter((l) => !l.move),
    moving = pl.layers.filter((l) => l.move);
  const P = ([px, py]) => [(px - x0) * s, (py - y0) * s];
  const notes =
    opts.balloons === false
      ? ""
      : `<svg class="plate-notes" viewBox="0 0 ${w.toFixed(1)} ${h.toFixed(1)}" width="${w.toFixed(1)}" height="${h.toFixed(1)}">` +
        (pl.labels || [])
          .map((l) => {
            const [ax, ay] = P(l.at),
              [bx, by] = P(l.b),
              R = 13,
              dx = ax - bx,
              dy = ay - by,
              d = Math.hypot(dx, dy) || 1;
            return (
              `<path class="lead" d="M${(bx + (dx / d) * R).toFixed(1)} ${(by + (dy / d) * R).toFixed(1)}L${ax.toFixed(1)} ${ay.toFixed(1)}"/>` +
              `<circle class="dot" cx="${ax.toFixed(1)}" cy="${ay.toFixed(1)}" r="3"/>` +
              `<circle class="ball" cx="${bx.toFixed(1)}" cy="${by.toFixed(1)}" r="${R}"/>` +
              `<text x="${bx.toFixed(1)}" y="${(by + 4.6).toFixed(1)}">${l.key}</text>`
            );
          })
          .join("") +
        `</svg>`;
  const o = pl.origin ? P(pl.origin) : [w / 2, h / 2];
  return (
    `<div class="plate p-${pl.name}" style="left:${x.toFixed(1)}px;top:${y.toFixed(1)}px;width:${w.toFixed(1)}px;height:${h.toFixed(1)}px">` +
    `<div class="plate-body">` +
    svg(still, texts) +
    (moving.length
      ? `<div class="plate-move ${opts.anim || ""}" style="transform-origin:${o[0].toFixed(1)}px ${o[1].toFixed(1)}px">${svg(moving)}</div>`
      : "") +
    notes +
    `</div><i class="scan"></i></div>`
  );
}

/* The parts list a plate's balloons point into. */
function partsList(pl, cls = "", style = "") {
  return (
    `<div class="parts ${cls}" style="${style}"><div class="parts-h"><span>ITEM</span><span>DESCRIPTION</span></div>` +
    pl.labels.map((l) => `<div><b>${l.key}</b><span>${l.name}</span></div>`).join("") +
    `</div>`
  );
}

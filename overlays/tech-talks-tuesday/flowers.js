/* overlays/tech-talks-tuesday/flowers.js -- the garden, and the wind in it
   Sunflowers, tulips, grass, small daisies and drifting pollen, drawn as 2D
   shapes on ascii.js's source canvas, which turns them into ASCII. They do
   not turn: they sway in a breeze, and every few seconds a gust runs
   through from left to right, bending stems and fluttering petals before it
   dies away (the user asked for that in place of rotating, 2026-11-03).

   Drawn the way a botanical plate is composed (2026-11-03 research, see
   CLAUDE.md): clusters in odd numbers, varied heights, buds beside open
   flowers, overlap, darker and smaller toward the back, one focal flower off
   centre, and room left around the words. Thin cuts between petals, round
   the seed head and along leaf veins leave gaps the ASCII traces in line
   characters, so each flower reads as a drawing, not a blob.

   Plain script (docs/adr/0006); nothing runs until a page asks. */

      /* ================================================================
   THEMES — `?bg=NAME` picks one; phosphor is the default (ADR 0023). Adapted from the restrained ramps
   in Lospec's Nostalgia, Ice Cream GB, Rustic GB and Mist GB; these are
   custom palettes, not exact copies. Olive uses sage, parchment, honey
   and dusty rose, with a separate honey ramp so sunflowers stay distinct
   from tulips. Pink uses plum type, bronze sunflowers and teal foliage.
   Ramps run light to dark. Sources and rationale: docs/adr/0019.
   ================================================================ */
      const THEMES = {
        olive: {
          ground: "#1c251d",
          band: "#141c16",
          glass: "#0c120e",
          line: "#83947a",
          ink: "#e5dfc6",
          dim: "#93a087",
          accent: "#e8c985",
          beam: "#fff6d3",
          title: ["#e5dfc6", "#b2bba1"],
          fx: { glow: 1.2, scan: 0.13 },
          bloom: 0.18,
          green: ["#bdc6a4", "#91a27c", "#657b58", "#40553e"],
          warm: ["#f0d9bd", "#dca58f", "#bc7b79", "#74545d"],
          petal: ["#f0dca0", "#d8b66a", "#ae8650", "#74594a"],
          seed: "#b99a69",
        },
        pink: {
          ground: "#f3d9de",
          band: "#ebc8d1",
          glass: "#2c2137",
          line: "#764462",
          ink: "#43263d",
          dim: "#a96868",
          accent: "#764462",
          beam: "#ffffff",
          title: ["#764462", "#2c2137"],
          fx: { glow: 0, scan: 0.04 },
          bloom: 0,
          green: ["#39a78d", "#258b76", "#216e5d", "#214d43"],
          warm: ["#fa4c8c", "#e32d75", "#bc245e", "#85274e"],
          petal: ["#ffc536", "#f2a51b", "#d98114", "#a35422"],
          seed: "#43263d",
          css: {
            surface: "#f3d9de", band: "#ebc8d1", ink: "#43263d", muted: "#795866", hair: "rgba(67,38,61,.23)",
            accent: "#9e4e70", "ink-soft": "#68485b", "ink-topic": "#674458", live: "#356b63",
            "disc-a": "#f9e9eb", "disc-b": "#e6b8c7", "disc-rim": "rgba(255,255,255,.65)", orbit: "rgba(131,66,95,.23)",
            "hole-a": "#302432", "hole-b": "#433646", "hole-ink": "#d6bdcc",
          },
        },
        /* Tech candidates for the fusion page, 2026-11-03, after the user
           turned pink down. Each carries `css`, the page's colour variables
           (tech.css), which fusion.js applies; `glow` is the transition's
           line colour. Dark grounds are tinted rather than black, as the
           phosphor references advise.
           phosphor: green-phosphor terminal, #4ade80, amber sunflowers.
           lime: Filmora's "Cyber Lime", charcoal navy, lime and aqua.
           midnight: midnight navy with electric cyan and an iris violet. */
        phosphor: {
          ground: "#0b110d",
          glow: "#4ade80",
          green: ["#86efac", "#4ade80", "#22a35a", "#14532d"],
          warm: ["#a5f3fc", "#22d3ee", "#0e9fb8", "#155e75"],
          petal: ["#ffd27a", "#ffb000", "#d98a00", "#8a5200"],
          seed: "#1c3a26",
          css: {
            surface: "#0b110d", band: "#08100b", ink: "#c9f7d6", muted: "#6f9a7c", hair: "rgba(74,222,128,.22)",
            accent: "#4ade80", "ink-soft": "#9cc7a8", "ink-topic": "#7fb08d", live: "#4ade80",
            "disc-a": "#12301e", "disc-b": "#0b1a11", "disc-rim": "rgba(74,222,128,.30)", orbit: "rgba(74,222,128,.22)",
            "hole-a": "#0e1a12", "hole-b": "#15261a", "hole-ink": "#4ade80",
          },
        },
        lime: {
          ground: "#111827",
          glow: "#d4ff1a",
          green: ["#5eead4", "#00e0b8", "#0f9f87", "#115e59"],
          warm: ["#e9ff7a", "#d4ff1a", "#9fc400", "#5c7300"],
          petal: ["#ffe066", "#facc15", "#ca8a04", "#854d0e"],
          seed: "#111827",
          css: {
            surface: "#111827", band: "#0b1120", ink: "#f9fafb", muted: "#94a3b8", hair: "rgba(148,163,184,.22)",
            accent: "#d4ff1a", "ink-soft": "#cbd5e1", "ink-topic": "#9fb0c6", live: "#00e0b8",
            "disc-a": "#1e293b", "disc-b": "#0f172a", "disc-rim": "rgba(0,224,184,.35)", orbit: "rgba(0,224,184,.25)",
            "hole-a": "#1e293b", "hole-b": "#273449", "hole-ink": "#00e0b8",
          },
        },
        midnight: {
          ground: "#0d1b2a",
          glow: "#22d3ee",
          green: ["#67e8f9", "#22d3ee", "#0891b2", "#164e63"],
          warm: ["#c7cbff", "#8f96ff", "#6366f1", "#3730a3"],
          petal: ["#fde68a", "#fbbf24", "#d97706", "#92400e"],
          seed: "#0d1b2a",
          css: {
            surface: "#0d1b2a", band: "#0a1522", ink: "#e0e1dd", muted: "#778da9", hair: "rgba(119,141,169,.28)",
            accent: "#22d3ee", "ink-soft": "#b8c4d6", "ink-topic": "#9aaac2", live: "#22d3ee",
            "disc-a": "#1b263b", "disc-b": "#0d1b2a", "disc-rim": "rgba(143,150,255,.35)", orbit: "rgba(143,150,255,.28)",
            "hole-a": "#1b263b", "hole-b": "#253552", "hole-ink": "#8f96ff",
          },
        },
      };
      const THEME = THEMES[new URLSearchParams(location.search).get("bg")] || THEMES.phosphor;

      /* ================================================================
   THE WIND — how far, and which way, the air pushes at time t (s) at
   canvas x (px): a light breeze always, and a gust every 6-10 s that rises
   in 0.7 s, dies over about 2 s and travels left to right at 900 px/s.
   ================================================================ */
      const hash01 = (k) => {
        const x = Math.sin(k * 127.1 + 311.7) * 43758.5453;
        return x - Math.floor(x);
      };
      function wind(t, x) {
        const tt = t - x / 900;
        const P = 7.5,
          k0 = Math.floor(tt / P);
        let g = 0;
        for (let k = k0 - 1; k <= k0; k++) {
          const tau = tt - (k * P + hash01(k) * 2.5);
          if (tau < 0) continue;
          const env = tau < 0.7 ? Math.sin(((tau / 0.7) * Math.PI) / 2) : Math.exp(-(tau - 0.7) / 1.5);
          g += env * (0.65 + 0.35 * hash01(k + 99)) * (1 + 0.22 * Math.sin(tau * 9 + x * 0.013));
        }
        return 0.1 * Math.sin(tt * 1.1 + x * 0.004) + 0.05 * Math.sin(tt * 2.3 + x * 0.011) + g;
      }

      /* ================================================================
   DRAWING HELPERS — canvas px, y down.
   ================================================================ */
      const lerp = (a, b, k) => a + (b - a) * k;

      /* A ramp colour by position 0 (light) .. 3 (dark), pushed darker by
         depth 0 (front) .. 1 (back): what recedes darkens toward the ground. */
      const tone = (ramp, i, depth = 0) => ramp[Math.min(ramp.length - 1, Math.round(i + depth * 1.6))];

      function onCurve(p0, p1, p2, s) {
        const x = (1 - s) ** 2 * p0[0] + 2 * (1 - s) * s * p1[0] + s * s * p2[0],
          y = (1 - s) ** 2 * p0[1] + 2 * (1 - s) * s * p1[1] + s * s * p2[1],
          dx = 2 * (1 - s) * (p1[0] - p0[0]) + 2 * s * (p2[0] - p1[0]),
          dy = 2 * (1 - s) * (p1[1] - p0[1]) + 2 * s * (p2[1] - p1[1]);
        return [x, y, Math.atan2(dy, dx)];
      }

      /* A tapering stem along a quadratic curve. */
      function stem(ctx, p0, p1, p2, w0, w1, fill) {
        const L = [],
          R = [];
        for (let i = 0; i <= 18; i++) {
          const [x, y, a] = onCurve(p0, p1, p2, i / 18),
            w = lerp(w0, w1, i / 18) / 2;
          L.push([x + Math.sin(a) * w, y - Math.cos(a) * w]);
          R.push([x - Math.sin(a) * w, y + Math.cos(a) * w]);
        }
        ctx.beginPath();
        L.forEach(([x, y], i) => (i ? ctx.lineTo(x, y) : ctx.moveTo(x, y)));
        R.reverse().forEach(([x, y]) => ctx.lineTo(x, y));
        ctx.closePath();
        ctx.fillStyle = fill;
        ctx.fill();
      }

      /* A thin cut through what is drawn: the ASCII traces it as a line. */
      function cut(ctx, w, draw) {
        ctx.save();
        ctx.globalCompositeOperation = "destination-out";
        ctx.lineWidth = w;
        ctx.lineCap = "round";
        ctx.lineJoin = "round";
        ctx.beginPath();
        draw();
        ctx.stroke();
        ctx.restore();
      }

      /* A leaf from its base at (0, 0) to its tip at (len, 0): heart-shaped
         at the base for a sunflower, long and narrow for a tulip; serrated
         if `teeth`; a midrib and side veins cut through it. */
      function leaf(ctx, len, wid, o) {
        const N = 28,
          up = [],
          dn = [];
        for (let i = 0; i <= N; i++) {
          const u = i / N;
          let w = wid * Math.pow(Math.sin(Math.PI * Math.pow(u, o.heart ? 0.55 : 0.8)), 0.9);
          if (o.heart && u < 0.2) w *= 1 + (0.2 - u) * 1.6;
          if (o.teeth && u > 0.12 && u < 0.92) w *= 1 + 0.07 * Math.abs(Math.sin(u * o.teeth * Math.PI));
          const bend = o.curl * len * u * u;
          up.push([u * len, -w + bend]);
          dn.push([u * len, w * (o.fold ?? 1) + bend]);
        }
        ctx.beginPath();
        up.forEach(([x, y], i) => (i ? ctx.lineTo(x, y) : ctx.moveTo(x, y)));
        dn.reverse().forEach(([x, y]) => ctx.lineTo(x, y));
        ctx.closePath();
        const g = ctx.createLinearGradient(0, -wid, 0, wid);
        g.addColorStop(0, o.light);
        g.addColorStop(1, o.dark);
        ctx.fillStyle = g;
        ctx.fill();
        cut(ctx, o.vein ?? 3, () => {
          ctx.moveTo(len * 0.04, o.curl * len * 0.0016);
          for (let i = 1; i <= 10; i++) {
            const u = 0.04 + (i / 10) * 0.86;
            ctx.lineTo(u * len, o.curl * len * u * u);
          }
          if (o.heart)
            [0.3, 0.5, 0.7].forEach((u) => {
              const y = o.curl * len * u * u;
              ctx.moveTo(u * len, y);
              ctx.lineTo((u + 0.14) * len, y - wid * 0.55);
              ctx.moveTo(u * len, y);
              ctx.lineTo((u + 0.14) * len, y + wid * 0.55);
            });
        });
      }

      /* ================================================================
   THE SUNFLOWER — o: { x, ground, h: the head's height, r: its radius,
   view: how far it faces us (1 full, 0.7 turned), face: which way it is
   turned (+1 right, -1 left), depth, seed }. Its stem curves into a neck,
   its heavy head nods in a gust, its petals flutter.
   ================================================================ */
      function drawSunflower(ctx, o, t) {
        const T = THEME,
          rnd = rng(o.seed || 5),
          d = o.depth || 0,
          w = wind(t, o.x),
          bend = w * o.h * 0.12,
          p0 = [o.x, o.ground],
          p2 = [o.x + bend + o.face * o.r * 0.15, o.ground - o.h + Math.abs(bend) * 0.1],
          p1 = [o.x - o.face * o.r * 0.12 + bend * 0.2, o.ground - o.h * 0.55];
        stem(ctx, p0, p1, p2, o.r * 0.15, o.r * 0.1, tone(T.green, 2, d));
        /* Leaves on petioles, alternating, drooping, lifting in a gust. */
        const leaves = o.leaves || [[0.3, 1, 1], [0.52, -1, 0.85], [0.72, 1, 0.6]];
        leaves.forEach(([s, side, k]) => {
          const [x, y, a] = onCurve(p0, p1, p2, s);
          ctx.save();
          ctx.translate(x, y);
          ctx.rotate(a + side * (1.75 - 0.3 * w * side));
          stem(ctx, [0, 0], [o.r * 0.12, 0], [o.r * 0.24, 0], 5, 3, tone(T.green, 2, d));
          ctx.translate(o.r * 0.22, 0);
          ctx.rotate(side * 0.35);
          leaf(ctx, o.r * 1.15 * k, o.r * 0.42 * k, {
            heart: true,
            teeth: 26,
            curl: side * (0.0012 + 0.0006 * w),
            light: tone(T.green, 1, d),
            dark: tone(T.green, 3, d),
          });
          ctx.restore();
        });
        /* The head: drawn face-on about its centre, then squeezed to turn
           it, and tilted with the stem's tip. */
        const [, , tipA] = onCurve(p0, p1, p2, 1);
        ctx.save();
        ctx.translate(p2[0], p2[1]);
        ctx.rotate(tipA + Math.PI / 2 + o.face * 0.12 + w * 0.08);
        ctx.scale(o.view || 0.88, 1);
        const R = o.r,
          rd = R * 0.4,
          N = 17;
        const petals = (count, off, r0, len, wid, light, dark, flutterK) => {
          for (let i = 0; i < count; i++) {
            const a = ((i + off) / count) * 2 * Math.PI + (rnd() - 0.5) * 0.12 + flutterK * Math.max(0, w) * Math.sin(i * 1.7 + t * 9),
              L = len * (0.82 + rnd() * 0.3),
              W = wid * (0.8 + rnd() * 0.4),
              curl = (rnd() - 0.5) * W * 1.4;
            ctx.save();
            ctx.rotate(a);
            ctx.beginPath();
            ctx.moveTo(r0, -W * 0.35);
            ctx.bezierCurveTo(r0 + L * 0.3, -W, r0 + L * 0.72, -W * 0.85 + curl, r0 + L, curl);
            ctx.bezierCurveTo(r0 + L * 0.72, W * 0.85 + curl, r0 + L * 0.3, W, r0, W * 0.35);
            ctx.closePath();
            const g = ctx.createLinearGradient(r0, 0, r0 + L, 0);
            g.addColorStop(0, dark);
            g.addColorStop(0.55, light);
            g.addColorStop(1, light);
            ctx.fillStyle = g;
            ctx.fill();
            ctx.restore();
          }
        };
        /* Green bracts behind, then two rings of petals, the back ring
           deeper in tone. */
        for (let i = 0; i < 13; i++) {
          ctx.save();
          ctx.rotate((i / 13) * 2 * Math.PI + 0.2);
          ctx.beginPath();
          ctx.moveTo(rd * 0.9, -R * 0.07);
          ctx.quadraticCurveTo(rd + R * 0.3, 0, rd * 0.9, R * 0.07);
          ctx.quadraticCurveTo(rd + R * 0.42, 0, rd * 0.9, -R * 0.07);
          ctx.fillStyle = tone(T.green, 2, d);
          ctx.fill();
          ctx.restore();
        }
        petals(N, 0.5, rd * 0.92, R * 0.66, R * 0.14, tone(T.petal, 1, d), tone(T.petal, 2, d), 0.05);
        petals(N, 0, rd * 0.92, R * 0.58, R * 0.13, tone(T.petal, 0, d), tone(T.petal, 1, d), 0.08);
        /* Cuts between the front petals, so each is drawn on its own. */
        cut(ctx, 4, () => {
          for (let i = 0; i < N; i++) {
            const a = ((i + 0.5) / N) * 2 * Math.PI;
            ctx.moveTo(Math.cos(a) * rd * 1.02, Math.sin(a) * rd * 1.02);
            ctx.lineTo(Math.cos(a) * R * 0.78, Math.sin(a) * R * 0.78);
          }
        });
        /* The seed head: a ring of florets, a dark disc, seeds in Vogel's
           spiral, and a cut round its rim. */
        ctx.fillStyle = tone(T.petal, 2, d);
        ctx.beginPath();
        ctx.arc(0, 0, rd, 0, 2 * Math.PI);
        ctx.fill();
        ctx.fillStyle = tone(T.petal, 3, d);
        ctx.beginPath();
        ctx.arc(0, 0, rd * 0.82, 0, 2 * Math.PI);
        ctx.fill();
        ctx.fillStyle = T.seed;
        const S = 120,
          GA = Math.PI * (3 - Math.sqrt(5));
        for (let k = 8; k < S; k++) {
          const rr = rd * 0.8 * Math.sqrt((k + 0.5) / S),
            a = k * GA;
          ctx.beginPath();
          ctx.arc(rr * Math.cos(a), rr * Math.sin(a), rd * 0.045, 0, 2 * Math.PI);
          ctx.fill();
        }
        cut(ctx, 3, () => ctx.arc(0, 0, rd * 1.02, 0, 2 * Math.PI));
        ctx.restore();
      }

      /* ================================================================
   THE TULIP — o: { x, ground, h, s: cup size, open: 0 (bud) .. 1, lean,
   hue: 0..1 how far down the warm ramp, depth, leaf: -1/1 }. Three outer
   petals round three inner ones; a bud is narrow and closed.
   ================================================================ */
      function drawTulip(ctx, o, t) {
        const T = THEME,
          d = o.depth || 0,
          w = wind(t, o.x),
          bend = w * o.h * 0.2 + o.lean * o.h * 0.12,
          p0 = [o.x, o.ground],
          p2 = [o.x + bend, o.ground - o.h + Math.abs(bend) * 0.15],
          p1 = [o.x + bend * 0.12, o.ground - o.h * 0.5];
        /* Leaves first, from the base: long, broad, curling outward. */
        const lv = o.leaves ?? 1;
        for (let k = 0; k < lv; k++) {
          const side = k ? -o.leaf : o.leaf;
          ctx.save();
          ctx.translate(o.x, o.ground - o.h * 0.02);
          ctx.rotate(-Math.PI / 2 + side * (0.38 + k * 0.15) - w * 0.12);
          leaf(ctx, o.h * (0.58 - k * 0.12), o.s * 0.2, {
            curl: side * (0.0028 + 0.0012 * w),
            fold: 0.55,
            light: tone(T.green, 1, d),
            dark: tone(T.green, 3, d),
            vein: 2.2,
          });
          ctx.restore();
        }
        stem(ctx, p0, p1, p2, o.s * 0.11, o.s * 0.08, tone(T.green, 2, d));
        const [, , tipA] = onCurve(p0, p1, p2, 1);
        ctx.save();
        ctx.translate(p2[0], p2[1]);
        ctx.rotate(tipA + Math.PI / 2);
        const s = o.s,
          op = o.open,
          narrow = lerp(0.62, 1, op),
          base = o.hue * 1.6,
          light = tone(T.warm, base, d),
          mid = tone(T.warm, base + 1, d),
          dark = tone(T.warm, base + 2, d);
        ctx.scale(narrow, 1);
        /* The outer petals behind, their tips flaring as it opens. */
        ctx.fillStyle = dark;
        [-1, 1].forEach((sd) => {
          ctx.beginPath();
          ctx.moveTo(0, 0);
          ctx.bezierCurveTo(sd * 0.55 * s, -0.08 * s, sd * (0.62 + op * 0.12) * s, -0.82 * s, sd * (0.34 + op * 0.2) * s, -1.22 * s);
          ctx.bezierCurveTo(sd * 0.2 * s, -1.0 * s, sd * 0.06 * s, -0.5 * s, 0, 0);
          ctx.fill();
        });
        /* The inner petal between them, and the lit front petal. */
        ctx.fillStyle = mid;
        ctx.beginPath();
        ctx.moveTo(-0.3 * s, -0.2 * s);
        ctx.quadraticCurveTo(-0.28 * s, -1.0 * s, 0, -1.18 * s);
        ctx.quadraticCurveTo(0.28 * s, -1.0 * s, 0.3 * s, -0.2 * s);
        ctx.fill();
        const g = ctx.createLinearGradient(-0.3 * s, -1.25 * s, 0.25 * s, 0);
        g.addColorStop(0, light);
        g.addColorStop(1, mid);
        ctx.fillStyle = g;
        ctx.beginPath();
        ctx.moveTo(-0.36 * s, -0.1 * s);
        ctx.bezierCurveTo(-0.46 * s, -0.7 * s, -0.2 * s, -1.08 * s, 0.02 * s, -1.3 * s);
        ctx.bezierCurveTo(0.22 * s, -1.08 * s, 0.46 * s, -0.7 * s, 0.36 * s, -0.1 * s);
        ctx.quadraticCurveTo(0, 0.06 * s, -0.36 * s, -0.1 * s);
        ctx.fill();
        /* The front petal's edges, cut, so its shape reads against the
           petals behind it. */
        cut(ctx, 2.4, () => {
          ctx.moveTo(-0.36 * s, -0.1 * s);
          ctx.bezierCurveTo(-0.46 * s, -0.7 * s, -0.2 * s, -1.08 * s, 0.02 * s, -1.3 * s);
          ctx.moveTo(0.36 * s, -0.1 * s);
          ctx.bezierCurveTo(0.46 * s, -0.7 * s, 0.22 * s, -1.08 * s, 0.02 * s, -1.3 * s);
        });
        ctx.restore();
      }

      /* A small daisy: five cream petals and a dot, on a thread of stem. */
      function drawDaisy(ctx, o, t) {
        const w = wind(t, o.x),
          tx = o.x + w * o.h * 0.3,
          ty = o.ground - o.h;
        ctx.strokeStyle = tone(THEME.green, 2, o.depth || 0);
        ctx.lineWidth = 2;
        ctx.beginPath();
        ctx.moveTo(o.x, o.ground);
        ctx.quadraticCurveTo(o.x + w * o.h * 0.05, o.ground - o.h * 0.5, tx, ty);
        ctx.stroke();
        ctx.fillStyle = THEME.warm[0];
        for (let i = 0; i < 5; i++) {
          const a = (i / 5) * 2 * Math.PI + w * 0.12;
          ctx.beginPath();
          ctx.ellipse(tx + Math.cos(a) * o.s * 0.55, ty + Math.sin(a) * o.s * 0.55, o.s * 0.5, o.s * 0.28, a, 0, 2 * Math.PI);
          ctx.fill();
        }
        ctx.fillStyle = THEME.warm[2];
        ctx.beginPath();
        ctx.arc(tx, ty, o.s * 0.3, 0, 2 * Math.PI);
        ctx.fill();
      }

      /* A tuft of grass: a few blades from one root, leaning with the wind. */
      function drawTuft(ctx, o, t) {
        const rnd = rng(o.seed),
          w = wind(t, o.x);
        ctx.lineCap = "round";
        for (let i = 0; i < o.n; i++) {
          const h = o.h * (0.45 + rnd() * 0.6),
            spread = (rnd() - 0.5) * o.h * 0.7,
            lean = w * h * 0.45 + spread;
          ctx.strokeStyle = tone(THEME.green, 1 + Math.floor(rnd() * 2), o.depth || 0);
          ctx.lineWidth = 2.6;
          ctx.beginPath();
          ctx.moveTo(o.x + (rnd() - 0.5) * 6, o.ground);
          ctx.quadraticCurveTo(o.x + lean * 0.25, o.ground - h * 0.6, o.x + lean, o.ground - h);
          ctx.stroke();
        }
      }

      /* Pollen drifting on the air, rising slowly and pushed by the wind. */
      function drawPollen(ctx, o, t) {
        const rnd = rng(o.seed || 7);
        ctx.fillStyle = THEME.warm[0];
        for (let i = 0; i < o.n; i++) {
          const x0 = o.x0 + rnd() * (o.x1 - o.x0),
            y0 = o.y0 + rnd() * (o.y1 - o.y0),
            sp = 8 + rnd() * 14,
            ph = rnd() * 100;
          const span = o.y1 - o.y0,
            y = o.y1 - (((y0 - o.y0) + (t + ph) * sp) % span);
          const x = x0 + Math.sin((t + ph) * 0.6) * 18 + wind(t, x0) * 40;
          ctx.globalAlpha = 0.55 + 0.45 * Math.sin((t + ph) * 1.3);
          ctx.beginPath();
          ctx.arc(x, y, 2.4, 0, 2 * Math.PI);
          ctx.fill();
        }
        ctx.globalAlpha = 1;
      }

      /* ================================================================
   A GARDEN — a composed list of plants, drawn back to front. Each item
   is [kind, options]; options in canvas px.
   ================================================================ */
      const DRAW = { sun: drawSunflower, tulip: drawTulip, daisy: drawDaisy, tuft: drawTuft, pollen: drawPollen };
      function makeGarden(items) {
        const sorted = items.slice().sort((a, b) => (b[1].depth || 0) - (a[1].depth || 0));
        return {
          draw(ctx, t) {
            sorted.forEach(([kind, o]) => DRAW[kind](ctx, o, t));
          },
        };
      }

      /* Grass along a stretch: tufts every so often, seeded. */
      function meadow(x0, x1, ground, o = {}) {
        const rnd = rng(o.seed || 13),
          out = [];
        for (let x = x0 + rnd() * 30; x < x1; x += (o.gap || 38) * (0.6 + rnd() * 0.8))
          out.push(["tuft", { x, ground, h: (o.h || 34) * (0.6 + rnd() * 0.7), n: 3 + Math.floor(rnd() * 4), seed: Math.floor(rnd() * 1e6), depth: o.depth || 0 }]);
        return out;
      }

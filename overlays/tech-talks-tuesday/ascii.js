/* overlays/tech-talks-tuesday/ascii.js -- pictures into ASCII
   The look of "AIR" (Llama's spot for Amazon Prime, the user's reference
   of 2026-11-03): a shape is filled with running text, and its edges are
   drawn in line characters, / \ | - _ ( ) ' . and the like.

   A cell wholly inside a shape takes the next letter of a running wall of
   text, so words run across the shape as it moves. A cell on an edge takes
   the line character whose shape fits the edge best: Alex Harri's method
   ("ASCII characters are not pixels", 2026), six staggered sampling
   circles per cell compared with the same six for every candidate
   character, sharpened against ten circles just outside the cell.

   The picture is a "source": coverage and colour at 2 × 2 px samples, drawn
   by the page on a canvas. Plain script (docs/adr/0006). */

      const SX = 4,
        SY = 6; /* samples per 8 × 12 cell: 2 × 2 px each */

      /* The characters an edge may be drawn in: printable ASCII, the line
         artist's set. Fill letters come from the wall instead. */
      const EDGE_CHARS = [..." .,'`-_~^/\\|()<>[]+=:;!"];

      /* Circles in cell px, 8 × 12. Internal: TL TR ML MR BL BR, the left
         column lowered and the right raised. External: two above, three on
         each side, two below. */
      const C_IN = [[2.2, 2.5], [5.8, 1.7], [2.2, 6.5], [5.8, 5.7], [2.2, 10.3], [5.8, 9.5]],
        R_IN = 2.6;
      const C_EX = [
        [2.2, -1.8], [5.8, -1.8],
        [-1.9, 2.5], [9.9, 1.7],
        [-1.9, 6.5], [9.9, 5.7],
        [-1.9, 10.3], [9.9, 9.5],
        [2.2, 13.8], [5.8, 13.8],
      ],
        R_EX = 2.1;
      const AFFECTS = [[0, 1, 2, 4], [0, 1, 3, 5], [2, 4, 6], [3, 5, 7], [4, 6, 8, 9], [5, 7, 8, 9]];

      function circleSamples([cx, cy], r) {
        const out = [];
        for (let dy = -SY; dy < 2 * SY; dy++)
          for (let dx = -SX; dx < 2 * SX; dx++) {
            const x = ((dx + 0.5) * CELL_W) / SX,
              y = ((dy + 0.5) * CELL_H) / SY;
            if ((x - cx) ** 2 + (y - cy) ** 2 <= r * r) out.push([dx, dy]);
          }
        return out;
      }
      const S_IN = C_IN.map((c) => circleSamples(c, R_IN)),
        S_EX = C_EX.map((c) => circleSamples(c, R_EX));

      /* Each edge character's six ink fractions, measured from the font,
         normalised per circle. Measured again once the font has loaded. */
      let SHAPES = null,
        shapeCache = new Map();
      function measureShapes() {
        const K = 4,
          c = document.createElement("canvas");
        c.width = CELL_W * K;
        c.height = CELL_H * K;
        const g = c.getContext("2d", { willReadFrequently: true });
        g.font = `${SCREEN_FONT_PX * K}px ${SCREEN_FONT}`;
        g.textAlign = "center";
        g.textBaseline = "middle";
        g.fillStyle = g.strokeStyle = "#fff";
        g.lineWidth = 0.55 * K;
        const raw = EDGE_CHARS.map((ch) => {
          g.clearRect(0, 0, c.width, c.height);
          g.fillText(ch, c.width / 2, c.height * 0.56);
          g.strokeText(ch, c.width / 2, c.height * 0.56);
          const a = g.getImageData(0, 0, c.width, c.height).data;
          return C_IN.map(([cx, cy]) => {
            let s = 0,
              m = 0;
            for (let y = 0; y < c.height; y++)
              for (let x = 0; x < c.width; x++)
                if ((x + 0.5 - cx * K) ** 2 + (y + 0.5 - cy * K) ** 2 <= (R_IN * K) ** 2) {
                  s += a[(y * c.width + x) * 4 + 3] / 255;
                  m++;
                }
            return s / m;
          });
        });
        const max = C_IN.map((_, i) => Math.max(...raw.map((v) => v[i])) || 1);
        SHAPES = raw.map((v) => v.map((x, i) => x / max[i]));
        shapeCache = new Map();
      }

      function nearestEdge(v) {
        let key = 0;
        for (let i = 0; i < 6; i++) key = (key << 5) | Math.min(31, Math.floor(v[i] * 32));
        let best = shapeCache.get(key);
        if (best !== undefined) return best;
        let bd = Infinity;
        for (let k = 1; k < SHAPES.length; k++) {
          const s = SHAPES[k];
          let d = 0;
          for (let i = 0; i < 6; i++) d += (v[i] - s[i]) ** 2;
          if (d < bd) {
            bd = d;
            best = k;
          }
        }
        shapeCache.set(key, best);
        return best;
      }

      /* ================================================================
   SOURCE — the picture: a canvas at 2 × 2 px samples, drawn in canvas
   px, read into coverage and colour per sample.
   ================================================================ */
      function makeSource(cols, rows) {
        const W = cols * SX,
          H = rows * SY,
          canvas = document.createElement("canvas");
        canvas.width = W;
        canvas.height = H;
        const ctx = canvas.getContext("2d", { willReadFrequently: true });
        ctx.setTransform(SX / CELL_W, 0, 0, SY / CELL_H, 0, 0);
        return {
          cols, rows, W, H, canvas, ctx,
          cov: new Float32Array(W * H),
          r: new Uint8ClampedArray(W * H),
          g: new Uint8ClampedArray(W * H),
          b: new Uint8ClampedArray(W * H),
        };
      }

      /* Clear a region of the canvas, in cells. */
      function clearSource(src, region) {
        const [c0, r0, c1, r1] = region;
        src.ctx.clearRect(c0 * CELL_W, r0 * CELL_H, (c1 - c0) * CELL_W, (r1 - r0) * CELL_H);
      }

      /* Read a region of the canvas, in cells, into the arrays. */
      function readSource(src, region) {
        const [c0, r0, c1, r1] = region;
        const x0 = c0 * SX, y0 = r0 * SY, w = (c1 - c0) * SX, h = (r1 - r0) * SY;
        if (w <= 0 || h <= 0) return;
        const d = src.ctx.getImageData(x0, y0, w, h).data;
        for (let y = 0; y < h; y++)
          for (let x = 0; x < w; x++) {
            const i = (y0 + y) * src.W + x0 + x,
              j = (y * w + x) * 4;
            src.cov[i] = d[j + 3] / 255;
            src.r[i] = d[j];
            src.g[i] = d[j + 1];
            src.b[i] = d[j + 2];
          }
      }

      /* ================================================================
   CONVERT — a region of the source into the grid. Cells the picture
   does not reach are left as they were.
   o: { wall: the running text, bg: the cells' background, full: the
   coverage from which a cell counts as inside, dir, glob: the contrast
   exponents }.
   ================================================================ */
      const hexOf = new Map();
      function convert(src, grid, region, o = {}) {
        if (!SHAPES) measureShapes();
        const [c0, r0, c1, r1] = region;
        const wall = o.wall || "TECH@TALKS@TUESDAY@",
          FULL = o.full ?? 0.8,
          E_DIR = o.dir ?? 2.2,
          E_GLOB = o.glob ?? 1.4,
          bg = o.bg ?? GROUND,
          W = src.W,
          H = src.H,
          A = src.cov;
        const v = new Float32Array(6),
          ex = new Float32Array(10);
        const avg = (list, sx, sy) => {
          let s = 0, m = 0;
          for (let k = 0; k < list.length; k++) {
            const x = sx + list[k][0], y = sy + list[k][1];
            if (x < 0 || y < 0 || x >= W || y >= H) {
              m++;
              continue;
            }
            s += A[y * W + x];
            m++;
          }
          return m ? s / m : 0;
        };
        for (let r = Math.max(0, r0); r < Math.min(src.rows, r1); r++)
          for (let c = Math.max(0, c0); c < Math.min(src.cols, c1); c++) {
            const sx = c * SX, sy = r * SY;
            let top = 0, bot = 1;
            for (let i = 0; i < 6; i++) {
              v[i] = avg(S_IN[i], sx, sy);
              if (v[i] > top) top = v[i];
              if (v[i] < bot) bot = v[i];
            }
            if (top < 0.12) continue;
            /* Colour: the covered samples' average. */
            let R = 0, G = 0, B = 0, wsum = 0;
            for (let y = sy; y < sy + SY; y++)
              for (let x = sx; x < sx + SX; x++) {
                const i = y * W + x, w = A[i];
                R += src.r[i] * w;
                G += src.g[i] * w;
                B += src.b[i] * w;
                wsum += w;
              }
            if (wsum <= 0) continue;
            /* Fill letters a little dimmer than edge lines, so the drawing
               reads first and the running text second. */
            const inside = bot >= FULL,
              k = inside ? (o.fillDim ?? 0.8) : 1;
            const q = (x) => Math.min(255, Math.round((x * k) / wsum / 17) * 17);
            const key = (q(R) << 16) | (q(G) << 8) | q(B);
            let hex = hexOf.get(key);
            if (!hex) hexOf.set(key, (hex = "#" + key.toString(16).padStart(6, "0")));
            let ch;
            if (inside) ch = wall[(c + r * 7 + (o.shift || 0)) % wall.length];
            else {
              for (let i = 0; i < 10; i++) ex[i] = avg(S_EX[i], sx, sy);
              for (let i = 0; i < 6; i++) {
                let m = v[i];
                for (const e of AFFECTS[i]) if (ex[e] > m) m = ex[e];
                if (m > 0) v[i] = Math.pow(v[i] / m, E_DIR) * m;
              }
              let m = 0;
              for (let i = 0; i < 6; i++) if (v[i] > m) m = v[i];
              if (m > 0) for (let i = 0; i < 6; i++) v[i] = Math.pow(v[i] / m, E_GLOB) * m;
              ch = EDGE_CHARS[nearestEdge(v)];
            }
            const gi = r * grid.cols + c;
            grid.ch[gi] = ch;
            grid.fg[gi] = colour(hex);
            grid.bg[gi] = bg;
          }
      }

      /* ================================================================
   STAMPS — art that does not move (titles, the big countdown), drawn
   and converted once into a list of cells, then laid into the grid each
   frame. draw(ctx) paints it in canvas px; region bounds it, in cells.
   ================================================================ */
      const stampCache = new Map();
      let stampSrc = null,
        stampGrid = null;
      function stamp(key, region, draw, o = {}) {
        let s = stampCache.get(key);
        if (s) return s;
        if (!stampSrc) {
          stampSrc = makeSource(COLS, ROWS);
          stampGrid = makeGrid(COLS, ROWS);
        }
        /* All of it, not just the region: a neighbour stamp's art left on
           the canvas would be read as part of this one. */
        clearSource(stampSrc, [0, 0, COLS, ROWS]);
        stampSrc.ctx.save();
        draw(stampSrc.ctx);
        stampSrc.ctx.restore();
        readSource(stampSrc, region);
        wipe(stampGrid, CLEAR);
        convert(stampSrc, stampGrid, region, { ...o, bg: CLEAR });
        s = [];
        const [c0, r0, c1, r1] = region;
        for (let r = r0; r < r1; r++)
          for (let c = c0; c < c1; c++) {
            const i = r * COLS + c;
            if (stampGrid.ch[i] !== " ") s.push(i, stampGrid.ch[i], stampGrid.fg[i]);
          }
        stampCache.set(key, s);
        return s;
      }

      /* Lay a stamp into the grid, on bg (default: what is there, or GROUND). */
      function layStamp(grid, s, bg) {
        for (let k = 0; k < s.length; k += 3) {
          const i = s[k];
          grid.ch[i] = s[k + 1];
          grid.fg[i] = s[k + 2];
          if (bg != null) grid.bg[i] = bg;
          else if (grid.bg[i] === CLEAR) grid.bg[i] = GROUND;
        }
      }

      /* Forget every stamp: after a font arrives. */
      function resetStamps() {
        stampCache.clear();
        measureShapes();
      }

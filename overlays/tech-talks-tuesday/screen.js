/* overlays/tech-talks-tuesday/screen.js -- the terminal screen
   Everything this overlay shows is one grid of 8 × 12 px cells drawn on a
   canvas, each holding one printable ASCII character in VT323, a foreground
   and a background colour. A cell with no background is transparent, and
   that is where the video shows. Characters are drawn bold, with a little
   phosphor glow, and every cell carries scanlines.

   A character may also be part of a bigger one, set across 2 × 2 cells,
   for labels that must read at a glance.

   Plain script, loaded before the page's config; nothing here runs until a
   page asks (docs/adr/0006). ascii.js turns pictures into these cells,
   flowers.js draws the garden, crt.js runs the switch. */

      /* 240 × 90 cells tile 1920 × 1080 exactly. */
      const CELL_W = 8,
        CELL_H = 12;
      const CLEAR = -1;

      const SCREEN_FONT = `"VT323", "Cascadia Mono", Consolas, monospace`;
      /* Set from the font once it has loaded, so one character fills a
         cell's width. */
      let SCREEN_FONT_PX = 15;
      function fitFont() {
        const c = document.createElement("canvas").getContext("2d");
        c.font = `100px ${SCREEN_FONT}`;
        const adv = c.measureText("M").width / 100;
        SCREEN_FONT_PX = Math.min(17, (CELL_W * 1.02) / adv);
      }

      /* Colours are kept as small numbers: an index into COLOURS. */
      const COLOURS = [],
        colourIds = new Map();
      function colour(hex) {
        let i = colourIds.get(hex);
        if (i === undefined) {
          i = COLOURS.push(hex) - 1;
          colourIds.set(hex, i);
        }
        return i;
      }

      /* ================================================================
   THE GRID — what the screen should show, diffed against the canvas by
   makeScreen().
   ================================================================ */
      function makeGrid(cols, rows) {
        const n = cols * rows;
        return {
          cols,
          rows,
          ch: new Array(n).fill(" "),
          fg: new Int16Array(n),
          bg: new Int16Array(n).fill(CLEAR),
        };
      }

      function wipe(g, bg) {
        g.ch.fill(" ");
        g.fg.fill(0);
        g.bg.fill(bg);
      }

      /* bg omitted keeps the cell's background, except that a character
         never lands on a transparent cell: over video it would be
         unreadable, so it gets the page's GROUND. */
      function putCell(g, c, r, ch, fg, bg) {
        if (c < 0 || r < 0 || c >= g.cols || r >= g.rows) return;
        const i = r * g.cols + c;
        g.ch[i] = ch;
        if (fg != null) g.fg[i] = fg;
        if (bg != null) g.bg[i] = bg;
        else if (g.bg[i] === CLEAR) g.bg[i] = GROUND;
      }

      /* size 1: a character a cell. size 2: across 2 × 2 cells. Returns the
         cells written across. */
      function putText(g, c, r, s, fg, bg, size = 1) {
        let x = c;
        for (const ch of s) {
          if (size === 1) putCell(g, x, r, ch, fg, bg);
          else
            for (let j = 0; j < 2; j++)
              for (let i = 0; i < 2; i++)
                putCell(g, x + i, r + j, ch === " " ? " " : `\u0002${i}${j}${ch}`, fg, bg);
          x += size;
        }
        return x - c;
      }

      function fillCells(g, c, r, w, h, ch, fg, bg) {
        for (let y = r; y < r + h; y++)
          for (let x = c; x < c + w; x++) putCell(g, x, y, ch, fg, bg);
      }

      /* A transparent rectangle: a window onto whatever OBS has behind. */
      function clearCells(g, c, r, w, h) {
        for (let y = Math.max(0, r); y < Math.min(g.rows, r + h); y++)
          for (let x = Math.max(0, c); x < Math.min(g.cols, c + w); x++) {
            const i = y * g.cols + x;
            g.ch[i] = " ";
            g.bg[i] = CLEAR;
          }
      }

      /* ================================================================
   THE SCREEN — draws a grid onto a canvas, only the cells that changed
   since the last draw. Every distinct cell (character, colours) is
   painted once into an atlas and copied from there.
   fx: { glow: px of phosphor glow, scan: scanline darkness 0..1 }.
   ================================================================ */
      function makeScreen(canvas, cols, rows, fx = {}) {
        const dpr = Math.max(1, Math.round(window.devicePixelRatio || 1));
        const W = CELL_W * dpr,
          H = CELL_H * dpr,
          n = cols * rows;
        canvas.width = cols * W;
        canvas.height = rows * H;
        canvas.style.width = cols * CELL_W + "px";
        canvas.style.height = rows * CELL_H + "px";
        const ctx = canvas.getContext("2d");

        const PER_ROW = Math.floor(2048 / W),
          PER_COL = Math.floor(2048 / H),
          PER_SHEET = PER_ROW * PER_COL;
        let sheets, used, atlas;
        const seenCh = new Array(n),
          seenFg = new Int16Array(n),
          seenBg = new Int16Array(n);

        /* Forget every painted cell: after a font arrives. */
        function reset() {
          sheets = [];
          used = 0;
          atlas = new Map();
          seenCh.fill(null);
        }
        reset();

        function paint(c, x, y, ch, fg, bg) {
          c.save();
          c.beginPath();
          c.rect(x, y, W, H);
          c.clip();
          c.clearRect(x, y, W, H);
          if (bg !== CLEAR) {
            c.fillStyle = COLOURS[bg];
            c.fillRect(x, y, W, H);
          }
          if (ch !== " ") {
            let s = ch,
              px = SCREEN_FONT_PX,
              cx = x + W / 2,
              cy = y + H * 0.56;
            /* Part (i, j) of a character set across 2 × 2 cells. */
            if (ch[0] === "\u0002") {
              s = ch.slice(3);
              px *= 2;
              cx = x - +ch[1] * W + W;
              cy = y - +ch[2] * H + H * 1.12;
            }
            c.font = `${px * dpr}px ${SCREEN_FONT}`;
            c.textAlign = "center";
            c.textBaseline = "middle";
            c.fillStyle = c.strokeStyle = COLOURS[fg];
            if (fx.glow) {
              c.shadowColor = COLOURS[fg];
              c.shadowBlur = fx.glow * dpr;
            }
            c.fillText(s, cx, cy);
            /* VT323 is drawn one pixel thin; a hair of stroke makes it the
               bold terminal face. */
            c.lineWidth = 0.55 * dpr * (px / SCREEN_FONT_PX);
            c.strokeText(s, cx, cy);
            c.shadowBlur = 0;
          }
          if (fx.scan) {
            c.globalCompositeOperation = "source-atop";
            c.fillStyle = `rgba(0,0,0,${fx.scan})`;
            for (let yy = 2 * dpr; yy < H; yy += 3 * dpr) c.fillRect(x, y + yy, W, dpr);
          }
          c.restore();
        }

        function glyph(ch, fg, bg) {
          const key = ch + "|" + fg + "|" + bg;
          let e = atlas.get(key);
          if (e) return e;
          const s = Math.floor(used / PER_SHEET),
            k = used++ % PER_SHEET;
          if (!sheets[s]) {
            const sh = document.createElement("canvas");
            sh.width = PER_ROW * W;
            sh.height = PER_COL * H;
            sheets[s] = sh;
          }
          const x = (k % PER_ROW) * W,
            y = Math.floor(k / PER_ROW) * H;
          paint(sheets[s].getContext("2d"), x, y, ch, fg, bg);
          e = { img: sheets[s], x, y };
          atlas.set(key, e);
          return e;
        }

        /* Returns whether anything changed. */
        function draw(g) {
          let changed = false;
          for (let i = 0; i < n; i++) {
            const ch = g.ch[i],
              bg = g.bg[i],
              fg = ch === " " ? 0 : g.fg[i];
            if (seenCh[i] === ch && seenBg[i] === bg && seenFg[i] === fg) continue;
            changed = true;
            seenCh[i] = ch;
            seenFg[i] = fg;
            seenBg[i] = bg;
            const x = (i % cols) * W,
              y = Math.floor(i / cols) * H;
            if (bg === CLEAR) ctx.clearRect(x, y, W, H);
            if (bg === CLEAR && ch === " ") continue;
            const e = glyph(ch, fg, bg);
            ctx.drawImage(e.img, e.x, e.y, W, H, x, y, W, H);
          }
          return changed;
        }

        return { draw, reset };
      }

      /* A small seeded generator (mulberry32), so a scene's random art is
         the same on every load. */
      function rng(seed) {
        let a = seed >>> 0;
        return () => {
          a = (a + 0x6d2b79f5) >>> 0;
          let t = a;
          t = Math.imul(t ^ (t >>> 15), t | 1);
          t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
          return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
        };
      }

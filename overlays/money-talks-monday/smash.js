/* overlays/money-talks-monday/smash.js -- the smash, this overlay's transition
   Loaded in place of core/camera-pan.js (core/README.md, "Another
   transition"; docs/adr/0013). Plain script, not a module: the page loads as
   file:// and Chromium refuses modules there (docs/adr/0006). Reads the
   page's NOTE, NOTE_X, NOTE_W, NOTE_H, BLEED, COIN, WINDOW, FRAMES, SOUND and
   frameArt(), and art.js's coinFace(). Both pages run it: the canvas is
   whatever CANVAS_W x CANVAS_H the page says.

   The note's two halves are opaque art over still video. A switch rewinds
   their white borders, slams them shut into the whole note, moves the holes
   and the OBS sources while nothing can be seen, spins the coin, and opens
   into the next scene's frame. The video never moves during a switch. */

      let current = null; /* the panel the holes show; hud.js reads it */

      /* Every panel is exactly the canvas, so resting on one is a plain
         translate. The page never travels: it jumps while the note is shut. */
      function transformFor(t) {
        const p = PANELS.find((v) => v.id === Number(t));
        return `translate(${-(p.x + PANEL_BORDER)}px,${-(p.y + PANEL_BORDER)}px)`;
      }

      function goTo(t, opts) {
        SMASH.goTo(String(t), opts || {});
      }

      const SMASH = (() => {
        const MID = CANVAS_H / 2,
          HALF_W = CANVAS_W + 2 * BLEED; /* each half's width: the canvas plus bleed */
        const lerp = (a, b, k) => a + (b - a) * k;
        const ease = {
          inOut: (k) =>
            k < 0.5 ? 4 * k * k * k : 1 - Math.pow(-2 * k + 2, 3) / 2,
          in: (k) => k * k * k,
          out: (k) => 1 - Math.pow(1 - k, 3),
          /* A small overshoot: 1.25% past rest, which every hole has room
             for under the frame's edges. */
          back: (k) => 1 + 1.6 * Math.pow(k - 1, 3) + 0.6 * Math.pow(k - 1, 2),
        };
        const keyOf = (t) => PANELS.find((p) => String(p.id) === t).key;
        const isOpen = (k) => !!(FRAMES[k] && FRAMES[k].open);

        /* ---- resting geometry of each open frame ---------------------- */
        const GEO = {};
        Object.entries(FRAMES).forEach(([k, f]) => {
          if (!f.open) return;
          const edge = f.footer.slice(f.artFrom || 0);
          GEO[k] = {
            yL: f.header[0],
            yR: f.header[1],
            Mh: Math.max(...f.header) /* the header's cut, at rest */,
            Mf: Math.min(...edge.map((p) => p[1])) /* the footer's */,
            edge,
            line: f.footer,
          };
        });

        /* Each half's height: enough to cover its side shut, to reach the
           far canvas edge from every resting cut (the vertical CHAT's
           footer rests above the middle), and BLEED more for the shake. */
        const HH =
          Math.max(
            NOTE_H / 2,
            MID,
            ...Object.values(GEO).map((g) => g.Mh),
            ...Object.values(GEO).map((g) => CANVAS_H - g.Mf),
          ) + BLEED;

        /* Canvas x to a half's own x: the halves overhang by BLEED, and a
           point on a canvas edge goes on out to the half's edge. */
        const hx = (x) => (x <= 0 ? 0 : x >= CANVAS_W ? HALF_W : x + BLEED);
        const poly = (pts) =>
          `polygon(${pts.map(([x, y]) => `${x.toFixed(1)}px ${y.toFixed(1)}px`).join(",")})`;

        /* c: 0 at rest, 1 shut. The cut straightens as the halves travel. */
        function headerClip(g, c) {
          const a = HH - (g.Mh - g.yL),
            b = HH - (g.Mh - g.yR);
          return poly([
            [0, 0],
            [HALF_W, 0],
            [HALF_W, lerp(b, HH, c)],
            [0, lerp(a, HH, c)],
          ]);
        }
        /* The footer's art edge, with the cam notch closing as it shuts. */
        function footerClip(g, c) {
          const e = g.edge,
            x0 = lerp(hx(e[0][0]), 0, c),
            pts = [[x0, HH]];
          e.forEach(([x, y], i) =>
            pts.push([i === 0 ? x0 : hx(x), lerp(y - g.Mf, 0, c)]),
          );
          const last = e[e.length - 1];
          if (last[0] < CANVAS_W) pts.push([HALF_W, lerp(last[1] - g.Mf, 0, c)]);
          pts.push([HALF_W, HH]);
          return poly(pts);
        }

        /* ---- build ------------------------------------------------------ */
        const frame = document.getElementById("frame");
        const add = (cls, parent, html) => {
          const d = document.createElement("div");
          d.className = cls;
          if (html) d.innerHTML = html;
          parent.appendChild(d);
          return d;
        };
        /* The note as drawn when shut, as a layer inside `el`, whose
           top-left is at (left, top) on the canvas. The drawn box starts at
           canvas x NOTE_X and is centred vertically; a page may make it
           wider than the canvas and shift it, so the rosette is centred. A
           turned file is laid in sideways and rotated into that box. */
        function paintNote(el, left, top) {
          const n = document.createElement("div");
          n.className = "note";
          const bx = NOTE_X - left,
            by = MID - NOTE_H / 2 - top;
          if (NOTE.rotate)
            Object.assign(n.style, {
              left: bx + NOTE_W / 2 - NOTE_H / 2 + "px",
              top: by + NOTE_H / 2 - NOTE_W / 2 + "px",
              width: NOTE_H + "px",
              height: NOTE_W + "px",
              transform: `rotate(${NOTE.rotate}deg)`,
            });
          else
            Object.assign(n.style, {
              left: bx + "px",
              top: by + "px",
              width: NOTE_W + "px",
              height: NOTE_H + "px",
            });
          n.style.backgroundImage = `url("${NOTE.src}")`;
          el.appendChild(n);
        }

        const art = frameArt();

        /* Decor: per scene, art that stays put while it is on air — a strip
           of the shut note and white rules. Under the halves, so they close
           over it; swapped only while the note is shut. The strip's shape is
           a polygon (`poly`), or an SVG path filled evenodd (`path`), which
           can cut a window in it. */
        const decor = {};
        Object.entries(FRAMES).forEach(([k, f]) => {
          const d = f.decor,
            html = (art.decor || {})[k];
          if (!d && !html) return;
          const box = add("decor", frame);
          if (d && (d.poly || d.path)) {
            const strip = add("strip", box);
            strip.style.clipPath = d.path ? `path(evenodd, "${d.path}")` : poly(d.poly);
            paintNote(strip, 0, 0);
          }
          if (d && d.lines)
            box.insertAdjacentHTML(
              "beforeend",
              `<svg class="rules" width="${CANVAS_W}" height="${CANVAS_H}">` +
                d.lines
                  .map(([x1, y1, x2, y2]) => `<line x1="${x1}" y1="${y1}" x2="${x2}" y2="${y2}"/>`)
                  .join("") +
                `</svg>`,
            );
          if (html) box.insertAdjacentHTML("beforeend", html);
          decor[k] = box;
        });

        const half = (cls, top) => {
          const h = add(`half ${cls}`, frame);
          Object.assign(h.style, {
            left: -BLEED + "px",
            top: top + "px",
            width: HALF_W + "px",
            height: HH + "px",
          });
          paintNote(h, -BLEED, top);
          return h;
        };
        const header = half("header", MID - HH),
          footer = half("footer", MID);

        /* Groups ride their half. `top` puts canvas y=0 where it falls in the
           half: at rest for an open scene's art, shut for a closed one's. */
        const group = (parent, html, top) => {
          const d = add("grp", parent, html);
          d.style.left = BLEED + "px";
          d.style.top = top + "px";
          return d;
        };
        const groups = {};
        Object.keys(GEO).forEach((k) => {
          groups[k] = {
            h: group(header, art.header[k], HH - GEO[k].Mh),
            f: group(footer, art.footer[k], -GEO[k].Mf),
          };
        });
        const closedH = group(header, art.header.closed, HH - MID),
          closedF = group(footer, art.footer.closed, -MID);

        /* White borders, drawn at rest. pathLength=1 makes the rewind a
           single dash offset; the faint track under it is the YouTube bar. */
        const lines = add("lines", frame);
        lines.innerHTML =
          `<svg width="${CANVAS_W}" height="${CANVAS_H}">` +
          Object.entries(GEO)
            .map(
              ([k, g]) =>
                `<g data-k="${k}">` +
                [`0,${g.yL} ${CANVAS_W},${g.yR}`, g.line.map((p) => p.join(",")).join(" ")]
                  .map(
                    (pts) =>
                      `<polyline class="track" points="${pts}" pathLength="1"/>` +
                      `<polyline class="line" points="${pts}" pathLength="1" stroke-dasharray="1 1"/>` +
                      `<circle class="knob" r="11"/>`,
                  )
                  .join("") +
                `</g>`,
            )
            .join("") +
          `</svg>`;
        const lineSets = {};
        Object.entries(GEO).forEach(([k, g]) => {
          const el = lines.querySelector(`g[data-k="${k}"]`);
          lineSets[k] = {
            el,
            parts: [
              [
                [0, g.yL],
                [CANVAS_W, g.yR],
              ],
              g.line,
            ].map((pts, i) => ({
              pts,
              line: el.querySelectorAll(".line")[i],
              track: el.querySelectorAll(".track")[i],
              knob: el.querySelectorAll(".knob")[i],
            })),
          };
        });

        const seam = add("seam", frame);

        const winFrame = add("window-frame", frame);
        Object.assign(winFrame.style, {
          left: COIN.x + "px",
          top: COIN.y + "px",
          width: WINDOW.w + 20 + "px",
          height: WINDOW.h + 20 + "px",
        });

        /* The coin, and two faint copies trailing it while it spins: motion
           blur is too dear in OBS's browser, ghosts are not. */
        const stage = add("coin-stage", frame);
        Object.assign(stage.style, {
          left: COIN.x + "px",
          top: COIN.y + "px",
          width: 2 * COIN.r + "px",
          height: 2 * COIN.r + "px",
        });
        const coins = [2, 1, 0].map((n) => {
          const pos = add("coin-pos", stage);
          pos.innerHTML =
            `<div class="coin-wob"><div class="coin">` +
            coinFace(n, true) +
            `<div class="edge"></div>` +
            coinFace(n, false) +
            `</div></div>`;
          if (n) pos.style.opacity = 0;
          return {
            pos,
            wob: pos.firstChild,
            coin: pos.querySelector(".coin"),
            n,
          };
        });
        const main = coins[2],
          ghosts = coins.slice(0, 2);
        const shine = main.coin.querySelector(".shine");

        /* ---- drawing ---------------------------------------------------- */
        let shownKey = null /* the frame drawn */,
          cAmt = 1 /* 0 rest .. 1 shut */,
          lAmt = 0 /* white borders drawn, 0..1 */,
          ovAmt = 0 /* the open scene's art on the halves */,
          trackOn = false,
          winK = 0 /* END's window, 0 shut .. 1 open */,
          coinShown = true;

        const pointAt = (pts, f) => {
          const seg = pts.slice(1).map((p, i) => Math.hypot(p[0] - pts[i][0], p[1] - pts[i][1]));
          let d = f * seg.reduce((a, b) => a + b, 0);
          for (let i = 0; i < seg.length; i++) {
            if (d <= seg[i] || i === seg.length - 1) {
              const k = seg[i] ? Math.min(1, d / seg[i]) : 0;
              return [lerp(pts[i][0], pts[i + 1][0], k), lerp(pts[i][1], pts[i + 1][1], k)];
            }
            d -= seg[i];
          }
        };

        function render() {
          const g = GEO[shownKey];
          Object.entries(lineSets).forEach(([k, s]) => s.el.classList.toggle("on", k === shownKey));
          Object.entries(groups).forEach(([k, gr]) => {
            const on = k === shownKey;
            gr.h.style.display = gr.f.style.display = on ? "" : "none";
            if (on) gr.h.style.opacity = gr.f.style.opacity = ovAmt;
          });
          /* A closed scene's words only while the note is shut, so a fading
             one can never ride a half out into the open frame. */
          closedH.style.display = closedF.style.display = !g || cAmt >= 1 ? "" : "none";
          if (!g) {
            header.style.transform = footer.style.transform = "none";
            header.style.clipPath = footer.style.clipPath = "none";
            return;
          }
          header.style.transform = `translateY(${lerp(g.Mh - MID, 0, cAmt)}px)`;
          footer.style.transform = `translateY(${lerp(g.Mf - MID, 0, cAmt)}px)`;
          header.style.clipPath = headerClip(g, cAmt);
          footer.style.clipPath = footerClip(g, cAmt);
          lineSets[shownKey].parts.forEach((p) => {
            p.line.setAttribute("stroke-dashoffset", (1 - lAmt).toFixed(4));
            p.track.style.opacity = trackOn ? 1 : 0;
            p.knob.style.opacity = trackOn ? 1 : 0;
            const [x, y] = pointAt(p.pts, lAmt);
            p.knob.setAttribute("cx", x.toFixed(1));
            p.knob.setAttribute("cy", y.toFixed(1));
          });
        }

        /* END's window: a rounded 16:9 hole in the whole frame, grown from
           the rosette's centre. One evenodd path, as core's masks are. */
        function setWindow(k) {
          winK = Math.max(0, Math.min(1, k));
          let m = "none";
          if (winK > 0.002) {
            const w = WINDOW.w * winK,
              h = WINDOW.h * winK,
              r = WINDOW.r * winK,
              x = COIN.x - w / 2,
              y = COIN.y - h / 2;
            const d =
              `M0 0H${CANVAS_W}V${CANVAS_H}H0Z` +
              `M${x + r} ${y}H${x + w - r}A${r} ${r} 0 0 1 ${x + w} ${y + r}` +
              `V${y + h - r}A${r} ${r} 0 0 1 ${x + w - r} ${y + h}` +
              `H${x + r}A${r} ${r} 0 0 1 ${x} ${y + h - r}` +
              `V${y + r}A${r} ${r} 0 0 1 ${x + r} ${y}Z`;
            const svg =
              `<svg xmlns="http://www.w3.org/2000/svg" width="${CANVAS_W}" height="${CANVAS_H}">` +
              `<path fill-rule="evenodd" d="${d}"/></svg>`;
            m = `url("data:image/svg+xml;utf8,${encodeURIComponent(svg)}")`;
          }
          Object.assign(frame.style, {
            maskImage: m,
            webkitMaskImage: m,
            maskSize: `${CANVAS_W}px ${CANVAS_H}px`,
            webkitMaskSize: `${CANVAS_W}px ${CANVAS_H}px`,
            maskRepeat: "no-repeat",
            webkitMaskRepeat: "no-repeat",
          });
          winFrame.style.opacity = Math.min(1, winK * 3);
          winFrame.style.transform = `translate(-50%,-50%) scale(${winK})`;
        }

        const coinSet = (scale, opacity) => {
          stage.style.transform = `translate(-50%,-50%) scale(${scale})`;
          stage.style.opacity = opacity;
        };
        const coinTurn = (a, g1, g2) => {
          main.coin.style.transform = `rotateY(${a}deg)`;
          ghosts[1].coin.style.transform = `rotateY(${g1}deg)`;
          ghosts[0].coin.style.transform = `rotateY(${g2}deg)`;
        };
        const ghostsOn = (on) => {
          ghosts[1].pos.style.opacity = on ? 0.22 : 0;
          ghosts[0].pos.style.opacity = on ? 0.1 : 0;
        };
        const coinIdle = (on) => main.wob.classList.toggle("idle", on);
        const restart = (el, cls) => {
          el.classList.remove(cls);
          void el.offsetWidth;
          el.classList.add(cls);
        };

        /* Which closed scene's words are on the note, if any. */
        function closedText(k) {
          closedH.querySelectorAll(".cart").forEach((c) => c.classList.toggle("on", c.dataset.k === k));
          closedF.querySelector(".serials").classList.toggle("on", !!k);
        }

        /* ---- sound: synthesised, so there is no file to lose. It plays
           through Overlay's audio, into the stream mix; SOUND false (the vertical
           page) or ?sfx=0 silences them. -- */
        const SFX = (() => {
          const off = !SOUND || params.get("sfx") === "0";
          let ac = null;
          const ctx = () => {
            if (off) return null;
            try {
              ac = ac || new AudioContext();
            } catch (_) {
              return null;
            }
            return ac.state === "running" || ac.state === "suspended" ? ac : null;
          };
          const out = (a, vol) => {
            const g = a.createGain();
            g.gain.value = vol;
            g.connect(a.destination);
            return g;
          };
          const noise = (a, secs) => {
            const b = a.createBuffer(1, Math.ceil(a.sampleRate * secs), a.sampleRate),
              d = b.getChannelData(0);
            for (let i = 0; i < d.length; i++) d[i] = Math.random() * 2 - 1;
            const s = a.createBufferSource();
            s.buffer = b;
            return s;
          };
          return {
            whoosh() {
              const a = ctx();
              if (!a) return;
              const t = a.currentTime,
                s = noise(a, 0.3),
                f = a.createBiquadFilter(),
                g = out(a, 0);
              f.type = "bandpass";
              f.Q.value = 1.2;
              f.frequency.setValueAtTime(500, t);
              f.frequency.exponentialRampToValueAtTime(2600, t + 0.22);
              g.gain.setValueAtTime(0, t);
              g.gain.linearRampToValueAtTime(0.32, t + 0.16);
              g.gain.exponentialRampToValueAtTime(0.001, t + 0.28);
              s.connect(f).connect(g);
              s.start(t);
            },
            thud() {
              const a = ctx();
              if (!a) return;
              const t = a.currentTime,
                o = a.createOscillator(),
                g = out(a, 0);
              o.frequency.setValueAtTime(110, t);
              o.frequency.exponentialRampToValueAtTime(42, t + 0.25);
              g.gain.setValueAtTime(0.55, t);
              g.gain.exponentialRampToValueAtTime(0.001, t + 0.32);
              o.connect(g);
              o.start(t);
              o.stop(t + 0.34);
            },
            ting() {
              const a = ctx();
              if (!a) return;
              const t = a.currentTime;
              [1760, 2637, 3520].forEach((hz, i) => {
                const o = a.createOscillator(),
                  g = out(a, 0);
                o.frequency.value = hz;
                g.gain.setValueAtTime(0.14 / (i + 1), t);
                g.gain.exponentialRampToValueAtTime(0.0008, t + 0.7);
                o.connect(g);
                o.start(t);
                o.stop(t + 0.72);
              });
            },
          };
        })();

        /* ---- timing ------------------------------------------------------
           gen is the run a tween belongs to. A press that restarts the run
           bumps it, and every tween of the old run stops where it is. */
        let gen = 0,
          running = false,
          phase = "idle",
          target = null;

        const tween = (ms, fn, g) =>
          new Promise((done) => {
            if (ms <= 0) {
              fn(1);
              return done(true);
            }
            const t0 = performance.now();
            const step = (now) => {
              if (g !== gen) return done(false);
              /* A frame's timestamp can predate t0. */
              const k = Math.max(0, Math.min(1, (now - t0) / ms));
              fn(k);
              if (k < 1) requestAnimationFrame(step);
              else done(true);
            };
            requestAnimationFrame(step);
          });
        const wait = (ms, g) =>
          new Promise((done) => setTimeout(() => done(g === gen), ms));

        /* The holes and the OBS sources move only here, and only while the
           note is shut. Both the page and the sources land in one frame. */
        function switchTo(t) {
          const k = keyOf(t);
          closedText(isOpen(k) ? null : k);
          Object.entries(decor).forEach(([dk, box]) => box.classList.toggle("on", dk === k));
          if (t === current) return;
          current = t;
          pageEl.style.transform = transformFor(t);
          applyPunch(Number(t));
          Object.entries(panelEls).forEach(([id, el]) => el.classList.toggle("is-live", id === t));
          startTracking(160);
        }

        function impact() {
          restart(frame, "shake");
          restart(seam, "flash");
          SFX.thud();
        }

        async function spinCoin(g) {
          coinIdle(false);
          if (!coinShown) {
            if (!(await wait(80, g))) return false;
            const ok = await tween(160, (k) => coinSet(lerp(1.35, 1, ease.out(k)), k), g);
            if (!ok) return false;
            coinShown = true;
          }
          ghostsOn(true);
          const turn = (k) => 720 * ease.out(Math.min(1, Math.max(0, k)));
          const ok = await tween(520, (k) => coinTurn(turn(k), turn(k - 0.05), turn(k - 0.1)), g);
          ghostsOn(false);
          coinTurn(0, 0, 0);
          if (!ok) return false;
          SFX.ting();
          restart(shine, "go");
          return true;
        }

        const hideCoin = (g) =>
          tween(140, (k) => coinSet(lerp(1, 0.6, ease.in(k)), 1 - k), g).then((ok) => {
            if (ok) coinShown = false;
            return ok;
          });

        const iris = (to, ms, g) => {
          const k0 = winK;
          return tween(ms, (k) => setWindow(lerp(k0, to, ease.inOut(k))), g);
        };

        async function run() {
          const g = ++gen;
          running = true;
          phase = "closing";
          /* The note is at full colour only while it moves; at rest it is
             muted so the plates and handles read over it (money.css). */
          frame.classList.add("loud");

          /* Rewind, then slam: only from an open frame, and only as far as
             it still has to go — a press mid-open closes from where it is. */
          if (isOpen(shownKey)) {
            const l0 = lAmt,
              o0 = ovAmt;
            trackOn = true;
            let ok = await tween(260 * l0, (k) => {
              const e = ease.inOut(k);
              lAmt = l0 * (1 - e);
              ovAmt = o0 * (1 - e);
              render();
            }, g);
            trackOn = false;
            render();
            if (!ok) return;
            const c0 = cAmt;
            if (c0 < 1) {
              SFX.whoosh();
              ok = await tween(200 * (1 - c0), (k) => {
                cAmt = lerp(c0, 1, ease.in(k));
                render();
              }, g);
              if (!ok) return;
              impact();
            }
          } else if (winK > 0) {
            if (!(await iris(0, 200 * winK, g))) return;
          }

          /* Shut. Everything that changes, changes now. */
          phase = "closed";
          switchTo(target);
          if (!(await spinCoin(g))) return;
          switchTo(target); /* a press during the spin */

          const k = keyOf(target);
          phase = "opening";
          if (isOpen(k)) {
            if (!(await wait(60, g))) return;
            if (!(await hideCoin(g))) return;
            shownKey = k;
            lAmt = 0;
            ovAmt = 0;
            render();
            const opened = tween(360, (q) => {
              cAmt = 1 - ease.back(q);
              render();
            }, g);
            const drawn = wait(250, g).then((ok) => {
              if (!ok) return false;
              /* Wherever this scene carries its socials, tick them in. */
              [groups[k].h, groups[k].f, decor[k]].forEach((el) =>
                el && el.querySelectorAll(".soc").forEach((s) => restart(s, "tick")),
              );
              trackOn = true;
              return tween(300, (q) => {
                lAmt = ease.out(q);
                ovAmt = Math.min(1, q * 2);
                render();
              }, g);
            });
            const done = await Promise.all([opened, drawn]);
            trackOn = false;
            if (g !== gen) return;
            cAmt = 0;
            lAmt = ovAmt = 1;
            render();
            if (!done.every(Boolean)) return;
          } else {
            shownKey = k;
            render();
            if (k === "end") {
              const ok = await Promise.all([hideCoin(g), iris(1, 380, g)]);
              if (!ok.every(Boolean)) return;
            } else coinIdle(k === "start");
          }
          frame.classList.remove("loud");
          running = false;
          phase = "idle";
        }

        /* Straight to a scene's rest, no sting: the first scene OBS reports,
           so the overlay does not play a switch on OBS startup. */
        function settle(t) {
          gen++;
          running = false;
          phase = "idle";
          frame.classList.remove("loud");
          switchTo(t);
          const k = keyOf(t),
            open = isOpen(k);
          shownKey = k;
          cAmt = open ? 0 : 1;
          lAmt = ovAmt = open ? 1 : 0;
          trackOn = false;
          coinShown = !open && k !== "end";
          coinSet(1, coinShown ? 1 : 0);
          coinTurn(0, 0, 0);
          ghostsOn(false);
          coinIdle(k === "start");
          setWindow(k === "end" ? 1 : 0);
          render();
        }

        /* The newest press wins and presses never queue (docs/adr/0013).
           Closing or shut: it opens to the newest scene. Opening: it closes
           again from where it is. */
        function goTo(t, { instant = false } = {}) {
          if (!PANELS.some((p) => String(p.id) === t)) return;
          target = t;
          if (instant || shownKey === null) return settle(t);
          if (!running) {
            if (t !== current) run();
            return;
          }
          if (phase === "opening") run();
        }

        /* Before OBS names a scene the note is shut, coin up: everything
           covered, nothing punched. */
        coinSet(1, 1);
        render();

        return { goTo, state: () => ({ shownKey, cAmt, lAmt, phase, current, target }) };
      })();

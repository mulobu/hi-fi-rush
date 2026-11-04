/* overlays/tech-talks-tuesday/crt.js -- the switch: an old CRT turning off and on
   Loaded in place of core/camera-pan.js (core/README.md, "Another
   transition"; docs/adr/0018). Plain script, not a module: the page loads
   as file:// and Chromium refuses modules there (docs/adr/0006). Reads the
   page's COLS, ROWS, SCENES and SOUND; draws with screen.js.

   Off: the picture squashes to a bright line across the middle, the line
   shrinks to a dot, the dot fades. The holes and the OBS sources move now,
   in the dark. On: a dot, a line, and the line opens into the next scene.
   The video never moves: the glass closing in from top and bottom covers
   it, and the overlay's own canvas is squashed with the picture. */

      let current = null; /* the panel the holes show; hud.js reads it */

      /* Every panel is exactly the canvas, so resting on one is a plain
         translate. The page never travels: it jumps in the dark. */
      function transformFor(t) {
        const p = PANELS.find((v) => v.id === Number(t));
        return `translate(${-(p.x + PANEL_BORDER)}px,${-(p.y + PANEL_BORDER)}px)`;
      }

      function goTo(t, opts) {
        CRT.goTo(String(t), opts || {});
      }

      const CRT = (() => {
        const canvas = document.getElementById("screen"),
          bloom = document.getElementById("bloom"),
          glass = document.getElementById("crt"),
          top = glass.querySelector(".top"),
          bot = glass.querySelector(".bot"),
          beam = glass.querySelector(".beam");
        const screen = makeScreen(canvas, COLS, ROWS, THEME.fx);
        const G = makeGrid(COLS, ROWS);
        const keyOf = (t) => PANELS.find((p) => String(p.id) === t).key;

        /* Bloom: a half-size copy of the screen, blurred by CSS and laid
           over it with `screen`, so bright characters glow past their cells. */
        bloom.width = (COLS * CELL_W) / 2;
        bloom.height = (ROWS * CELL_H) / 2;
        const bctx = bloom.getContext("2d");
        bloom.style.opacity = THEME.bloom;
        if (!THEME.bloom) bloom.style.display = "none";

        /* ms from the press. */
        const T = { squash: 230, shrink: 130, fade: 120, dark: 90, dotIn: 80, grow: 120, open: 260 };
        const at = {};
        let acc = 0;
        ["squash", "shrink", "fade", "dark", "dotIn", "grow", "open"].forEach((k) => {
          at[k] = acc;
          acc += T[k];
        });
        T.cut = at.dark;
        T.end = acc;
        const K_MIN = 3 / (ROWS * CELL_H);

        const easeIn = (k) => k * k * k,
          easeOut = (k) => 1 - Math.pow(1 - k, 3),
          /* A little overshoot as the picture opens, as a tube's sweep did. */
          easeBack = (k) => 1 + 2.2 * Math.pow(k - 1, 3) + 1.2 * Math.pow(k - 1, 2);
        const clamp = (k) => Math.max(0, Math.min(1, k));

        /* ---- sound: synthesised, through Overlay's audio. ?sfx=0 or SOUND
           false silences it. ---- */
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
          const gain = (a, v) => {
            const g = a.createGain();
            g.gain.value = v;
            g.connect(a.destination);
            return g;
          };
          const crackle = (a, t, len, vol) => {
            const b = a.createBuffer(1, Math.ceil(a.sampleRate * len), a.sampleRate),
              d = b.getChannelData(0);
            for (let i = 0; i < d.length; i++) d[i] = (Math.random() < 0.02 ? Math.random() * 2 - 1 : 0) * (1 - i / d.length);
            const s = a.createBufferSource();
            s.buffer = b;
            s.connect(gain(a, vol));
            s.start(t);
          };
          return {
            /* The tube going off: a falling bloop and a little static. */
            off() {
              const a = ctx();
              if (!a) return;
              const t = a.currentTime,
                o = a.createOscillator(),
                g = gain(a, 0);
              o.frequency.setValueAtTime(1100, t);
              o.frequency.exponentialRampToValueAtTime(55, t + 0.32);
              g.gain.setValueAtTime(0.12, t);
              g.gain.exponentialRampToValueAtTime(0.001, t + 0.36);
              o.connect(g);
              o.start(t);
              o.stop(t + 0.38);
              crackle(a, t, 0.4, 0.25);
            },
            /* The tube coming on: a soft thump and a rising hum. */
            on() {
              const a = ctx();
              if (!a) return;
              const t = a.currentTime,
                o = a.createOscillator(),
                g = gain(a, 0);
              o.type = "triangle";
              o.frequency.setValueAtTime(60, t);
              o.frequency.exponentialRampToValueAtTime(520, t + 0.25);
              g.gain.setValueAtTime(0.0, t);
              g.gain.linearRampToValueAtTime(0.1, t + 0.05);
              g.gain.exponentialRampToValueAtTime(0.001, t + 0.4);
              o.connect(g);
              o.start(t);
              o.stop(t + 0.42);
              crackle(a, t + 0.05, 0.3, 0.18);
            },
          };
        })();

        /* ---- the glass ---- */
        const H = ROWS * CELL_H;
        function view(k, bright, beamW, beamOn, dot) {
          const scale = `scaleY(${k})`;
          canvas.style.transform = bloom.style.transform = scale;
          canvas.style.filter = bright > 1.01 ? `brightness(${bright})` : "";
          const cover = ((1 - k) * H) / 2;
          top.style.height = bot.style.height = cover + "px";
          glass.style.display = k < 0.999 || beamOn || dot ? "block" : "none";
          beam.style.opacity = beamOn ? 1 : dot;
          beam.style.width = beamW * 100 + "%";
          beam.style.height = beamW < 0.02 ? "6px" : "3px";
        }

        /* ---- the run ---- */
        let run = null,
          shownKey = null,
          target = null;
        const since = {};

        function start(fromK) {
          run = { t0: performance.now(), from: shownKey, cut: false, k0: fromK ?? 1, on: false };
          SFX.off();
        }

        /* The holes and the OBS sources move only here, in the dark. */
        function switchTo(t) {
          if (t === current) return;
          current = t;
          pageEl.style.transform = transformFor(t);
          applyPunch(Number(t));
          Object.entries(panelEls).forEach(([id, el]) => el.classList.toggle("is-live", id === t));
          startTracking(160);
        }

        function animate(now) {
          const e = now - run.t0;
          if (e < at.shrink) {
            const q = easeIn(clamp(e / T.squash));
            const k = lerp(run.k0, K_MIN, q);
            view(k, 1 + q * 1.2, 1, k < 0.02, 0);
          } else if (e < at.fade) {
            const q = easeIn(clamp((e - at.shrink) / T.shrink));
            view(K_MIN, 2.2, lerp(1, 0.004, q), true, 0);
          } else if (e < at.dark) {
            const q = clamp((e - at.fade) / T.fade);
            view(K_MIN, 2.2, 0.004, false, 1 - q);
          } else if (e < at.dotIn) {
            if (!run.cut) {
              run.cut = true;
              shownKey = keyOf(target);
              switchTo(target);
            }
            view(K_MIN, 2.2, 0.004, false, 0.08 * (1 - (e - at.dark) / T.dark));
          } else if (e < at.grow) {
            if (!run.on) {
              run.on = true;
              since[shownKey] = now + T.grow + T.dotIn;
              SFX.on();
            }
            view(K_MIN, 2.2, 0.004, false, clamp((e - at.dotIn) / T.dotIn));
          } else if (e < at.open) {
            const q = easeOut(clamp((e - at.grow) / T.grow));
            view(K_MIN, 2.2, lerp(0.004, 1, q), true, 0);
          } else if (e < T.end) {
            const q = clamp((e - at.open) / T.open);
            view(Math.max(K_MIN, easeBack(q)), lerp(2.2, 1, easeOut(q)), 1, q < 0.05, 0);
          } else {
            view(1, 1, 1, false, 0);
            run = null;
          }
        }

        /* Before OBS names a scene: a terminal waiting. Opaque, so nothing
           unplaced shows through. */
        function boot(g, now) {
          wipe(g, GROUND);
          putText(g, 4, 4, "TECH TALKS TUESDAY", INK, null, 2);
          putText(g, 4, 8, "waiting for OBS ...", DIM);
          if (Math.floor(now / 530) % 2 === 0) putCell(g, 24, 8, "_", INK);
        }

        function tick(now) {
          if (run) animate(now);
          if (shownKey) SCENES[shownKey](G, { now, t: now - (since[shownKey] ?? now) });
          else boot(G, now);
          if (screen.draw(G) && THEME.bloom) {
            bctx.clearRect(0, 0, bloom.width, bloom.height);
            bctx.drawImage(canvas, 0, 0, bloom.width, bloom.height);
          }
        }

        /* Straight to a scene's rest, no switch: the first scene OBS
           reports, so the overlay does not play one on OBS startup. */
        function settle(t) {
          run = null;
          switchTo(t);
          shownKey = keyOf(t);
          since[shownKey] = performance.now();
          view(1, 1, 1, false, 0);
        }

        /* The newest press wins and presses never queue (docs/adr/0018).
           Before the cut: the cut takes the newest scene. After it: the
           tube goes off again from wherever it is. */
        function goTo(t, { instant = false } = {}) {
          if (!PANELS.some((p) => String(p.id) === t)) return;
          target = t;
          if (instant || shownKey === null) return settle(t);
          if (!run) {
            if (t !== current) start(1);
            return;
          }
          if (run.cut) {
            const k = parseFloat((canvas.style.transform.match(/scaleY\(([\d.e-]+)\)/) || [])[1] || K_MIN);
            start(k);
          }
        }

        /* 30 frames a second. */
        let last = 0;
        function loop(now) {
          requestAnimationFrame(loop);
          if (now - last < 1000 / 30 - 2) return;
          last = now;
          tick(now);
        }
        requestAnimationFrame(loop);

        /* The fonts come from Google Fonts; refit, re-measure and repaint
           once they are here. */
        const fontsIn = () => {
          fitFont();
          resetStamps();
          screen.reset();
        };
        document.fonts.addEventListener("loadingdone", fontsIn);
        window.addEventListener("load", () =>
          Promise.all([document.fonts.load(`16px "VT323"`), document.fonts.load(`100px "Anton"`)]).then(fontsIn, fontsIn),
        );

        return {
          goTo,
          state: () => ({ shownKey, current, target, run: run && { ...run, e: performance.now() - run.t0 } }),
        };
      })();

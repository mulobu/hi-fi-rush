/* overlays/neon-nights/cruise.js -- the city page and the cruise
   Loaded in place of core/camera-pan.js (core/README.md, "Another
   transition"; docs/adr/0033). Plain script, not a module (docs/adr/0006).

   Before this file the page defines CANVAS_W and CANVAS_H; art.js comes
   first. After it, and before core/panel-page.js, the page defines PANELS
   (with panel() and hole() below) and SCENES: per scene key, its `words`,
   its `sub` slate, its `sky` class, its `solid` rects (default: the whole
   canvas) and `cut()` / `over()`, which run at boot once SOCIALS exists.
   Nothing here runs until the page's boot script calls startCity().

   THE CRUISE. A switch drives out of the old scene and into the new one.
   The sunset rises from the bottom edge with streaks running ahead of its
   lit rule; once it has the frame, the layout, the windows and the OBS
   sources change behind it; the destination's name slams in as chrome, a
   word at a time, over the sun and the grid; then the sky keeps going and
   leaves out of the top, and the new scene lands with 170 ms of tape tear
   over it. Nothing moves that the video shows through -- the motion is all
   in the cover -- which is why a window never slides out from under its own
   frame mid-switch. */

/* ---- the page of panels: one per scene, each exactly the canvas, side by
   side. They paint nothing; they exist for their holes, which core punches
   and fills with OBS sources. hole() takes a window in canvas px. -------- */
const PANEL_SPACING = CANVAS_W + 80,
  PAGE_W = 6 * PANEL_SPACING,
  PAGE_H = CANVAS_H + 30;
const FULL = [0, 0, CANVAS_W, CANVAS_H];
const hole = (src, a) => ({
  src,
  x: a[0] / (CANVAS_W / 100),
  y: a[1] / (CANVAS_H / 100),
  w: a[2] / (CANVAS_W / 100),
  h: a[3] / (CANVAS_H / 100),
  bare: true,
  label: src,
  c: "#1b0536",
});
const panel = (id, key, holes) => ({
  id,
  key,
  cls: "p-" + key,
  x: (id - 1) * PANEL_SPACING,
  y: 0,
  w: CANVAS_W + 30,
  h: CANVAS_H + 30,
  rot: 0,
  fit: "fill",
  tag: key.toUpperCase(),
  holes,
});
const SCENE_MAP = { START: 1, CHAT: 2, GAME: 3, CAM: 4, BRB: 5, END: 6 };
function scaleFor() {
  return 1;
}
function artFor() {
  return "";
}
/* The panel's content box on the canvas: its 15 px border is outside it. */
function transformFor(t) {
  return `translate(${-(Number(t) - 1) * PANEL_SPACING - 15}px,-15px)`;
}

/* ================================================================
   BUILDERS -- what a scene's cut() and over() are made of. Boxes are in
   canvas px, so a layout reads as the frame it will be.
   ================================================================ */
const SCENE_NO = { start: "01", chat: "02", game: "03", cam: "04", brb: "05", end: "06" };
const r1 = (v) => Math.round(v * 10) / 10;
const px = (v) => `${r1(v)}px`;
const at = (x, y, w, h) =>
  `left:${px(x)};top:${px(y)}` + (w != null ? `;width:${px(w)}` : "") + (h != null ? `;height:${px(h)}` : "");

/* The sky, and the CRT texture over it. Every scene's cut() opens with one
   and closes with the other. */
const sky = (mood = "dusk") => `<div class="sky sky-${mood}"></div>`;
const crt = (vig = true) => (vig ? `<div class="vignette"></div>` : "") + `<div class="scan"></div>`;
const horizon = (y) => `<div class="horizon" style="top:${px(y)}"></div>`;

/* HUGE chrome type: each line is fitted to the box's width at boot
   (fitAll), so a short line sets bigger than a long one. <em> is the cyan
   chrome. `same` sets every line at the size of the one that fits
   smallest. The block is skewed 9 deg, so leave ~0.16 x line-height of
   room to its right. */
function huge(lines, { x, y, w, same = false, cls = "" }) {
  return (
    `<div class="huge ${cls}${same ? " same" : ""}" style="${at(x, y, w)}">` +
    lines.map((l, i) => `<div class="ln" style="--i:${i}"><span class="fit" data-w="${w}">${l}</span></div>`).join("") +
    `</div>`
  );
}
/* A neon sign. `size` is the font size; cy makes it the cyan tube. */
function neon(text, { x, y, size, cls = "" }) {
  return `<div class="neon ${cls}" style="${at(x, y)};font-size:${px(size)}">${text}</div>`;
}
/* The mono caption that labels everything: SCENE 03 ---- OCEAN DRIVE. */
function slate(no, text, x, y, cls = "") {
  return (
    `<div class="slate ${cls}"${x == null ? "" : ` style="${at(x, y)}"`}>` +
    (no ? `<b>SCENE ${no}</b><i></i>` : "") +
    `<span>${text}</span></div>`
  );
}
function note(html, x, y) {
  return `<div class="note" style="${at(x, y)}">${html}</div>`;
}
function rule(x, y, w) {
  return `<div class="rule" style="${at(x, y, w)}"><i></i><i></i><i></i></div>`;
}
/* The HUD money row, carrying the live clock: WED 21:48. Its number is the
   machine's own, updated by CLOCK below -- the one readout on this page
   that is real, which is why the rest of the HUD is drawn as ornament
   rather than as meters that would be lying. */
function clockRow(x, y, size, label = "LIVE") {
  return (
    `<div class="money" style="${at(x, y)};font-size:${px(size)}">` +
    `<small>${label}</small><span class="day-val">---</span><b class="clock-val">--:--</b></div>`
  );
}
/* A window frame: a neon rule 3 px over the hole's edge, chrome brackets
   outside it, and a tab with the source's name. */
function win(r, label, { tab = "tl", corners = ["tl", "tr", "bl", "br"], cls = "", bulbs = false } = {}) {
  const [x, y, w, h] = r;
  return (
    `<div class="win ${cls} tab-${tab}" style="${at(x - 3, y - 3, w + 6, h + 6)}">` +
    corners.map((c) => `<i class="c ${c}"></i>`).join("") +
    (bulbs ? `<i class="bulbs"></i>` : "") +
    (label ? `<span class="win-tab">${label}</span>` : "") +
    `</div>`
  );
}
function socialsRow(cls = "", style = "") {
  return (
    `<div class="soc ${cls}" style="${style}">` +
    SOCIALS.map(
      (g) =>
        `<span class="soc-item">` +
        g.on.map((n) => `<img src="assets/socials/${n}.svg" alt="${SOCIAL_NAMES[n]}">`).join("") +
        `<b>${g.handle}</b></span>`,
    ).join("") +
    `</div>`
  );
}

/* ================================================================
   THE CUT -- the canvas minus this scene's windows, as one evenodd path.
   Written to the on-scene's .cut layer, so every piece of art inside it is
   clipped at the windows and none of it can paint over video. A cut lying
   inside another would flip that region back to opaque under evenodd, so a
   contained cut is dropped first -- the same rule core/holes.js follows for
   its masks, for the same reason (root CLAUDE.md §2).
   ================================================================ */
function cutPath(key) {
  const p = PANELS.find((q) => q.key === key),
    sc = SCENES[key] || {};
  const r = (a) => `M${r1(a[0])} ${r1(a[1])}h${r1(a[2])}v${r1(a[3])}h${r1(-a[2])}Z`;
  if (sc.solid) return sc.solid.map(r).join("");
  const cuts = p.holes.map((h) => [
    (h.x * CANVAS_W) / 100,
    (h.y * CANVAS_H) / 100,
    (h.w * CANVAS_W) / 100,
    (h.h * CANVAS_H) / 100,
  ]);
  const inside = (a, b) =>
    a !== b && a[0] >= b[0] && a[1] >= b[1] && a[0] + a[2] <= b[0] + b[2] && a[1] + a[3] <= b[1] + b[3];
  return r(FULL) + cuts.filter((a) => !cuts.some((b) => inside(a, b))).map(r).join("");
}

/* Fit every .fit to its data-w. Run once the fonts are in; again on a late
   font load, since a fallback face measures differently. */
function fitAll(root = document) {
  const scenes = [...document.querySelectorAll(".scene")];
  scenes.forEach((s) => s.classList.add("measure"));
  root.querySelectorAll(".fit").forEach((el) => {
    el.style.fontSize = "100px";
    /* Layout width, not the rect: a preview scales the whole viewport. */
    const w = el.offsetWidth || 1;
    el.dataset.size = ((100 * Number(el.dataset.w)) / w).toFixed(2);
  });
  root.querySelectorAll(".huge.same").forEach((h) => {
    const fits = [...h.querySelectorAll(".fit")],
      m = Math.min(...fits.map((e) => Number(e.dataset.size)));
    fits.forEach((e) => (e.dataset.size = m));
  });
  root.querySelectorAll(".fit").forEach((el) => (el.style.fontSize = el.dataset.size + "px"));
  scenes.forEach((s) => s.classList.remove("measure"));
}

/* ================================================================
   SCENES on and off
   ================================================================ */
let current = null,
  standalone = false;
function showScene(key, enter) {
  document.querySelectorAll(".scene").forEach((s) => s.classList.toggle("on", s.dataset.key === key));
  document.body.dataset.scene = key;
  const s = document.querySelector(`.scene[data-key="${key}"]`);
  if (!s) return;
  const cut = s.querySelector(".cut");
  if (cut) cut.style.clipPath = `path(evenodd, "${cutPath(key)}")`;
  s.classList.remove("enter");
  if (enter) {
    void s.offsetWidth;
    s.classList.add("enter");
  }
}
/* The holes and the OBS sources move only here, and only while the frame is
   covered (or on the first scene OBS reports). */
function switchTo(t) {
  const p = PANELS.find((q) => String(q.id) === t);
  if (!p || t === current) return;
  current = t;
  showScene(p.key, false);
  pageEl.style.transform = transformFor(t);
  applyPunch(Number(t));
  Object.entries(panelEls).forEach(([id, el]) => el.classList.toggle("is-live", id === t));
  if (!standalone) startTracking(160);
}

function goTo(t, opts) {
  CRUISE.go(String(t), opts || {});
}

/* ================================================================
   THE CRUISE. Newest press wins and presses never queue: while covered the
   words restart for the new scene; while uncovering, the sky comes back
   from wherever it has got to.
   ================================================================ */
const CRUISE = (() => {
  const root = document.getElementById("cruise"),
    skyEl = root.querySelector(".cr-sky"),
    flash = root.querySelector(".cr-flash"),
    wordBox = root.querySelector(".cr-word"),
    ghostBox = root.querySelector(".cr-ghost"),
    sub = root.querySelector(".cr-sub"),
    slateNo = root.querySelector(".cr-no"),
    tear = document.getElementById("tear");
  const W = CANVAS_W,
    H = CANVAS_H,
    TRAVEL = H;
  const DOWN = H,
    HOME = 0,
    UP = -H;
  let gen = 0,
    target = null,
    phase = "covered"; /* boot: covered until OBS names a scene */

  const yOf = (el) => new DOMMatrixReadOnly(getComputedStyle(el).transform).m42;
  const place = (el, y) => {
    el.getAnimations().forEach((a) => a.cancel());
    el.style.transform = `translateY(${y}px)`;
  };
  const wait = (ms, g) => new Promise((done) => setTimeout(() => done(g === gen), ms));
  /* Slide from wherever the sky is. Resolves true if this run is still the
     newest when it lands. The CLOCK decides when it has landed, not the
     animation: a page whose frames stall -- a hidden tab, a GPU reset --
     must still switch, so on time the end state is committed wherever the
     animation got to. */
  function slide(el, to, ms, g, easing = "cubic-bezier(.62,0,.3,1)") {
    const from = yOf(el);
    place(el, from);
    if (Math.abs(to - from) < 1) return Promise.resolve(g === gen);
    const dur = ms * Math.min(1, Math.abs(to - from) / TRAVEL + 0.3);
    el.animate([{ transform: `translateY(${from}px)` }, { transform: `translateY(${to}px)` }], {
      duration: dur,
      easing,
      fill: "forwards",
    });
    return wait(dur, g).then((ok) => {
      if (ok) place(el, to);
      return ok;
    });
  }

  /* Measure with canvas text metrics, so the CAPS -- not the line box --
     are what gets centred and fitted. */
  const ctx = document.createElement("canvas").getContext("2d");
  function metrics(t) {
    ctx.font = `100px Anton, "Arial Narrow", sans-serif`;
    const m = ctx.measureText(t),
      cap = ctx.measureText("H").actualBoundingBoxAscent || 74;
    return { w: m.width, cap };
  }
  /* Where the words go: the page's CRUISE_BOX if it has one (the vertical
     page keeps them inside the platform safe zone), else the canvas. */
  const box = () => (typeof CRUISE_BOX !== "undefined" ? CRUISE_BOX : { x: 0, y: 0, w: W, h: H });
  let lastWord = null;
  function showWord(t, i, n) {
    const { w, cap } = metrics(t),
      B = box(),
      cx = B.x + B.w / 2;
    /* The skew widens the word by 0.1585 of its cap height, so the width it
       is fitted against is the skewed one -- otherwise a two-letter word
       runs off both edges at the size the metrics said would fit. */
    const F = 100 * Math.min((0.86 * B.w) / (w + cap * 0.1585), (0.56 * B.h) / cap),
      ch = (cap * F) / 100,
      base = B.y + B.h / 2 + ch / 2;
    const last = i === n - 1;
    root.dataset.tone = last ? "flash" : "chrome";
    flash.classList.toggle("on", last);
    /* skewX(-9) moves a point left by 0.1585 y, so the compensating shift is
       taken at the CAPS' mid-height, not at the baseline. At the baseline the
       word is centred where no ink is, and the letters themselves land about
       a twelfth of a frame to the right. */
    const sx = (base - ch / 2) * 0.1585;
    const svg = (cls) =>
      `<svg viewBox="0 0 ${W} ${H}" width="${W}" height="${H}"><text class="${cls}" x="${r1(cx)}"` +
      ` y="${r1(base)}" font-size="${r1(F)}" transform="skewX(-9) translate(${r1(sx)} 0)">${t}</text></svg>`;
    /* The word before it zooms out through the frame as an outline. */
    if (lastWord) {
      ghostBox.innerHTML = lastWord;
      ghostBox.animate(
        [
          { transform: "scale(1)", opacity: 0.75 },
          { transform: "scale(1.8)", opacity: 0 },
        ],
        { duration: 340, easing: "cubic-bezier(.2,.7,.3,1)", fill: "forwards" },
      );
    }
    lastWord = svg("ghost");
    wordBox.innerHTML = svg("word");
    wordBox.animate(
      [
        { transform: "scale(1.34) translateX(-2%)", opacity: 0 },
        { opacity: 1, offset: 0.32 },
        { transform: "scale(1)", opacity: 1 },
      ],
      { duration: 160, easing: "cubic-bezier(.2,.9,.3,1)", fill: "forwards" },
    );
    sub.style.top = px(B.y + B.h - 62);
  }

  async function run() {
    const g = ++gen;
    if (phase !== "covered" && phase !== "words") {
      phase = "in";
      lastWord = null;
      flash.classList.remove("on");
      wordBox.innerHTML = ghostBox.innerHTML = "";
      skyEl.classList.add("rush");
      const ok = await slide(skyEl, HOME, 300, g);
      skyEl.classList.remove("rush");
      if (!ok) return;
    }
    phase = "covered";
    switchTo(target);
    const key = PANELS.find((p) => String(p.id) === target).key,
      sc = SCENES[key] || {},
      words = sc.words || [key.toUpperCase()];
    slateNo.textContent = `SCENE ${SCENE_NO[key]} / 06`;
    sub.querySelector("span").textContent = sc.sub || "ON AIR";
    phase = "words";
    const per = words.length > 2 ? 235 : 310;
    for (let i = 0; i < words.length; i++) {
      showWord(words[i], i, words.length);
      if (!(await wait(per, g))) return;
    }
    phase = "out";
    showScene(key, true);
    /* The tear lands on the new scene, not on the sky: fire it once the sky
       is most of the way out. */
    setTimeout(() => {
      if (g !== gen) return;
      tear.classList.add("on");
      setTimeout(() => g === gen && tear.classList.remove("on"), 170);
    }, 190);
    if (!(await slide(skyEl, UP, 320, g, "cubic-bezier(.4,0,.5,1)"))) return;
    place(skyEl, DOWN);
    phase = "idle";
  }

  /* Straight to a scene's rest, no cruise: the first scene OBS reports, so
     the overlay does not play a switch on OBS startup. */
  function settle(t) {
    gen++;
    target = t;
    switchTo(t);
    showScene(PANELS.find((p) => String(p.id) === t).key, false);
    place(skyEl, DOWN);
    tear.classList.remove("on");
    phase = "idle";
  }

  function go(t, { instant = false } = {}) {
    if (!PANELS.some((p) => String(p.id) === t)) return;
    if (instant || current === null) return settle(t);
    if (phase === "idle" && t === current) return;
    target = t;
    run();
  }

  /* Before OBS names a scene the frame is covered, the show's name on it. */
  place(skyEl, HOME);
  return { go, settle, state: () => ({ phase, current, target, gen }), showWord };
})();

/* ================================================================
   THE CLOCK -- the machine's own time, into every .clock-val on the page
   and the cruise. The only live number here; everything else in the HUD is
   ornament, drawn as ornament.
   ================================================================ */
const CLOCK = (() => {
  const DAYS = ["SUN", "MON", "TUE", "WED", "THU", "FRI", "SAT"];
  function tick() {
    const d = new Date(),
      t = `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
    document.querySelectorAll(".clock-val").forEach((e) => (e.textContent = t));
    document.querySelectorAll(".day-val").forEach((e) => (e.textContent = DAYS[d.getDay()]));
  }
  function start() {
    tick();
    setInterval(tick, 10000);
  }
  return { start };
})();

/* ================================================================
   BOOT -- build every scene from SCENES, lay out the tape tear, fit the
   type, and keep the page's keys for previewing outside OBS.
   ================================================================ */
function startCity() {
  document.getElementById("scenes").innerHTML = Object.entries(SCENES)
    .map(
      ([k, s]) =>
        `<div class="scene" data-key="${k}">` +
        `<div class="cut">${sky(s.sky || "dusk")}${s.cut ? s.cut() : ""}${crt(!s.solid)}</div>` +
        `<div class="over">${s.over ? s.over() : ""}</div></div>`,
    )
    .join("");
  /* The tear's bands: uneven heights down the frame, each shearing on its
     own step, which is what a tracking break looks like. */
  const tear = document.getElementById("tear");
  const bands = [0.0, 0.14, 0.26, 0.41, 0.55, 0.68, 0.82, 0.92];
  tear.innerHTML =
    bands
      .map((t, i) => {
        const h = CANVAS_H * (i % 3 === 0 ? 0.1 : i % 3 === 1 ? 0.055 : 0.082);
        return `<i class="tr-band" style="top:${px(CANVAS_H * t)};height:${px(h)};animation-delay:${i * 14}ms"></i>`;
      })
      .join("") + `<div class="tr-rgb"></div><div class="tr-noise"></div>`;
  /* The cover's own sunset, built from the canvas rather than authored
     twice: the same cruise plays on both pages at the same real size. */
  const hy = CANVAS_H * 0.7,
    R = Math.min(CANVAS_W, CANVAS_H) * 0.19,
    /* A palm is drawn 2 : 5, so its height follows its width or the fronds
       squash. On the tall canvas it is half the frame, not all of it, or
       the two of them close over the words. */
    PH = CANVAS_H * (CANVAS_W > CANVAS_H ? 0.95 : 0.55),
    PW = PH * 0.4,
    PY = CANVAS_H - PH * 0.94;
  document.querySelector("#cruise .cr-art").innerHTML =
    ART.stardust({ x: 0, y: 0, w: CANVAS_W, h: hy * 0.72, n: 130, seed: 13 }) +
    ART.sun({ x: CANVAS_W * 0.5, y: hy - CANVAS_H * 0.055, r: R, id: "crsun" }) +
    ART.skyline({ x: -40, y: hy - CANVAS_H * 0.1, w: CANVAS_W + 80, h: CANVAS_H * 0.1, seed: 64 }) +
    horizon(hy) +
    ART.floor({ y: hy, h: CANVAS_H - hy }) +
    ART.palm({ x: -PW * 0.42, y: PY, w: PW, h: PH, seed: 2 }) +
    ART.palm({ x: CANVAS_W - PW * 0.58, y: PY, w: PW, h: PH, seed: 8, flip: true });
  CLOCK.start();
  fitAll();
  CRUISE.showWord("THE DEEP EFFECT", 0, 2);
  document.fonts.ready.then(() => {
    fitAll();
    if (current === null) CRUISE.showWord("THE DEEP EFFECT", 0, 2);
  });
  if (!window.obsstudio) startPreview();
}

/* Outside OBS only: scale the canvas to fit the window, and give it keys
   1-6 and a bar of scene buttons (?clean hides the bar). OBS sizes the
   source to the canvas exactly, so none of this runs there. */
function startPreview() {
  const vp = document.getElementById("viewport");
  vp.style.transformOrigin = "0 0";
  const fit = () => {
    const s = Math.min(1, innerWidth / CANVAS_W, innerHeight / CANVAS_H);
    const x = Math.max(0, (innerWidth - CANVAS_W * s) / 2),
      y = Math.max(0, (innerHeight - CANVAS_H * s) / 2);
    vp.style.transform = `translate(${x}px,${y}px) scale(${s})`;
  };
  addEventListener("resize", fit);
  fit();
  document.addEventListener("keydown", (e) => {
    const n = Number(e.key);
    if (!DEBUG && n >= 1 && n <= PANELS.length) goTo(String(n));
  });
  if (params.has("clean")) return;
  const bar = document.createElement("div");
  bar.className = "preview-bar";
  bar.innerHTML = Object.entries(SCENE_MAP)
    .map(([name, id]) => `<button data-id="${id}">${id} ${name}</button>`)
    .join("");
  bar.addEventListener("click", (e) => {
    const b = e.target.closest("button");
    if (b) goTo(b.dataset.id);
  });
  document.body.appendChild(bar);
  setInterval(
    () =>
      bar
        .querySelectorAll("button")
        .forEach((b) => b.classList.toggle("on", b.dataset.id === (CRUISE.state().target || current))),
    150,
  );
}

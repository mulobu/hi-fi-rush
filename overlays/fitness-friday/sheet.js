/* overlays/fitness-friday/sheet.js -- the drafting sheet and the sting
   Loaded in place of core/camera-pan.js (core/README.md, "Another
   transition"; docs/adr/0027). Plain script, not a module (docs/adr/0006).

   Before this file the page defines CANVAS_W and CANVAS_H; anatomy.js comes
   first. After it, and before core/panel-page.js, the page defines PANELS
   (with panel() and hole() below) and SCENES: per scene key, its sting
   `words`, its sheet `solid` rects (default: the whole canvas) and `html()`,
   which runs at boot once SOCIALS exists. Nothing here runs until the
   page's boot script calls startSheet().

   One drafting sheet, royal blue with its grid, has each scene's windows
   cut out of it; the video shows through them. A switch is the sting: a
   yellow slab and a blue one sweep across, the destination's words slam in
   one at a time, filling the frame, and the slabs sweep off the new scene.
   The layout, the holes and the OBS sources change only while the frame is
   covered. */

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
  c: "#0d2275",
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
function transformFor(t) {
  return `translate(${-(Number(t) - 1) * PANEL_SPACING - 15}px,-15px)`;
}

/* ================================================================
   BUILDERS -- what a page's SCENES html() is made of. Boxes are canvas px.
   ================================================================ */
const SHEET_NO = { start: "01", chat: "02", game: "03", cam: "04", brb: "05", end: "06" };
const px = (v) => `${Math.round(v * 10) / 10}px`;
const at = (x, y, w, h) =>
  `left:${px(x)};top:${px(y)}` + (w != null ? `;width:${px(w)}` : "") + (h != null ? `;height:${px(h)}` : "");

/* HUGE type: each line is fitted to the box's width at boot (fitAll), so a
   short line sets bigger than a long one. <em> is the yellow. `same` sets
   every line at the size of the one that fits smallest. */
function huge(lines, { x, y, w, same = false, cls = "" }) {
  return (
    `<div class="huge ${cls}${same ? " same" : ""}" style="${at(x, y, w)}">` +
    lines.map((l, i) => `<div class="ln" style="--i:${i}"><span class="fit" data-w="${w}">${l}</span></div>`).join("") +
    `</div>`
  );
}
/* The figure caption over a plate or a headline. */
function fig(no, text, x, y, cls = "") {
  return `<div class="fig ${cls}"${x == null ? "" : ` style="${at(x, y)}"`}><b>FIG. ${no}</b><i></i><span>${text}</span></div>`;
}
function socialsRow(cls = "", style = "") {
  return (
    `<div class="soc ${cls}" style="${style}">` +
    SOCIALS.map(
      (g) =>
        `<span class="soc-item">${g.on.map((n) => `<img src="assets/socials/${n}.svg" alt="${SOCIAL_NAMES[n]}">`).join("")}<b>${g.handle}</b></span>`,
    ).join("") +
    `</div>`
  );
}
/* The drawing's title block, bottom corner of a sheet: show, sheet number,
   scale, title, drawn-by, date, and the socials row. */
function titleBlock(key, title, { x, y, w, scale = "1 : 10", cls = "" }) {
  const d = new Date(),
    date = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
  return (
    `<div class="tblock ${cls}" style="${at(x, y, w)}">` +
    `<div class="tb-name"><span>FITNESS</span> <em>FRIDAY</em></div>` +
    `<div class="tb-cell"><small>SHEET</small><b>${SHEET_NO[key]} / 06</b></div>` +
    `<div class="tb-cell"><small>SCALE</small><b>${scale}</b></div>` +
    `<div class="tb-cell tb-wide"><small>TITLE</small><b>${title}</b></div>` +
    `<div class="tb-cell"><small>DRAWN</small><b>THE DEEP EFFECT</b></div>` +
    `<div class="tb-cell"><small>DATE</small><b>${date}</b></div>` +
    `<div class="tb-soc">${socialsRow(cls === "narrow" ? "stack" : "")}</div>` +
    `</div>`
  );
}
/* A window frame: yellow rule, corner brackets outside it, a tab with the
   source's name. The video fills the rect; the rule sits 3 px over its edge. */
function win(r, label, { tab = "tl", corners = ["tl", "tr", "bl", "br"] } = {}) {
  const [x, y, w, h] = r;
  return `<div class="win tab-${tab}" style="${at(x, y, w, h)}">${corners.map((c) => `<i class="c ${c}"></i>`).join("")}${label ? `<span class="win-tab">${label}</span>` : ""}</div>`;
}
/* A running ECG strip, w x h. The trace is two copies long and slides one
   copy's worth per loop, at 72 bpm. */
function ecgStrip(x, y, w, h, { beat = 180, cls = "" } = {}) {
  const k = Math.ceil(w / beat),
    dur = ((k * 60) / 72).toFixed(3);
  return (
    `<div class="ecg ${cls}" style="${at(x, y, w, h)}"><div class="ecg-run" style="width:${2 * k * beat}px;animation-duration:${dur}s;--shift:${-k * beat}px">` +
    `<svg viewBox="0 0 ${2 * k * beat} ${h}" width="${2 * k * beat}" height="${h}"><path d="${ANATOMY.ecg(2 * k, beat, h * 0.7, h * 0.78)}"/></svg>` +
    `</div></div>`
  );
}
/* The BPM readout. Its number is HEART's: the drawn 72 until the watch
   sends one (docs/adr/0028). */
function bpmReadout(x, y, size) {
  return `<div class="bpm" style="${at(x, y)};font-size:${size}px"><span class="bpm-val">72</span><small>BPM</small></div>`;
}
function dimLine(x1, x2, y, text) {
  return `<div class="dimh" style="${at(x1, y, x2 - x1)}"><span>${text}</span></div>`;
}

/* The drafting border: a rule inset 20 px, zone numbers along the top and
   bottom, zone letters down the sides. Shared by every sheet scene. */
function zoneFrame() {
  const I = 20,
    W = CANVAS_W,
    H = CANVAS_H,
    nx = Math.round(W / 240),
    ny = Math.round(H / 216);
  let d = `M${I} ${I}H${W - I}V${H - I}H${I}Z`,
    t = "";
  for (let i = 0; i <= nx; i++) {
    const x = I + ((W - 2 * I) * i) / nx;
    d += `M${x} 0V${I}M${x} ${H - I}V${H}`;
    if (i < nx) {
      const cx = x + (W - 2 * I) / nx / 2;
      t += `<text x="${cx}" y="14">${i + 1}</text><text x="${cx}" y="${H - 6}">${i + 1}</text>`;
    }
  }
  for (let j = 0; j <= ny; j++) {
    const y = I + ((H - 2 * I) * j) / ny;
    d += `M0 ${y}H${I}M${W - I} ${y}H${W}`;
    if (j < ny) {
      const cy = y + (H - 2 * I) / ny / 2 + 4;
      const L = String.fromCharCode(65 + j);
      t += `<text x="10" y="${cy}">${L}</text><text x="${W - 10}" y="${cy}">${L}</text>`;
    }
  }
  const crop = (x, y, sx, sy) => `M${x} ${y + sy * 34}V${y}H${x + sx * 34}`;
  d += crop(I + 8, I + 8, 1, 1) + crop(W - I - 8, I + 8, -1, 1) + crop(I + 8, H - I - 8, 1, -1) + crop(W - I - 8, H - I - 8, -1, -1);
  return `<svg class="zones" viewBox="0 0 ${W} ${H}"><path d="${d}"/>${t}</svg>`;
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
   THE SHEET -- one background, its windows cut per scene (evenodd)
   ================================================================ */
function sheetPath(key) {
  const p = PANELS.find((q) => q.key === key),
    sc = SCENES[key] || {};
  const r = (a) => `M${a[0]} ${a[1]}h${a[2]}v${a[3]}h${-a[2]}Z`;
  let d;
  if (sc.solid) d = sc.solid.map(r).join("");
  else {
    const cuts = p.holes.map((h) => [(h.x * CANVAS_W) / 100, (h.y * CANVAS_H) / 100, (h.w * CANVAS_W) / 100, (h.h * CANVAS_H) / 100]);
    const inside = (a, b) => a !== b && a[0] >= b[0] && a[1] >= b[1] && a[0] + a[2] <= b[0] + b[2] && a[1] + a[3] <= b[1] + b[3];
    d = r(FULL) + cuts.filter((a) => !cuts.some((b) => inside(a, b))).map(r).join("");
  }
  document.querySelectorAll("#sheet-bg path").forEach((el) => el.setAttribute("d", d));
}

let current = null,
  standalone = false;
function showScene(key, enter) {
  document.querySelectorAll(".scene").forEach((s) => s.classList.toggle("on", s.dataset.key === key));
  document.body.dataset.scene = key;
  document.body.classList.toggle("bands", !!(SCENES[key] && SCENES[key].solid));
  sheetPath(key);
  const s = document.querySelector(`.scene[data-key="${key}"]`);
  if (!s) return;
  s.classList.remove("enter");
  if (enter) {
    void s.offsetWidth;
    s.classList.add("enter");
  }
}
/* The holes and the OBS sources move only here, and only while the frame
   is covered (or on the first scene OBS reports). */
function switchTo(t) {
  const p = PANELS.find((q) => String(q.id) === t);
  if (!p) return;
  if (t === current) return;
  current = t;
  showScene(p.key, false);
  pageEl.style.transform = transformFor(t);
  applyPunch(Number(t));
  Object.entries(panelEls).forEach(([id, el]) => el.classList.toggle("is-live", id === t));
  if (!standalone) startTracking(160);
}

function goTo(t, opts) {
  STING.go(String(t), opts || {});
}

/* ================================================================
   THE STING -- slabs in, the words, slabs out. Newest press wins and
   presses never queue: while covered the words restart for the new scene;
   while uncovering, the slabs come back from wherever they are.
   ================================================================ */
const STING = (() => {
  const root = document.getElementById("sting"),
    yel = root.querySelector(".st-y"),
    blu = root.querySelector(".st-b"),
    flash = root.querySelector(".st-flash"),
    wordBox = root.querySelector(".st-word"),
    ghostBox = root.querySelector(".st-ghost"),
    dim = root.querySelector(".st-dim"),
    slate = root.querySelector(".st-fig");
  const W = CANVAS_W,
    H = CANVAS_H,
    TRAVEL = W + 520; /* a slab is the canvas plus 260 px of slant each side */
  const OFF_L = -TRAVEL,
    OFF_R = TRAVEL;
  let gen = 0,
    target = null,
    phase = "covered"; /* boot: covered until OBS names a scene */

  const xOf = (el) => new DOMMatrixReadOnly(getComputedStyle(el).transform).m41;
  const place = (el, x) => {
    el.getAnimations().forEach((a) => a.cancel());
    el.style.transform = `translateX(${x}px)`;
  };
  const wait = (ms, g) => new Promise((done) => setTimeout(() => done(g === gen), ms));
  /* Slide from wherever the slab is. Resolves true if this run is still the
     newest when it lands. The clock decides when it has landed, not the
     animation: a page whose frames stall (a hidden tab) must still switch,
     so on time the end state is committed wherever the animation got to. */
  function slide(el, to, ms, delay, g, easing = "cubic-bezier(.7,0,.3,1)") {
    const from = xOf(el);
    place(el, from);
    if (Math.abs(to - from) < 1) return Promise.resolve(g === gen);
    const dur = ms * Math.min(1, Math.abs(to - from) / TRAVEL + 0.25);
    el.animate([{ transform: `translateX(${from}px)` }, { transform: `translateX(${to}px)` }], {
      duration: dur,
      delay,
      easing,
      fill: "forwards",
    });
    return wait(dur + delay, g).then((ok) => {
      if (ok) place(el, to);
      return ok;
    });
  }

  /* Measure with canvas text metrics, so the caps -- not the line box -- are
     what is centred and fitted. */
  const ctx = document.createElement("canvas").getContext("2d");
  function metrics(t) {
    ctx.font = `100px Anton, "Arial Narrow", sans-serif`;
    const m = ctx.measureText(t),
      cap = ctx.measureText("H").actualBoundingBoxAscent || 74;
    return { w: m.width, cap };
  }
  /* Where the words go: the page's STING_BOX if it has one (the vertical
     page keeps them inside the platform safe zone), else the canvas. */
  const box = () =>
    typeof STING_BOX !== "undefined" ? STING_BOX : { x: 0, y: 0, w: W, h: H };
  let lastWord = null;
  function showWord(t, i, n) {
    const { w, cap } = metrics(t),
      B = box(),
      cx = B.x + B.w / 2;
    const F = 100 * Math.min((0.9 * B.w) / w, (0.66 * B.h) / cap),
      ww = (w * F) / 100,
      ch = (cap * F) / 100,
      base = B.y + B.h / 2 + ch / 2;
    const last = i === n - 1;
    root.dataset.tone = last ? "flash" : i % 2 ? "yellow" : "white";
    flash.classList.toggle("on", last);
    const svg = (cls) =>
      `<svg viewBox="0 0 ${W} ${H}" width="${W}" height="${H}"><text class="${cls}" x="${cx}" y="${base.toFixed(1)}" font-size="${F.toFixed(1)}">${t}</text></svg>`;
    /* The word before zooms through the frame as an outline. */
    if (lastWord) {
      ghostBox.innerHTML = lastWord;
      ghostBox.animate([{ transform: "scale(1)", opacity: 0.7 }, { transform: "scale(1.7)", opacity: 0 }], {
        duration: 340,
        easing: "cubic-bezier(.2,.7,.3,1)",
        fill: "forwards",
      });
    }
    lastWord = svg("ghost");
    wordBox.innerHTML = svg("word");
    wordBox.animate(
      [{ transform: "scale(1.32)", opacity: 0 }, { opacity: 1, offset: 0.35 }, { transform: "scale(1)", opacity: 1 }],
      { duration: 150, easing: "cubic-bezier(.2,.9,.3,1)", fill: "forwards" },
    );
    /* A dimension line under the word, as if the sheet measured it. */
    Object.assign(dim.style, { left: px(cx - ww / 2), width: px(ww), top: px(base + 34) });
    dim.firstChild.textContent = `${Math.round(ww)} PX`;
  }

  async function run() {
    const g = ++gen;
    if (phase !== "covered" && phase !== "words") {
      phase = "in";
      lastWord = null;
      flash.classList.remove("on");
      wordBox.innerHTML = ghostBox.innerHTML = "";
      dim.firstChild.textContent = "";
      const a = slide(yel, 0, 240, 0, g),
        b = slide(blu, 0, 250, 70, g);
      if (!(await Promise.all([a, b])).every(Boolean)) return;
    }
    phase = "covered";
    switchTo(target);
    const key = PANELS.find((p) => String(p.id) === target).key,
      words = (SCENES[key] && SCENES[key].words) || [key.toUpperCase()];
    slate.textContent = `FIG. ${SHEET_NO[key]}`;
    phase = "words";
    const per = words.length > 2 ? 230 : 300;
    for (let i = 0; i < words.length; i++) {
      showWord(words[i], i, words.length);
      if (!(await wait(per, g))) return;
    }
    phase = "out";
    showScene(key, true);
    const a = slide(blu, OFF_R, 280, 0, g),
      b = slide(yel, OFF_R, 280, 90, g);
    if (!(await Promise.all([a, b])).every(Boolean)) return;
    place(yel, OFF_L);
    place(blu, OFF_L);
    phase = "idle";
  }

  /* Straight to a scene's rest, no sting: the first scene OBS reports, so
     the overlay does not play a switch on OBS startup. */
  function settle(t) {
    gen++;
    target = t;
    switchTo(t);
    showScene(PANELS.find((p) => String(p.id) === t).key, false);
    place(yel, OFF_L);
    place(blu, OFF_L);
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
  place(yel, 0);
  place(blu, 0);
  return { go, settle, state: () => ({ phase, current, target, gen }), showWord };
})();

/* ================================================================
   LIVE HEART RATE -- from heart/heart-bridge.py, which the watch app posts
   to (docs/adr/0028). Three states, on body[data-hr]:
     design  no reading yet this session: the drawn 72, as designed
     live    a reading under STALE old: the number, and the hearts beat at
             that rate
     lost    there were readings and none for STALE: a dash, dimmed -- a
             number that is not live is never shown
   Staleness is this page's own clock from when a reading arrived, never
   the watch's timestamp: two clocks disagree. The ECG keeps its drawn
   speed; a trace scrolls at a constant paper speed, and changing a running
   CSS animation's duration makes it jump.
   ================================================================ */
const HEART = (() => {
  const STALE = 15000,
    DESIGN = 72;
  let bpm = null,
    last = 0;
  function show(state) {
    document.body.dataset.hr = state;
    const text = state === "live" ? String(bpm) : state === "lost" ? "--" : String(DESIGN);
    document.querySelectorAll(".bpm-val").forEach((e) => (e.textContent = text));
    const rate = state === "live" ? bpm : DESIGN;
    document.documentElement.style.setProperty("--beat", `${Math.round(60000 / rate)}ms`);
  }
  function start(port) {
    show("design");
    if (!port || !("EventSource" in window)) return;
    /* The bridge may start after OBS, or not at all. EventSource would
       retry every 3 s forever, and each refused try is an error line in
       the log, so it is reopened by hand with a backoff: 3 s doubling to
       a minute, back to 3 s once connected. */
    let wait = 3000;
    const open = () => {
      const es = new EventSource(`http://127.0.0.1:${port}/events`);
      es.onopen = () => (wait = 3000);
      es.onerror = () => {
        es.close();
        setTimeout(open, wait);
        wait = Math.min(wait * 2, 60000);
      };
      es.addEventListener("hr", (ev) => {
        let d;
        try {
          d = JSON.parse(ev.data);
        } catch (e) {
          return;
        }
        if (!(d && d.bpm >= 20 && d.bpm <= 250)) return;
        bpm = Math.round(d.bpm);
        last = Date.now();
        show("live");
      });
    };
    open();
    setInterval(() => {
      if (bpm !== null && Date.now() - last > STALE && document.body.dataset.hr === "live") show("lost");
    }, 1000);
  }
  return { start, state: () => ({ state: document.body.dataset.hr, bpm, age: last ? Date.now() - last : null }) };
})();

/* ================================================================
   BOOT -- build every scene from SCENES, fit the type, and keep the
   page's keys for previewing outside OBS.
   ================================================================ */
function startSheet() {
  const host = document.getElementById("scenes");
  host.innerHTML = Object.entries(SCENES)
    .map(([k, s]) => `<div class="scene" data-key="${k}">${s.html()}</div>`)
    .join("");
  document.getElementById("zones").innerHTML = zoneFrame();
  HEART.start(OVERLAY_CONTRACT.ports.heart);
  fitAll();
  STING.showWord("FITNESS FRIDAY", 0, 2);
  document.fonts.ready.then(() => {
    fitAll();
    if (current === null) STING.showWord("FITNESS FRIDAY", 0, 2);
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
  const mark = () =>
    bar.querySelectorAll("button").forEach((b) => b.classList.toggle("on", b.dataset.id === (STING.state().target || current)));
  setInterval(mark, 150);
}

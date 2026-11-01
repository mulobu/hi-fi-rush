/* core/obs-link.js -- scene detection and the obs-websocket client
   Shared by every overlay page. Plain script, not a module: pages load as
   file:// and Chromium refuses modules there (docs/adr/0006). What a page
   must define before loading this, and the load order, are in
   core/README.md. */

      /* ================================================================
   OBS WIRING

   Scene detection is window.obsstudio first, websocket second.
   Measured on OBS 32.0.1 / obs-websocket 5.6.3: both paths fire on
   every switch and land within one 60fps frame of each other, but
   obsstudio keeps working when the socket is down. See CLAUDE.md §2.
   ================================================================ */
      let currentScene = null,
        seeded = false;

      function applyScene(name, via) {
        if (!name) return;

        /* The host scene is not a panel. Clicking COMIC in OBS during setup
           must not move the page. */
        if (name === OVERLAY_CONTRACT.host.main)
          return hud(`${via}: ${name} — host scene, ignored`, true);

        const id = SCENE_MAP[name];
        if (!id) return hud(`${via}: ${name} — not a mapped scene, ignored`, true);

        /* Both paths report the same switch a few ms apart. First one wins;
           the second is a no-op rather than a second pan. */
        if (name === currentScene) return;

        currentScene = name;
        const first = !seeded;
        seeded = true;
        goTo(String(id), { instant: first });
        syncVisibility();
        /* Re-read sizes, because the crop that makes a source fill its opening
           depends on them and a capture can change resolution at any time —
           a game going fullscreen, a webcam renegotiating. One request per
           pan, against an idle cost of zero between them. */
        if (wsReady && PAGE.hostKey()) loadItemIds({ quiet: true });
        hud(`${via}: ${name} → panel ${id}${first ? " (seed)" : ""}`);
      }

      /* --- path A: window.obsstudio ------------------------------------ */
      function listenObsStudio() {
        window.addEventListener("obsSceneChanged", (e) =>
          applyScene(e.detail && e.detail.name, "obsstudio"),
        );
      }

      /* getCurrentScene() comes back null at startup in a nested source — it
         only learns on the first change. Retry for a few seconds, and let the
         websocket seed us if it never answers. The vertical page does not
         call this: inside a second canvas obsstudio's answer is unmeasured,
         and its websocket seed is the primary path anyway. */
      function seedFromObsStudio(tries) {
        if (seeded || !window.obsstudio) return;
        try {
          window.obsstudio.getCurrentScene((sc) => {
            if (sc && sc.name) applyScene(sc.name, "obsstudio/seed");
          });
        } catch (_) {}
        if (tries < 12) setTimeout(() => seedFromObsStudio(tries + 1), 300);
      }

      /* --- path B: obs-websocket v5 ------------------------------------ */
      const K = [
        0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1,
        0x923f82a4, 0xab1c5ed5, 0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3,
        0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174, 0xe49b69c1, 0xefbe4786,
        0x0fc19dc6, 0x240ca1cc, 0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da,
        0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7, 0xc6e00bf3, 0xd5a79147,
        0x06ca6351, 0x14292967, 0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13,
        0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85, 0xa2bfe8a1, 0xa81a664b,
        0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
        0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a,
        0x5b9cca4f, 0x682e6ff3, 0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208,
        0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2,
      ];
      const rotr = (x, n) => ((x >>> n) | (x << (32 - n))) >>> 0;

      /* Hand-rolled because crypto.subtle needs a secure context and this
         page is loaded from file:// inside CEF. Verified against node's
         crypto over 285 vectors. */
      function sha256(bytes) {
        const len = bytes.length;
        const buf = new Uint8Array(((len + 9 + 63) >> 6) << 6);
        buf.set(bytes);
        buf[len] = 0x80;
        const dv = new DataView(buf.buffer);
        dv.setUint32(buf.length - 4, (len * 8) >>> 0, false);
        dv.setUint32(buf.length - 8, Math.floor((len * 8) / 4294967296), false);

        let H = [
          0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a, 0x510e527f,
          0x9b05688c, 0x1f83d9ab, 0x5be0cd19,
        ];
        const w = new Uint32Array(64);

        for (let i = 0; i < buf.length; i += 64) {
          for (let j = 0; j < 16; j++) w[j] = dv.getUint32(i + j * 4, false);
          for (let j = 16; j < 64; j++) {
            const a = w[j - 15],
              b = w[j - 2];
            const s0 = (rotr(a, 7) ^ rotr(a, 18) ^ (a >>> 3)) >>> 0;
            const s1 = (rotr(b, 17) ^ rotr(b, 19) ^ (b >>> 10)) >>> 0;
            w[j] = (w[j - 16] + s0 + w[j - 7] + s1) >>> 0;
          }
          let [a, b, c, d, e, f, g, h] = H;
          for (let j = 0; j < 64; j++) {
            const S1 = (rotr(e, 6) ^ rotr(e, 11) ^ rotr(e, 25)) >>> 0;
            const ch = ((e & f) ^ (~e & g)) >>> 0;
            const t1 = (h + S1 + ch + K[j] + w[j]) >>> 0;
            const S0 = (rotr(a, 2) ^ rotr(a, 13) ^ rotr(a, 22)) >>> 0;
            const maj = ((a & b) ^ (a & c) ^ (b & c)) >>> 0;
            const t2 = (S0 + maj) >>> 0;
            h = g;
            g = f;
            f = e;
            e = (d + t1) >>> 0;
            d = c;
            c = b;
            b = a;
            a = (t1 + t2) >>> 0;
          }
          H = H.map((v, k) => (v + [a, b, c, d, e, f, g, h][k]) >>> 0);
        }
        const out = new Uint8Array(32);
        const odv = new DataView(out.buffer);
        H.forEach((v, i) => odv.setUint32(i * 4, v, false));
        return out;
      }

      const utf8 = (str) => new TextEncoder().encode(str);
      const b64 = (bytes) => btoa(String.fromCharCode(...bytes));
      const catBytes = (a, b) => {
        const r = new Uint8Array(a.length + b.length);
        r.set(a);
        r.set(b, a.length);
        return r;
      };
      const authString = (pw, salt, challenge) =>
        b64(
          sha256(catBytes(utf8(b64(sha256(utf8(pw + salt)))), utf8(challenge))),
        );

      const WS_URL =
        params.get("host") || "ws://127.0.0.1:" + OVERLAY_CONTRACT.ports.obs;
      const WS_PW = params.get("pw") || "";

      function request(type, data) {
        return new Promise((resolve, reject) => {
          if (!wsReady) return reject(new Error("not identified"));
          const id = "r" + ++reqId;
          pendingReq.set(id, { resolve, reject });
          ws.send(
            JSON.stringify({
              op: 6,
              d: { requestType: type, requestId: id, requestData: data || {} },
            }),
          );
        });
      }

      function connect() {
        try {
          ws = new WebSocket(WS_URL);
        } catch (_) {
          return scheduleReconnect();
        }

        ws.onclose = () => {
          wsReady = false;
          PAGE.onClosed();
          pendingReq.clear();
          hud("websocket: closed", true);
          scheduleReconnect();
        };
        ws.onerror = () => {}; /* onclose always follows; handle it there */

        ws.onmessage = (ev) => {
          const msg = JSON.parse(ev.data);

          if (msg.op === 0) {
            /* General | Scenes | Inputs — Inputs for Browser's mute. */
            const d = { rpcVersion: 1, eventSubscriptions: 1 | 4 | 8 };
            if (msg.d.authentication) {
              if (!WS_PW) {
                hud("websocket: server wants a password, none given", true);
                return ws.close();
              }
              d.authentication = authString(
                WS_PW,
                msg.d.authentication.salt,
                msg.d.authentication.challenge,
              );
            }
            ws.send(JSON.stringify({ op: 1, d }));
            return;
          }

          if (msg.op === 2) {
            wsReady = true;
            backoff = 1000;
            hud("websocket: identified");
            /* Seeds the panel if obsstudio hasn't already, and re-syncs after
               a reconnect in case a switch happened while we were away. No
               canvasUuid: the MAIN canvas's program scene drives every page,
               the vertical one included. */
            request("GetSceneList")
              .then((r) =>
                applyScene(r.currentProgramSceneName, "websocket/seed"),
              )
              .catch(() => {});
            PAGE.onIdentified();
            request("GetInputMute", { inputName: BROWSER })
              .then((r) => setBrowserLive(!r.inputMuted))
              .catch(() => setBrowserLive(false));
            return;
          }

          if (msg.op === 5) {
            const e = msg.d.eventData || {};
            if (msg.d.eventType === "CurrentProgramSceneChanged")
              applyScene(e.sceneName, "websocket");
            else if (e.inputName === BROWSER) {
              if (msg.d.eventType === "InputMuteStateChanged")
                setBrowserLive(!e.inputMuted);
              else if (msg.d.eventType === "InputRemoved") setBrowserLive(false);
            }
            return;
          }

          if (msg.op === 9) return; /* RequestBatchResponse — fire and forget */

          if (msg.op === 7) {
            const pr = pendingReq.get(msg.d.requestId);
            if (!pr) return;
            pendingReq.delete(msg.d.requestId);
            if (msg.d.requestStatus.result)
              pr.resolve(msg.d.responseData || {});
            else pr.reject(new Error(msg.d.requestStatus.comment || "failed"));
          }
        };
      }

      function scheduleReconnect() {
        setTimeout(connect, backoff);
        backoff = Math.min(backoff * 2, 8000);
      }

      /* Socket state. Nothing touches it until the page's boot script
         calls connect(), by which time every core file has loaded. */
      let ws = null,
        wsReady = false,
        reqId = 0,
        backoff = 1000;
      const pendingReq = new Map();

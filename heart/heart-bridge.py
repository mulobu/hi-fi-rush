#!/usr/bin/env python3
"""
heart-bridge -- live heart rate from the watch to the overlay pages.

    python3 heart/heart-bridge.py           Windows: py -3 heart\\heart-bridge.py
    python3 heart/heart-bridge.py --fake    a synthetic heart rate, no watch

The watch app (docs/adr/0028) posts each reading here, and the pages listen
on /events, the way chat/tts.html listens to the chat bridge.

    POST /hr       {"bpm": 72, "at": 1730000000000}  ->  204
                   bpm: a number from 20 to 250. at: when it was measured,
                   ms since the epoch, optional. A bare number also works.
                   Anything else -> 400, with the reason.
    GET  /events   Server-Sent Events: an "hr" event per reading, data
                   {"bpm", "at", "rx"} -- rx is this bridge's receive time.
                   A fresh reading is sent on connect.
    GET  /status   the last reading, its age, and how many pages listen

It listens on every interface, because the watch is another device on the
network: the first run on Windows asks to allow Python through the firewall
(Private networks). The addresses to give the watch app are printed at
startup. Standard library only.
"""

from __future__ import annotations

import argparse
import json
import random
import socket
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
LO, HI = 20, 250
STALE = 15.0          # s: the watch measures about every 5 s, sometimes late
KEEPALIVE = 15.0      # s between comments on an idle event stream


def load_contract() -> dict:
    """core/contract.js, whose body is strict JSON (docs/adr/0004)."""
    text = (REPO / "core" / "contract.js").read_text(encoding="utf-8")
    start = text.index("=", text.index("window.OVERLAY_CONTRACT")) + 1
    return json.loads(text[start:text.rindex("}") + 1])


LOG_LOCK = threading.Lock()


def log(msg: str) -> None:
    with LOG_LOCK:
        print(time.strftime("%H:%M:%S ") + msg, flush=True)


def now_ms() -> int:
    return int(time.time() * 1000)


class State:
    """The last reading, and a condition every event stream waits on."""

    def __init__(self) -> None:
        self.cond = threading.Condition()
        self.reading: dict | None = None
        self.seq = 0
        self.clients = 0
        self.lost = False

    def put(self, bpm: int, at: int | None, who: str) -> None:
        with self.cond:
            first = self.reading is None
            self.reading = {"bpm": bpm, "at": at, "rx": now_ms()}
            self.seq += 1
            back, self.lost = self.lost, False
            self.cond.notify_all()
        if first:
            log("first reading: %d bpm from %s" % (bpm, who))
        elif back:
            log("readings back: %d bpm from %s" % (bpm, who))

    def fresh(self) -> dict | None:
        r = self.reading
        return r if r and now_ms() - r["rx"] < STALE * 1000 else None

    def watch(self) -> None:
        """Say once when the readings stop."""
        while True:
            time.sleep(1)
            with self.cond:
                r = self.reading
                gone = r and not self.lost and now_ms() - r["rx"] >= STALE * 1000
                if gone:
                    self.lost = True
            if gone:
                log("no reading for %ds -- the pages show the readout as lost" % STALE)


STATE = State()


def parse(body: bytes) -> tuple[int | None, int | None, str]:
    """(bpm, at, error) from a request body."""
    try:
        d = json.loads(body.decode("utf-8") or "null")
    except (ValueError, UnicodeDecodeError):
        return None, None, "the body is not JSON"
    if isinstance(d, (int, float)) and not isinstance(d, bool):
        d = {"bpm": d}
    if not isinstance(d, dict):
        return None, None, 'send {"bpm": 72}'
    bpm, at = d.get("bpm"), d.get("at")
    if isinstance(bpm, bool) or not isinstance(bpm, (int, float)) or not LO <= bpm <= HI:
        return None, None, "bpm must be a number from %d to %d" % (LO, HI)
    ok_at = isinstance(at, (int, float)) and not isinstance(at, bool)
    return round(bpm), int(at) if ok_at else None, ""


class Handler(BaseHTTPRequestHandler):
    server_version = "heart-bridge"

    def log_message(self, *args) -> None:  # one line per reading is noise
        pass

    def cors(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")

    def reply(self, code: int, obj: dict | None = None) -> None:
        body = json.dumps(obj).encode() if obj is not None else b""
        self.send_response(code)
        self.cors()
        if body:
            self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self.cors()
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_POST(self) -> None:
        if self.path.split("?")[0] != "/hr":
            return self.reply(404, {"error": "POST to /hr"})
        n = int(self.headers.get("Content-Length") or 0)
        if n > 4096:
            return self.reply(413, {"error": "too big"})
        bpm, at, err = parse(self.rfile.read(n))
        if err:
            return self.reply(400, {"error": err})
        STATE.put(bpm, at, self.client_address[0])
        self.reply(204)

    def do_GET(self) -> None:
        path = self.path.split("?")[0]
        if path == "/events":
            return self.events()
        if path == "/status":
            r = STATE.reading
            return self.reply(200, {
                **(r or {"bpm": None, "at": None, "rx": None}),
                "age": (now_ms() - r["rx"]) if r else None,
                "fresh": STATE.fresh() is not None,
                "clients": STATE.clients,
            })
        self.reply(404, {"error": "GET /events or /status, POST /hr"})

    def events(self) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.cors()
        self.end_headers()
        with STATE.cond:
            STATE.clients += 1
            seen = STATE.seq
        log("page connected (%d listening)" % STATE.clients)
        try:
            self.wfile.write(b"retry: 3000\n\n")
            r = STATE.fresh()
            if r:
                self.send_reading(r)
            self.wfile.flush()
            while True:
                with STATE.cond:
                    STATE.cond.wait_for(lambda: STATE.seq != seen, timeout=KEEPALIVE)
                    changed, seen, r = STATE.seq != seen, STATE.seq, STATE.reading
                if changed:
                    self.send_reading(r)
                else:
                    self.wfile.write(b": keepalive\n\n")
                self.wfile.flush()
        except OSError:
            pass
        finally:
            with STATE.cond:
                STATE.clients -= 1
            log("page gone (%d listening)" % STATE.clients)

    def send_reading(self, r: dict) -> None:
        self.wfile.write(("event: hr\ndata: %s\n\n" % json.dumps(r)).encode())


def lan_addresses() -> list[str]:
    """This machine's IPv4 addresses, for the watch app's setting."""
    ips = set()
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ips.add(info[4][0])
    except OSError:
        pass
    try:
        # The address the default route uses. A UDP connect sends nothing.
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("192.0.2.1", 9))
        ips.add(s.getsockname()[0])
        s.close()
    except OSError:
        pass
    return sorted(ip for ip in ips if not ip.startswith("127."))


def fake() -> None:
    """A wandering resting-to-working heart rate, every 5 s."""
    bpm = 74.0
    while True:
        bpm = max(58, min(165, bpm + random.uniform(-6, 7)))
        STATE.put(round(bpm), now_ms(), "--fake")
        time.sleep(5)


def main() -> None:
    sys.stdout.reconfigure(errors="backslashreplace", line_buffering=True)
    ap = argparse.ArgumentParser(prog="heart-bridge", description=__doc__.split("\n\n")[0])
    ap.add_argument("--port", type=int, default=load_contract()["ports"]["heart"])
    ap.add_argument("--host", default="0.0.0.0",
                    help="interface to listen on; 127.0.0.1 tests without the "
                         "firewall prompt, but then the watch cannot reach it")
    ap.add_argument("--fake", action="store_true",
                    help="post a synthetic heart rate every 5 s -- for testing without the watch")
    a = ap.parse_args()

    class Server(ThreadingHTTPServer):
        # On Windows SO_REUSEADDR lets a second bridge bind the same port
        # without an error; one of them would then get nothing.
        allow_reuse_address = not sys.platform.startswith("win")
        daemon_threads = True

    try:
        # Every interface by default, not 127.0.0.1: the watch is another
        # device.
        srv = Server((a.host, a.port), Handler)
    except OSError as e:
        print("error: cannot listen on port %d (%s) -- is another heart-bridge "
              "already running?" % (a.port, e), flush=True)
        sys.exit(2)
    threading.Thread(target=STATE.watch, name="watch", daemon=True).start()
    if a.fake:
        threading.Thread(target=fake, name="fake", daemon=True).start()
        log("--fake: a synthetic heart rate every 5 s")
    ips = lan_addresses() if a.host == "0.0.0.0" else [a.host]
    log("listening on port %d. The watch app posts to %s" % (
        a.port, ", ".join("http://%s:%d/hr" % (ip, a.port) for ip in ips)
        or "http://<this PC's address>:%d/hr" % a.port))
    log("pages read http://127.0.0.1:%d/events" % a.port)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()

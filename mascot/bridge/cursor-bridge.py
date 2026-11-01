#!/usr/bin/env python3
"""
cursor-bridge -- pushes the OS cursor position to the mascot browser source.

OBS browser sources receive no mouse events from your desktop; the only mouse
input they ever see comes from the Interact window. So the cursor position has
to be read outside the browser and pushed in.

This does both jobs in one process:
  * serves the mascot over HTTP, so OBS has one URL to point at: the shared
    page and sprite sets in mascot/, and each overlay's placement files in
    overlays/<name>/mascot/ -- nothing else in the repo
  * streams the cursor over Server-Sent Events at /cursor

Standard library only -- no pip install. macOS reads CGEventGetLocation through
ctypes (no Accessibility permission needed, it is a poll rather than an event
tap); Windows reads GetCursorPos from user32. Both report the position
normalised to 0..1 within one display, so every platform difference dies here
and the page sees one shape of data.

    python3 cursor-bridge.py
    python3 cursor-bridge.py --list-displays
    python3 cursor-bridge.py --display 1 --port 4460

Then point an OBS browser source at:
    http://127.0.0.1:4460/mascot/mascot.html?set=deer&overlay=hi-fi-rush
"""

from __future__ import annotations

import argparse
import ctypes
import ctypes.util
import json
import posixpath
import re
import sys
import threading
import time
import urllib.parse
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

# The repo root, because placement belongs to an overlay and the sprite sets
# do not. SERVED keeps it to the mascot's own files: the root also holds the
# blocklist, the venv and .git, none of which a loopback port should hand out.
WEB_ROOT = Path(__file__).resolve().parent.parent.parent
SERVED = re.compile(r"^/(mascot|overlays/[\w-]+/mascot)/")


# ---------------------------------------------------------------------------
# platform cursor readers


class MacCursor:
    """CGEventGetLocation. Top-left origin, y down -- same as Windows."""

    name = "macOS / CoreGraphics"

    class _Point(ctypes.Structure):
        _fields_ = [("x", ctypes.c_double), ("y", ctypes.c_double)]

    class _Rect(ctypes.Structure):
        _fields_ = [("x", ctypes.c_double), ("y", ctypes.c_double),
                    ("w", ctypes.c_double), ("h", ctypes.c_double)]

    def __init__(self) -> None:
        lib = (ctypes.util.find_library("ApplicationServices") or
               "/System/Library/Frameworks/ApplicationServices.framework"
               "/ApplicationServices")
        cg = ctypes.cdll.LoadLibrary(lib)
        cg.CGEventCreate.restype = ctypes.c_void_p
        cg.CGEventCreate.argtypes = [ctypes.c_void_p]
        cg.CGEventGetLocation.restype = self._Point
        cg.CGEventGetLocation.argtypes = [ctypes.c_void_p]
        cg.CGDisplayBounds.restype = self._Rect
        cg.CGDisplayBounds.argtypes = [ctypes.c_uint32]
        cg.CGGetActiveDisplayList.argtypes = [
            ctypes.c_uint32, ctypes.POINTER(ctypes.c_uint32),
            ctypes.POINTER(ctypes.c_uint32)]
        self.cg = cg
        self.core = ctypes.cdll.LoadLibrary(
            ctypes.util.find_library("CoreFoundation") or "CoreFoundation")
        self.core.CFRelease.argtypes = [ctypes.c_void_p]

    def displays(self) -> list:
        ids = (ctypes.c_uint32 * 16)()
        count = ctypes.c_uint32(0)
        self.cg.CGGetActiveDisplayList(16, ids, ctypes.byref(count))
        out = []
        for i in range(count.value):
            b = self.cg.CGDisplayBounds(ids[i])
            out.append((b.x, b.y, b.w, b.h))
        return out

    def position(self) -> tuple:
        ev = self.cg.CGEventCreate(None)
        pt = self.cg.CGEventGetLocation(ev)
        if ev:
            self.core.CFRelease(ctypes.c_void_p(ev))
        return pt.x, pt.y


class WinCursor:
    """GetCursorPos. Physical pixels once the process is DPI aware."""

    name = "Windows / user32"

    class _Point(ctypes.Structure):
        _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]

    class _Rect(ctypes.Structure):
        _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long),
                    ("right", ctypes.c_long), ("bottom", ctypes.c_long)]

    def __init__(self) -> None:
        self.u32 = ctypes.windll.user32
        # Without this, GetCursorPos and the monitor rects can land in
        # different coordinate spaces on a scaled display.
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except Exception:
            try:
                self.u32.SetProcessDPIAware()
            except Exception:
                pass

    def displays(self) -> list:
        found = []
        proto = ctypes.WINFUNCTYPE(
            ctypes.c_int, ctypes.c_void_p, ctypes.c_void_p,
            ctypes.POINTER(self._Rect), ctypes.c_double)

        def cb(_h, _dc, rect, _p):
            r = rect.contents
            found.append((float(r.left), float(r.top),
                          float(r.right - r.left), float(r.bottom - r.top)))
            return 1

        self.u32.EnumDisplayMonitors(None, None, proto(cb), 0)
        # primary (origin at 0,0) first, so --display 0 means the same thing
        # it does on macOS
        found.sort(key=lambda d: (d[0] != 0 or d[1] != 0, d[0], d[1]))
        return found or [(0.0, 0.0,
                          float(self.u32.GetSystemMetrics(0)),
                          float(self.u32.GetSystemMetrics(1)))]

    def position(self) -> tuple:
        pt = self._Point()
        self.u32.GetCursorPos(ctypes.byref(pt))
        return float(pt.x), float(pt.y)


def make_reader():
    if sys.platform == "darwin":
        return MacCursor()
    if sys.platform.startswith("win"):
        return WinCursor()
    sys.exit("error: unsupported platform %r (macOS and Windows only)"
             % sys.platform)


# ---------------------------------------------------------------------------
# shared state


class Tracker:
    def __init__(self, reader, display: int, hz: float) -> None:
        self.reader = reader
        self.hz = hz
        rects = reader.displays()
        if display >= len(rects):
            sys.exit("error: no display %d (found %d)" % (display, len(rects)))
        self.dx, self.dy, self.dw, self.dh = rects[display]
        self.value = (0.5, 0.5)
        self.seq = 0
        self.lock = threading.Lock()

    def run(self) -> None:
        period = 1.0 / self.hz
        while True:
            x, y = self.reader.position()
            u = min(1.0, max(0.0, (x - self.dx) / self.dw))
            v = min(1.0, max(0.0, (y - self.dy) / self.dh))
            with self.lock:
                if abs(u - self.value[0]) > 1e-4 or abs(v - self.value[1]) > 1e-4:
                    self.value = (u, v)
                    self.seq += 1
            time.sleep(period)

    def read(self) -> tuple:
        with self.lock:
            return self.value, self.seq


# ---------------------------------------------------------------------------
# http


class Handler(SimpleHTTPRequestHandler):
    tracker: Tracker = None          # set in main

    def log_message(self, *_a) -> None:
        pass                          # quiet; this runs behind OBS

    def end_headers(self) -> None:
        # the page may be loaded from file:// during testing
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Cache-Control", "no-store")
        SimpleHTTPRequestHandler.end_headers(self)

    def _served(self) -> bool:
        path = posixpath.normpath(urllib.parse.unquote(self.path.split("?")[0]))
        if SERVED.match(path + "/"):
            return True
        self.send_error(404)
        return False

    def do_GET(self) -> None:
        if self.path.split("?")[0] == "/cursor":
            return self._stream()
        if self._served():
            SimpleHTTPRequestHandler.do_GET(self)

    def do_HEAD(self) -> None:
        if self._served():
            SimpleHTTPRequestHandler.do_HEAD(self)

    def _stream(self) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Connection", "keep-alive")
        self.end_headers()
        last = -1
        beat = 0.0
        try:
            while True:
                (u, v), seq = self.tracker.read()
                now = time.time()
                # resend on a heartbeat too, so a client that connected while
                # the cursor was still knows where it is
                if seq != last or now - beat > 1.0:
                    last, beat = seq, now
                    self.wfile.write(
                        ("data: %s\n\n" % json.dumps(
                            {"x": round(u, 5), "y": round(v, 5)})).encode())
                    self.wfile.flush()
                time.sleep(1.0 / self.tracker.hz)
        except (BrokenPipeError, ConnectionResetError):
            pass                      # OBS closed the source; normal


# ---------------------------------------------------------------------------


def main() -> None:
    try:
        sys.stdout.reconfigure(line_buffering=True)
    except Exception:
        pass
    ap = argparse.ArgumentParser(prog="cursor-bridge")
    ap.add_argument("--port", type=int, default=4460)
    ap.add_argument("--display", type=int, default=0,
                    help="which display to normalise against (see --list-displays)")
    ap.add_argument("--hz", type=float, default=60.0)
    ap.add_argument("--list-displays", action="store_true")
    a = ap.parse_args()

    reader = make_reader()
    if a.list_displays:
        print("reader: %s" % reader.name)
        for i, (x, y, w, h) in enumerate(reader.displays()):
            print("  display %d: %.0fx%.0f at %.0f,%.0f" % (i, w, h, x, y))
        return

    tracker = Tracker(reader, a.display, a.hz)
    Handler.tracker = tracker
    threading.Thread(target=tracker.run, daemon=True).start()

    handler = partial(Handler, directory=str(WEB_ROOT))
    # 127.0.0.1, never 0.0.0.0 -- binding to all interfaces trips the Windows
    # Firewall dialog on every new machine
    srv = ThreadingHTTPServer(("127.0.0.1", a.port), handler)
    srv.daemon_threads = True

    print("cursor-bridge running")
    print("  reader   %s" % reader.name)
    print("  display  %.0fx%.0f at %.0f,%.0f"
          % (tracker.dw, tracker.dh, tracker.dx, tracker.dy))
    print("  serving  %s" % WEB_ROOT)
    print()
    print("  OBS browser source URL:")
    print("    http://127.0.0.1:%d/mascot/mascot.html?set=deer&overlay=hi-fi-rush"
          % a.port)
    print()
    print("  ctrl-C to stop")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")


if __name__ == "__main__":
    main()

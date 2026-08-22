#!/usr/bin/env python3
"""
obs-setup -- build (or repair) this overlay's OBS scene collection.

Everything the overlay needs on the OBS side is derivable: one host scene
called COMIC holding the video sources plus two browser sources, and six
trigger scenes that contain nothing but a nested reference to COMIC. This
script asserts that shape over obs-websocket, so moving to another machine is
"install OBS, enable the websocket, run this" rather than forty minutes of
clicking. See CLAUDE.md §2 for why the shape is what it is.

    python3 tools/obs-setup.py --check          report, change nothing
    python3 tools/obs-setup.py                  create and repair
    python3 tools/obs-setup.py --placeholders   colour blocks, no hardware
    python3 tools/obs-setup.py --prune          also remove strays from COMIC
    python3 tools/obs-setup.py --export         write obs/comic-scenes.json

Standard library only -- no pip install. The obs-websocket client below is
about eighty lines because a dependency you have to explain in a README is
worse than eighty lines you can read.

It is idempotent and conservative: it creates what is missing and repositions
what is misplaced, but it never deletes a source or overwrites one that exists
with a different kind. Those are reported for you to decide about, because a
script that silently replaces your webcam source is a script that eventually
eats a working setup.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import socket
import struct
import sys
import time
import urllib.parse
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

CANVAS_W, CANVAS_H = 1920, 1080

HOST_SCENE = "COMIC"

# Scene name -> the panel it pans to. Must match SCENE_MAP in overlay.html.
TRIGGERS = ["START", "CHAT", "GAME", "CAM", "BRB", "END"]

# Bottom to top. The video sources sit under the overlay so its art can mask
# their spill; the mascot sits over it, because a mascot punched through as a
# hole would be a transparent rectangle instead of a sprite on comic art.
MASCOT_PORT = 4460


def stack(placeholders: bool):
    """The COMIC scene, bottom item first."""
    video = "color_source_v3" if placeholders else None
    win = sys.platform.startswith("win")
    return [
        # name        real kind                              placeholder colour
        ("Standby", video or "ffmpeg_source", 0xFF858585),
        ("Game", video or ("game_capture" if win else "screen_capture"), 0xFF10DA16),
        ("Cam", video or ("dshow_input" if win else "av_capture_input_v2"), 0xFF3C8BDA),
        ("Chat", video or "browser_source", 0xFFDA2624),
        ("Overlay", "browser_source", None),
        ("Deer", "browser_source", None),
    ]


# Sources the overlay positions through obs-websocket. Anything else in COMIC
# is a stray as far as this script is concerned.
MANAGED = {"Standby", "Game", "Cam", "Chat", "Overlay", "Deer"}


# ---------------------------------------------------------------------------
# a very small websocket client


class WS:
    """Text-frame websocket client. Enough for obs-websocket v5, no more."""

    def __init__(self, host: str, port: int, timeout: float = 10.0) -> None:
        self.sock = socket.create_connection((host, port), timeout=timeout)
        key = base64.b64encode(os.urandom(16)).decode()
        self.sock.sendall(
            (
                "GET / HTTP/1.1\r\n"
                f"Host: {host}:{port}\r\n"
                "Upgrade: websocket\r\n"
                "Connection: Upgrade\r\n"
                f"Sec-WebSocket-Key: {key}\r\n"
                "Sec-WebSocket-Version: 13\r\n"
                "\r\n"
            ).encode()
        )
        head = b""
        while b"\r\n\r\n" not in head:
            chunk = self.sock.recv(1)
            if not chunk:
                raise ConnectionError("server closed during handshake")
            head += chunk
        if b"101" not in head.split(b"\r\n")[0]:
            raise ConnectionError("handshake refused: %s" % head.split(b"\r\n")[0])
        self.buf = b""

    def _recv_exact(self, n: int) -> bytes:
        while len(self.buf) < n:
            chunk = self.sock.recv(65536)
            if not chunk:
                raise ConnectionError("server closed")
            self.buf += chunk
        out, self.buf = self.buf[:n], self.buf[n:]
        return out

    def send(self, obj) -> None:
        payload = json.dumps(obj).encode()
        n = len(payload)
        header = bytearray([0x81])  # FIN + text
        if n < 126:
            header.append(0x80 | n)
        elif n < 1 << 16:
            header.append(0x80 | 126)
            header += struct.pack(">H", n)
        else:
            header.append(0x80 | 127)
            header += struct.pack(">Q", n)
        mask = os.urandom(4)
        header += mask
        self.sock.sendall(
            bytes(header) + bytes(b ^ mask[i % 4] for i, b in enumerate(payload))
        )

    def recv(self):
        while True:
            b0, b1 = self._recv_exact(2)
            opcode = b0 & 0x0F
            n = b1 & 0x7F
            if n == 126:
                n = struct.unpack(">H", self._recv_exact(2))[0]
            elif n == 127:
                n = struct.unpack(">Q", self._recv_exact(8))[0]
            data = self._recv_exact(n) if n else b""
            if opcode == 0x9:  # ping
                self.sock.sendall(bytes([0x8A, 0x80]) + os.urandom(4))
                continue
            if opcode == 0x8:  # close
                raise ConnectionError("server closed the socket")
            if opcode in (0x1, 0x2):
                return json.loads(data)

    def close(self) -> None:
        try:
            self.sock.close()
        except Exception:
            pass


class OBS:
    def __init__(self, host: str, port: int, password: str) -> None:
        self.ws = WS(host, port)
        hello = self.ws.recv()
        d = {"rpcVersion": 1, "eventSubscriptions": 0}
        auth = hello["d"].get("authentication")
        if auth:
            if not password:
                raise SystemExit(
                    "error: this obs-websocket wants a password and none was found.\n"
                    "       pass --password, set OBS_WS_PASSWORD, or let the script\n"
                    "       read it from OBS's own config (see --help)."
                )
            secret = base64.b64encode(
                hashlib.sha256((password + auth["salt"]).encode()).digest()
            ).decode()
            d["authentication"] = base64.b64encode(
                hashlib.sha256((secret + auth["challenge"]).encode()).digest()
            ).decode()
        self.ws.send({"op": 1, "d": d})
        got = self.ws.recv()
        if got.get("op") != 2:
            raise SystemExit("error: obs-websocket refused the password")
        self.n = 0

    def req(self, kind: str, data=None):
        self.n += 1
        rid = "s%d" % self.n
        self.ws.send(
            {"op": 6, "d": {"requestType": kind, "requestId": rid,
                            "requestData": data or {}}}
        )
        while True:
            m = self.ws.recv()
            if m.get("op") == 7 and m["d"]["requestId"] == rid:
                st = m["d"]["requestStatus"]
                if not st["result"]:
                    raise ObsError(kind, st.get("comment") or st.get("code"))
                return m["d"].get("responseData") or {}


class ObsError(RuntimeError):
    def __init__(self, kind, comment):
        super().__init__("%s failed: %s" % (kind, comment))


# ---------------------------------------------------------------------------
# password discovery


def obs_config_dir() -> Path:
    if sys.platform == "darwin":
        return Path.home() / "Library/Application Support/obs-studio"
    if sys.platform.startswith("win"):
        return Path(os.environ.get("APPDATA", "")) / "obs-studio"
    return Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "obs-studio"


def discover_password() -> str:
    """Read the password OBS generated for itself on this machine.

    The password is per-install, so it can never live in the repo. Reading it
    from OBS's own config is what makes `run the script` work on a new machine
    without the user hunting through Tools -> WebSocket Server Settings.
    """
    cfg = obs_config_dir() / "plugin_config/obs-websocket/config.json"
    try:
        return json.loads(cfg.read_text()).get("server_password", "")
    except Exception:
        return ""


# ---------------------------------------------------------------------------
# export


EXPORT_DEFAULT = REPO / "obs" / "comic-scenes.json"

# Query parameters and settings keys that carry a credential. Scrubbed by name
# rather than by value, so this never has to know what the secret actually is.
SECRET_PARAMS = {"pw", "password", "passwd", "key", "token", "auth", "secret"}
SECRET_KEYS = {"password", "server_password", "key", "stream_key", "token",
               "auth_token", "secret", "bearer_token"}

REPO_TOKEN = "{{REPO}}"
HOME_TOKEN = "{{HOME}}"


def collection_path(name: str = "") -> Path:
    """The scene collection OBS has on disk.

    OBS autosaves every few minutes and on a clean quit, so this can lag your
    last change. The caller reports the file's mtime for exactly that reason.
    """
    d = obs_config_dir() / "basic/scenes"
    files = sorted(p for p in d.glob("*.json") if p.suffix == ".json")
    if not files:
        raise SystemExit("error: no scene collection found in %s" % d)
    if name:
        for f in files:
            try:
                if json.loads(f.read_text()).get("name") == name:
                    return f
            except Exception:
                pass
        raise SystemExit("error: no collection named %r in %s" % (name, d))
    if len(files) > 1:
        raise SystemExit(
            "error: %d collections in %s -- name the one you want with "
            "--collection\n       %s"
            % (len(files), d, ", ".join(f.stem for f in files))
        )
    return files[0]


def scrub_url(url: str) -> str:
    """Drop credential query params, and tokenise anything machine-specific."""
    if not isinstance(url, str) or not url:
        return url
    parts = urllib.parse.urlsplit(url)
    kept = [(k, v) for k, v in urllib.parse.parse_qsl(parts.query, keep_blank_values=True)
            if k.lower() not in SECRET_PARAMS]
    url = urllib.parse.urlunsplit(
        (parts.scheme, parts.netloc, parts.path,
         urllib.parse.urlencode(kept), parts.fragment)
    )
    # file:// urls into this repo become a token. obs-setup.py rewrites them to
    # the real path on whatever machine imports the collection.
    repo_uri = REPO.as_uri()
    if url.startswith(repo_uri):
        url = REPO_TOKEN + url[len(repo_uri):]
    return url


def scrub(node):
    """Recursively strip secrets, repo paths and home paths."""
    if isinstance(node, dict):
        out = {}
        for k, v in node.items():
            if k.lower() in SECRET_KEYS:
                out[k] = ""
            elif k == "url":
                out[k] = scrub_url(v)
            else:
                out[k] = scrub(v)
        return out
    if isinstance(node, list):
        return [scrub(v) for v in node]
    if isinstance(node, str):
        # Catches anything the structured rules missed -- module settings,
        # recording paths, script paths. Your username is not repo content.
        home = str(Path.home())
        for raw, token in ((REPO.as_uri(), REPO_TOKEN), (str(REPO), REPO_TOKEN),
                           (Path.home().as_uri(), HOME_TOKEN), (home, HOME_TOKEN)):
            node = node.replace(raw, token)
            node = node.replace(urllib.parse.quote(raw), token)
        return node
    return node


def live_shape(a):
    """The COMIC stack as OBS has it *right now*, or None if OBS is not up.

    Only used to catch a stale file. Export itself needs no websocket.
    """
    try:
        obs = OBS(a.host, a.port, a.password or discover_password())
    except Exception:
        return None
    try:
        scenes = {x["sceneName"] for x in obs.req("GetSceneList")["scenes"]}
        items = obs.req("GetSceneItemList", {"sceneName": HOST_SCENE})["sceneItems"]
        stack_ = [i["sourceName"] for i in
                  sorted(items, key=lambda i: i["sceneItemIndex"])]
        return scenes, stack_
    except ObsError:
        return None
    finally:
        obs.ws.close()


def file_shape(doc):
    scenes = {x["name"] for x in doc.get("sources", []) if x.get("id") == "scene"}
    comic = next((x for x in doc.get("sources", [])
                  if x.get("name") == HOST_SCENE and x.get("id") == "scene"), None)
    stack_ = [i["name"] for i in comic.get("settings", {}).get("items", [])] if comic else []
    return scenes, stack_


def do_export(a) -> None:
    src = Path(a.export_from) if a.export_from else collection_path(a.collection)
    out = Path(a.out) if a.out else EXPORT_DEFAULT

    raw = json.loads(src.read_text())
    age = time.time() - src.stat().st_mtime

    # OBS keeps the collection in memory and writes it out on its own schedule,
    # so the file on disk can be minutes behind what you are looking at. An
    # export of a stale file is worse than no export -- it looks right and
    # ships the setup you already fixed. Compare against the live scene graph
    # and refuse rather than warn.
    if not a.export_from:
        live = live_shape(a)
        if live and live != file_shape(raw):
            ls, lstack = live
            fs, fstack = file_shape(raw)
            raise SystemExit(
                "error: %s is stale -- OBS has changes it has not written out yet.\n"
                "\n"
                "       on disk : %s\n"
                "       in OBS  : %s\n"
                "%s"
                "\n"
                "       Quit OBS (it saves on a clean exit) and run this again, or use\n"
                "       Scene Collection -> Export in OBS and pass --export-from <file>."
                % (
                    src.name,
                    " < ".join(fstack) or "(no %s scene)" % HOST_SCENE,
                    " < ".join(lstack) or "(no %s scene)" % HOST_SCENE,
                    ("       scenes  : on disk %s, in OBS %s\n"
                     % (sorted(fs), sorted(ls))) if fs != ls else "",
                )
            )

    clean = scrub(raw)

    # OBS names the imported collection after this field, and "Untitled" is a
    # poor thing to hand someone. Landing on START also beats importing into
    # whatever scene happened to be live when the file was written.
    clean["name"] = a.name
    if HOST_SCENE in [x.get("name") for x in clean.get("sources", [])]:
        clean["current_scene"] = "START"
        clean["current_program_scene"] = "START"

    # Belt and braces: never write a file that still looks like it holds a
    # credential. Structural scrubbing above should make this unreachable.
    blob = json.dumps(clean)
    leaks = [p for p in SECRET_PARAMS if ("%s=" % p) in blob and
             not blob.count("%s=&" % p) and not blob.count('%s="' % p)]
    if str(Path.home()) in blob:
        leaks.append("home path")
    if leaks:
        raise SystemExit(
            "error: refusing to write %s -- it still looks like it contains %s.\n"
            "       This is a bug in obs-setup.py; do not commit the file."
            % (out, ", ".join(sorted(set(leaks))))
        )

    unmanaged = sorted(
        {i["name"] for s2 in clean.get("sources", [])
         if s2.get("id") == "scene" and s2.get("name") == HOST_SCENE
         for i in s2.get("settings", {}).get("items", [])}
        - MANAGED
    )

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(clean, indent=2, ensure_ascii=False) + "\n")

    print("exported %s" % out)
    print("  from      %s" % src)
    print("  collection %r, %d scenes, %d sources"
          % (clean.get("name"), sum(1 for x in clean.get("sources", [])
                                    if x.get("id") == "scene"),
             sum(1 for x in clean.get("sources", [])
                 if x.get("id") != "scene")))
    print("  saved     %d min ago by OBS" % (age // 60))
    print("  scrubbed  credential query params, %s -> %s, home -> %s"
          % (REPO, REPO_TOKEN, HOME_TOKEN))

    if age > 300 and a.export_from:
        print("\n  ! that file is %d min old, and --export-from skips the staleness"
              % (age // 60))
        print("    check against the running OBS. Make sure it is the one you meant.")
    if unmanaged:
        print("\n  ! %s sits in %s but no hole maps to it, so this export bakes in a"
              % (", ".join(unmanaged), HOST_SCENE))
        print("    source that shows through whichever hole it overlaps. Run with")
        print("    --prune first if you did not mean to keep it.")


# ---------------------------------------------------------------------------


class Plan:
    def __init__(self, check: bool) -> None:
        self.check = check
        self.actions: list[str] = []
        self.warnings: list[str] = []

    def do(self, what: str, fn) -> None:
        self.actions.append(what)
        if not self.check:
            fn()

    def warn(self, what: str) -> None:
        self.warnings.append(what)


def browser_settings(name: str, pw: str) -> dict:
    if name == "Overlay":
        # file:// on purpose: the overlay must keep working when the mascot
        # bridge is not running. See README, "Why the overlay is file:// and
        # the mascot is http://".
        url = (REPO / "overlay.html").as_uri()
        if pw:
            url += "?pw=" + urllib.parse.quote(pw)
        return {
            "url": url,
            "width": CANVAS_W,
            "height": CANVAS_H,
            "shutdown": False,          # keep state across scene switches
            "restart_when_active": False,
            "reroute_audio": True,      # alert audio rides the browser source
        }
    if name == "Deer":
        url = "http://127.0.0.1:%d/mascot.html?set=deer" % MASCOT_PORT
        if pw:
            url += "&pw=" + urllib.parse.quote(pw)
        return {
            "url": url,
            "width": CANVAS_W,
            "height": CANVAS_H,
            "shutdown": False,
            "restart_when_active": False,
            "reroute_audio": False,
        }
    if name == "Chat":
        return {"url": "about:blank", "width": 800, "height": 1200,
                "shutdown": False, "restart_when_active": False}
    return {}


def main() -> None:
    ap = argparse.ArgumentParser(
        prog="obs-setup",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__.split("Standard library only")[0].strip(),
    )
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=4455)
    ap.add_argument("--password", default=os.environ.get("OBS_WS_PASSWORD", ""),
                    help="defaults to $OBS_WS_PASSWORD, then OBS's own config file")
    ap.add_argument("--check", action="store_true",
                    help="report what would change and exit non-zero if anything would")
    ap.add_argument("--placeholders", action="store_true",
                    help="create missing video sources as colour blocks, for a "
                         "machine with no capture hardware yet")
    ap.add_argument("--prune", action="store_true",
                    help="remove items from COMIC that this overlay does not manage")
    ap.add_argument("--export", action="store_true",
                    help="write a sanitised copy of the scene collection to "
                         "obs/comic-scenes.json and exit. Strips credentials and "
                         "machine paths, so the result is safe to commit")
    ap.add_argument("--out", default="",
                    help="--export: where to write (default obs/comic-scenes.json)")
    ap.add_argument("--export-from", dest="export_from", default="",
                    help="--export: sanitise this file instead of OBS's live one, "
                         "e.g. something you made with Scene Collection -> Export")
    ap.add_argument("--collection", default="",
                    help="--export: which collection, if you have more than one")
    ap.add_argument("--name", default="Comic Overlay",
                    help="--export: the name OBS will show for the imported "
                         "collection (default: Comic Overlay)")
    a = ap.parse_args()

    # Export reads a file. It deliberately does not need OBS running, or the
    # websocket, or a password -- you may well be exporting after quitting OBS
    # to force it to write the collection out.
    if a.export:
        return do_export(a)

    pw = a.password or discover_password()

    try:
        obs = OBS(a.host, a.port, pw)
    except (ConnectionRefusedError, OSError) as e:
        raise SystemExit(
            "error: could not reach obs-websocket at %s:%d (%s)\n"
            "       is OBS running, and is Tools -> WebSocket Server Settings\n"
            "       -> Enable WebSocket server ticked?" % (a.host, a.port, e)
        )

    plan = Plan(a.check)
    layout = stack(a.placeholders)

    # --- canvas ------------------------------------------------------------
    v = obs.req("GetVideoSettings")
    if (v["baseWidth"], v["baseHeight"]) != (CANVAS_W, CANVAS_H):
        plan.warn(
            "canvas is %dx%d, this overlay assumes %dx%d -- every hole rect it "
            "pushes is in canvas pixels, so fix this in Settings -> Video first"
            % (v["baseWidth"], v["baseHeight"], CANVAS_W, CANVAS_H)
        )

    preflight(plan)

    # --- scenes ------------------------------------------------------------
    scenes = {s["sceneName"] for s in obs.req("GetSceneList")["scenes"]}

    if HOST_SCENE not in scenes:
        plan.do("create scene %s" % HOST_SCENE,
                lambda: obs.req("CreateScene", {"sceneName": HOST_SCENE}))
        scenes.add(HOST_SCENE)

    for name in TRIGGERS:
        if name not in scenes:
            plan.do("create scene %s" % name,
                    lambda n=name: obs.req("CreateScene", {"sceneName": n}))

    # --- inputs ------------------------------------------------------------
    inputs = {i["inputName"]: i["inputKind"] for i in obs.req("GetInputList")["inputs"]}
    kinds = set(obs.req("GetInputKindList")["inputKinds"])

    for name, kind, colour in layout:
        if name in inputs:
            if inputs[name] != kind:
                plan.warn(
                    "%s exists as %s, not %s -- left alone. Delete it in OBS and "
                    "re-run if you want this script to make it."
                    % (name, inputs[name], kind)
                )
            continue
        if kind not in kinds:
            plan.warn("%s: this OBS has no %s input kind -- creating a colour "
                      "placeholder instead" % (name, kind))
            kind, colour = "color_source_v3", colour or 0xFF404040

        settings = browser_settings(name, pw)
        if kind == "color_source_v3":
            settings = {"color": colour or 0xFF404040,
                        "width": CANVAS_W, "height": CANVAS_H}
        plan.do(
            "create input %s (%s)" % (name, kind),
            lambda n=name, k=kind, s=settings: obs.req(
                "CreateInput",
                {"sceneName": HOST_SCENE, "inputName": n,
                 "inputKind": k, "inputSettings": s, "sceneItemEnabled": True},
            ),
        )

    # Browser settings are asserted every run: a wrong url, or "Shutdown source
    # when not visible" left ticked, breaks the overlay in ways that look like
    # an overlay bug.
    for name in ("Overlay", "Deer", "Chat"):
        want = browser_settings(name, pw)
        if not want or inputs.get(name) != "browser_source":
            continue
        if name == "Chat":
            want = {k: want[k] for k in ("shutdown", "restart_when_active")}
        have = obs.req("GetInputSettings", {"inputName": name})["inputSettings"]
        diff = {k: v for k, v in want.items() if have.get(k) != v}
        # OBS omits defaults from the settings blob, so absent == the default.
        diff = {k: v for k, v in diff.items() if not (k not in have and v is False)}
        if diff:
            plan.do(
                "%s: set %s" % (name, ", ".join(sorted(diff))),
                lambda n=name, d=diff: obs.req(
                    "SetInputSettings", {"inputName": n, "inputSettings": d}),
            )

    if a.check and any(x.startswith("create input") for x in plan.actions):
        # Nothing below can be checked meaningfully against sources that do not
        # exist yet, so stop here rather than print a wall of noise.
        report(plan, a)
        return

    # --- COMIC contents and z-order ---------------------------------------
    items = obs.req("GetSceneItemList", {"sceneName": HOST_SCENE})["sceneItems"]
    by_name = {i["sourceName"]: i for i in items}

    for name in [n for n, _, _ in layout]:
        if name not in by_name:
            plan.do(
                "add %s to %s" % (name, HOST_SCENE),
                lambda n=name: obs.req(
                    "CreateSceneItem",
                    {"sceneName": HOST_SCENE, "sourceName": n, "sceneItemEnabled": True},
                ),
            )

    strays = sorted(set(by_name) - MANAGED)
    for name in strays:
        if a.prune:
            plan.do(
                "remove %s from %s" % (name, HOST_SCENE),
                lambda i=by_name[name]["sceneItemId"]: obs.req(
                    "RemoveSceneItem",
                    {"sceneName": HOST_SCENE, "sceneItemId": i}),
            )
        else:
            plan.warn(
                "%s sits in %s but no hole maps to it. It renders behind the "
                "overlay and shows through whatever hole it happens to overlap. "
                "Re-run with --prune to remove it." % (name, HOST_SCENE)
            )

    # Index 0 is the bottom of the list. Set every item explicitly rather than
    # computing a minimal set of moves: it is six requests, once.
    if not a.check or all(n in by_name for n, _, _ in layout):
        items = obs.req("GetSceneItemList", {"sceneName": HOST_SCENE})["sceneItems"]
        by_name = {i["sourceName"]: i for i in items}
        want_order = [n for n, _, _ in layout if n in by_name]
        have_order = [i["sourceName"] for i in
                      sorted(items, key=lambda i: i["sceneItemIndex"])
                      if i["sourceName"] in want_order]
        if have_order != want_order:
            plan.do(
                "restack %s: %s" % (HOST_SCENE, " < ".join(want_order)),
                lambda: [
                    obs.req("SetSceneItemIndex",
                            {"sceneName": HOST_SCENE,
                             "sceneItemId": by_name[n]["sceneItemId"],
                             "sceneItemIndex": i})
                    for i, n in enumerate(want_order)
                ],
            )

    # --- trigger scenes ----------------------------------------------------
    # Each holds exactly one item: COMIC, filling the canvas. The nesting is
    # the whole trick -- the browser source is never torn down, so animation
    # and websocket state survive every switch.
    want_tf = {
        "positionX": 0.0, "positionY": 0.0, "rotation": 0.0, "alignment": 5,
        "boundsType": "OBS_BOUNDS_SCALE_INNER", "boundsAlignment": 0,
        "boundsWidth": float(CANVAS_W), "boundsHeight": float(CANVAS_H),
        "cropLeft": 0, "cropRight": 0, "cropTop": 0, "cropBottom": 0,
    }
    for name in TRIGGERS:
        try:
            tit = obs.req("GetSceneItemList", {"sceneName": name})["sceneItems"]
        except ObsError:
            continue                       # only just scheduled for creation
        host = next((i for i in tit if i["sourceName"] == HOST_SCENE), None)
        if host is None:
            plan.do(
                "add %s to %s" % (HOST_SCENE, name),
                lambda n=name: obs.req(
                    "CreateSceneItem",
                    {"sceneName": n, "sourceName": HOST_SCENE,
                     "sceneItemEnabled": True}),
            )
            continue
        tf = host["sceneItemTransform"]
        if any(abs(float(tf.get(k, 0)) - float(vv)) > 0.5
               if isinstance(vv, float) else tf.get(k) != vv
               for k, vv in want_tf.items()):
            plan.do(
                "%s: square %s up to the canvas" % (name, HOST_SCENE),
                lambda n=name, i=host["sceneItemId"]: obs.req(
                    "SetSceneItemTransform",
                    {"sceneName": n, "sceneItemId": i,
                     "sceneItemTransform": want_tf}),
            )
        for extra in [i for i in tit if i["sourceName"] != HOST_SCENE]:
            plan.warn("%s holds %s as well as %s -- a trigger scene should hold "
                      "nothing but the nested host scene"
                      % (name, extra["sourceName"], HOST_SCENE))

    # --- transition --------------------------------------------------------
    # The pan IS the transition. Anything else double-animates the switch.
    tr = obs.req("GetCurrentSceneTransition")
    if tr["transitionKind"] != "cut_transition":
        plan.do(
            "set transition to Cut (was %s)" % tr["transitionName"],
            lambda: obs.req("SetCurrentSceneTransition", {"transitionName": "Cut"}),
        )

    report(plan, a)
    obs.ws.close()


def preflight(plan: Plan) -> None:
    """Read-only checks for the things the websocket cannot set.

    These are not part of the scene graph, so nothing here is repaired -- but
    each one breaks the overlay in a way that looks like an overlay bug, which
    makes them worth naming before you find out live.
    """
    # Browser Source Hardware Acceleration lives in OBS's app-wide global.ini,
    # not in the profile, so there is no websocket request that can reach it.
    ini = obs_config_dir() / "global.ini"
    try:
        for line in ini.read_text(errors="replace").splitlines():
            if line.strip().lower().startswith("browserhwaccel"):
                if line.split("=", 1)[1].strip().lower() != "true":
                    plan.warn(
                        "Browser Source Hardware Acceleration is off. The pan is a "
                        "CSS transform on a 7680x4320 page; without it OBS renders "
                        "that on the CPU and the pan judders. Settings -> Advanced."
                    )
                break
    except OSError:
        pass

    # The mascot's sprite sheet is served BY the bridge, so a missing bridge is
    # not just a still mascot -- it is no mascot at all until it comes up.
    sock = socket.socket()
    sock.settimeout(0.4)
    try:
        sock.connect(("127.0.0.1", MASCOT_PORT))
    except OSError:
        plan.warn(
            "nothing is listening on 127.0.0.1:%d, so the Deer source has no "
            "sprite sheet to load. Start it with:\n"
            "        python3 mascot/bridge/cursor-bridge.py" % MASCOT_PORT
        )
    finally:
        sock.close()

    for rel in ("mascot/mascot.html", "mascot/placement.json",
                "mascot/deer/manifest.json", "overlay.html"):
        if not (REPO / rel).exists():
            plan.warn("%s is missing from the repo" % rel)

    # The sheet the manifest names, whatever it is called.
    try:
        man = json.loads((REPO / "mascot/deer/manifest.json").read_text())
        sheet = REPO / "mascot/deer" / man.get("sheet", "")
        if not sheet.exists():
            plan.warn(
                "mascot/deer/manifest.json names %r but that file is not there. "
                "It is gitignored if it is sheet.png -- only the webp ships."
                % man.get("sheet")
            )
    except Exception:
        pass


def report(plan: Plan, a) -> None:
    if plan.actions:
        print("changes" if not plan.check else "would change")
        for x in plan.actions:
            print("  %s %s" % ("*" if plan.check else "+", x))
    else:
        print("scene collection already matches" if not plan.warnings
              else "scene collection matches")

    if plan.warnings:
        print("\nneeds a look")
        for w in plan.warnings:
            print("  ! %s" % w)

    if not plan.check and plan.actions:
        print("\nOBS does not write the scene collection to disk until it quits "
              "cleanly.\nScene Collection -> Export if you want a copy now.")

    if plan.check and plan.actions:
        sys.exit(1)


if __name__ == "__main__":
    main()

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
    python3 tools/obs-setup.py --vertical       also build VCOMIC on the
                                                vertical canvas
    python3 tools/obs-setup.py --encoder auto   pick the best hardware encoder
                                                OBS reports on this machine

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

# --- vertical canvas -------------------------------------------------------
# A second 1080x1920 canvas, added by the Aitum Vertical Canvas plugin, which
# builds on OBS 32's native canvas API rather than running its own -- which is
# why the standard websocket requests can see into it at all.
#
# Measured on OBS 32.2.2 / obs-websocket 5.7.4: CreateScene, CreateSceneItem,
# SetSceneItemIndex and SetSceneItemTransform all work there, but ONLY by uuid.
# canvasName is silently ignored -- GetSceneList {canvasName: "Aitum Vertical"}
# hands back Main's scene list with no error -- and vertical scenes cannot be
# addressed by sceneName at all, because name lookup resolves within Main only.
# The uuid is random per scene collection, so it is discovered every run and
# never written down. See CLAUDE.md §2.
VERT_W, VERT_H = 1080, 1920

# Not COMIC: OBS shares one source namespace across canvases too, and a scene
# is a source internally.
VERT_SCENE = "VCOMIC"

# Bottom to top. The same inputs COMIC uses -- one input referenced from both
# canvases, with independent scene items, so the horizontal and vertical
# overlays cannot fight over a transform. No trigger scenes here: the vertical
# canvas needs exactly one scene and never switches, because vertical.html
# reads the MAIN canvas's program scene to decide where to pan.
#
# DeerV is last for the same reason Deer is last in COMIC: above the overlay,
# because a punched hole is a transparent rectangle and would put live video
# behind the mascot's own alpha instead of comic art.
VERT_STACK = ["Game", "Cam", "Chat", "OverlayV", "DeerV"]
VERT_MANAGED = set(VERT_STACK)


# --- encoders --------------------------------------------------------------
# The pan is a CSS transform on a 7680x4320 page inside CEF, and Source Record
# adds an output per source on top of the program encode. The CPU has enough to
# do; the encode belongs on the GPU. CLAUDE.md §6 already names encoder count as
# the real ceiling.
#
# Only the encoder ID is asserted here, never bitrate, preset or tuning. Those
# live in the profile's streamEncoder.json / recordEncoder.json, which no
# websocket request can reach -- and they are a judgement call about your
# upload and your GPU, which a repo has no business making for you.

# Pre-OBS-30 IDs. OBS still accepts each one and silently maps it to the value
# on the right, logging "Encoder ID 'x' is deprecated and may be removed in a
# future version" once per output per launch. Rewriting them is a rename, not a
# change of encoder, which is why it happens on an ordinary run.
DEPRECATED_ENCODERS = {
    "jim_nvenc": "obs_nvenc_h264_tex",
    "jim_hevc_nvenc": "obs_nvenc_hevc_tex",
    "jim_av1_nvenc": "obs_nvenc_av1_tex",
    "ffmpeg_nvenc": "obs_nvenc_h264_tex",
    "obs_qsv11": "obs_qsv11_v2",
}

# Best first, for --encoder auto. H.264 only: YouTube and Twitch both take it
# everywhere, and an HEVC or AV1 ingest is a decision about your service, not
# about this overlay.
HW_PREFERENCE = [
    "obs_nvenc_h264_tex",   # NVIDIA
    "obs_qsv11_v2",         # Intel QuickSync
    "h264_texture_amf",     # AMD
    "com.apple.videotoolbox.videoencoder.ave.avc",
    "obs_x264",             # software, and the OBS default
]

# Simple output mode stores a short token instead of the encoder ID.
SIMPLE_TOKEN = {
    "obs_nvenc_h264_tex": "nvenc",
    "obs_qsv11_v2": "qsv",
    "h264_texture_amf": "amd",
    "com.apple.videotoolbox.videoencoder.ave.avc": "apple_h264",
    "obs_x264": "x264",
}
SIMPLE_ID = {v: k for k, v in SIMPLE_TOKEN.items()}
# Simple mode's own deprecated spellings.
SIMPLE_ID.update({"jim_nvenc": "obs_nvenc_h264_tex", "nvenc": "obs_nvenc_h264_tex",
                  "amd_h264": "h264_texture_amf"})

SOFTWARE_ENCODERS = {"obs_x264", "ffmpeg_svt_av1", "ffmpeg_aom_av1"}

# What --encoder accepts. "auto" is the first entry of HW_PREFERENCE this
# machine actually has.
ENCODER_CHOICES = {
    "nvenc": "obs_nvenc_h264_tex",
    "qsv": "obs_qsv11_v2",
    "amd": "h264_texture_amf",
    "apple": "com.apple.videotoolbox.videoencoder.ave.avc",
    "x264": "obs_x264",
}


def stack(placeholders: bool):
    """The COMIC scene, bottom item first."""
    video = "color_source_v3" if placeholders else None
    win = sys.platform.startswith("win")
    return [
        # name        real kind                              placeholder colour
        ("Game", video or ("game_capture" if win else "screen_capture"), 0xFF10DA16),
        ("Cam", video or ("dshow_input" if win else "av_capture_input_v2"), 0xFF3C8BDA),
        ("Chat", video or "browser_source", 0xFFDA2624),
        ("Overlay", "browser_source", None),
        ("Deer", "browser_source", None),
    ]


# Sources the overlay positions through obs-websocket. Anything else in COMIC
# is a stray as far as this script is concerned.
MANAGED = {"Game", "Cam", "Chat", "Overlay", "Deer"}


# The chat hole is punched, so the widget's own page is what shows through it.
# A transparent chat box therefore reads as a black rectangle cut out of the
# panel, not as chat floating on comic art -- hence the opaque --peri ground,
# which is the chat panel's own background colour.
#
# The rest strips YouTube's popout chrome, measured against a live
# youtube.com/live_chat?v=...&is_popout=1 page: #panel-pages is the "Sign in to
# chat" footer, #show-more the jump-to-latest pill. With the header and footer
# hidden the message list reflows to the full height on its own. The selectors
# are inert for any other provider, so this is safe to leave set.
CHAT_CSS = """\
body { background: #b9c3d6 !important; margin: 0; overflow: hidden; }
yt-live-chat-header-renderer, #panel-pages, #show-more,
yt-live-chat-banner-manager { display: none !important; }
yt-live-chat-renderer, #chat, #contents, #item-list, #item-scroller, #items,
yt-live-chat-item-list-renderer { background: transparent !important; }
#item-scroller { overflow: hidden !important; }
yt-live-chat-text-message-renderer { font-size: 20px !important; padding: 5px 10px !important; }
yt-live-chat-text-message-renderer #author-name { color: #16161d !important; font-weight: 700 !important; }
yt-live-chat-text-message-renderer #message { color: #16161d !important; }"""


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
    def display(f: Path) -> str:
        try:
            return json.loads(f.read_text()).get("name") or f.stem
        except Exception:
            return f.stem

    if name:
        # Either spelling. OBS's display name can hold spaces that the filename
        # replaces with underscores, and the listing below has to print one of
        # them -- so whatever it prints must also be accepted back.
        for f in files:
            if name in (display(f), f.stem):
                return f
        raise SystemExit(
            "error: no collection named %r in %s\n       have: %s"
            % (name, d, ", ".join(sorted({display(f) for f in files})))
        )
    if len(files) > 1:
        raise SystemExit(
            "error: %d collections in %s -- name the one you want with "
            "--collection\n       %s"
            % (len(files), d, ", ".join(sorted({display(f) for f in files})))
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
        # Every canvas, not just Main. One scene collection file holds the
        # scenes of all of them -- a vertical canvas is a native libobs canvas,
        # so VCOMIC is written into the same JSON -- while GetSceneList without
        # a canvasUuid answers for Main alone. Compare those two and the file
        # looks permanently stale by exactly the vertical scenes, which is a
        # refusal to export that no amount of quitting OBS can clear.
        #
        # GetCanvasList is OBS 32 / obs-websocket 5.7; older builds have no
        # second canvas to miss.
        try:
            for c in obs.req("GetCanvasList")["canvases"]:
                if c.get("canvasFlags", {}).get("MAIN"):
                    continue
                scenes |= {x["sceneName"] for x in obs.req(
                    "GetSceneList", {"canvasUuid": c["canvasUuid"]})["scenes"]}
        except ObsError:
            pass
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
    if name == "OverlayV":
        # Same file:// reasoning as Overlay.
        #
        # reroute_audio stays FALSE. Alert audio rides the horizontal Overlay
        # (CLAUDE.md §4); a second rerouted browser source would put every
        # alert sound into the mix twice.
        url = (REPO / "vertical.html").as_uri()
        if pw:
            url += "?pw=" + urllib.parse.quote(pw)
        return {
            "url": url,
            "width": VERT_W,
            "height": VERT_H,
            "shutdown": False,
            "restart_when_active": False,
            "reroute_audio": False,
        }
    if name == "DeerV":
        # The vertical twin of Deer. Same bridge, same sprite set, different
        # placement file -- mascot.html needed no changes, because it already
        # takes `place` and sizes itself from innerWidth/innerHeight.
        url = ("http://127.0.0.1:%d/mascot.html?set=deer"
               "&place=placement-vertical.json" % MASCOT_PORT)
        if pw:
            url += "&pw=" + urllib.parse.quote(pw)
        return {
            "url": url,
            "width": VERT_W,
            "height": VERT_H,
            "shutdown": False,
            "restart_when_active": False,
            "reroute_audio": False,
        }
    if name == "Chat":
        # 800x938 is the chat hole's own aspect (2174 x 2550 page px). The
        # source is cropped to that aspect before it is stretched, so any
        # other shape throws away chat rather than letterboxing it.
        # The hole is punched, so the widget's page is what shows -- a
        # transparent chat box would read as a black rectangle cut out of the
        # panel. --peri is the chat panel's own background.
        return {"url": "about:blank", "width": 800, "height": 938,
                "css": CHAT_CSS,
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
    ap.add_argument("--encoder", default="", metavar="WHICH",
                    choices=["", "auto"] + sorted(ENCODER_CHOICES),
                    help="set the stream and recording video encoder: auto "
                         "(best hardware encoder this OBS reports), or one of "
                         "%s. Without it, a deprecated encoder ID is still "
                         "rewritten and a software encoder is reported."
                         % "/".join(sorted(ENCODER_CHOICES)))
    ap.add_argument("--vertical", action="store_true",
                    help="also assert %s on the vertical canvas, for streaming "
                         "9:16 alongside. Needs the Aitum Vertical Canvas "
                         "plugin and a canvas added in its dock." % VERT_SCENE)
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
            # Everything but the url, which is yours -- your channel, your
            # widget provider. The rest is derived from the hole.
            want = {k: want[k] for k in
                    ("width", "height", "css", "shutdown", "restart_when_active")}
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

    # --- vertical canvas ---------------------------------------------------
    # After COMIC, because it reuses the very inputs that phase creates.
    if a.vertical:
        do_vertical(obs, plan, a, pw)

    # --- encoder -----------------------------------------------------------
    do_encoder(obs, plan, a)

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


def vertical_canvas(obs):
    """The canvas that is not Main, by uuid. Never matched by name -- OBS
    accepts canvasName and then ignores it."""
    for c in obs.req("GetCanvasList")["canvases"]:
        if not c.get("canvasFlags", {}).get("MAIN"):
            return c
    return None


def do_vertical(obs, plan: Plan, a, pw: str) -> None:
    """Assert VCOMIC on the vertical canvas.

    Everything here addresses the canvas by uuid and the scene by uuid, for the
    reasons in the VERT_SCENE block above. Runs after the COMIC phase because
    it reuses Game / Cam / Chat, which that phase creates.
    """
    cv = vertical_canvas(obs)
    if cv is None:
        plan.warn(
            "no second canvas exists, so there is nothing to build on. Install "
            "the Aitum Vertical Canvas plugin, restart OBS -- plugins bind at "
            "process start -- and add a canvas in its dock. --vertical does the "
            "rest."
        )
        return

    cu = cv["canvasUuid"]
    vs = cv["canvasVideoSettings"]
    if (vs["baseWidth"], vs["baseHeight"]) != (VERT_W, VERT_H):
        plan.warn(
            "vertical canvas %r is %dx%d, vertical.html assumes %dx%d -- every "
            "hole rect it pushes is in canvas pixels, so they would all be "
            "wrong. Fix it in the Aitum dock; obs-websocket has no request that "
            "can set a canvas resolution."
            % (cv["canvasName"], vs["baseWidth"], vs["baseHeight"], VERT_W, VERT_H)
        )

    def vscenes():
        return {x["sceneName"]: x["sceneUuid"]
                for x in obs.req("GetSceneList", {"canvasUuid": cu})["scenes"]}

    # --- the scene ---------------------------------------------------------
    # RENAME what the plugin already owns; do not CreateScene if it can be
    # avoided. A scene made over the websocket is real -- libobs has it and
    # GetSceneList returns it -- but the Aitum dock never learns about it. Its
    # config stores only `current_scene` and no scene list, so it enumerates
    # the canvas once at load and otherwise tracks only what its own UI made.
    # A created scene is therefore invisible in the dock, cannot be selected,
    # and so can never go on air: its sources stay inactive and the vertical
    # overlay never even boots.
    #
    # Renaming the plugin's own default scene sidesteps all of that. The uuid
    # is preserved, so it stays whatever the canvas already had on air -- which
    # for a fresh canvas is exactly the scene we want to become VCOMIC.
    have = vscenes()
    if VERT_SCENE not in have:
        spare = [n for n in have if n != VERT_SCENE]
        if len(spare) == 1:
            old = spare[0]
            plan.do(
                "rename vertical scene %r -> %s (keeps its uuid, so it stays "
                "the canvas's current scene)" % (old, VERT_SCENE),
                lambda u=have[old]: obs.req(
                    "SetSceneName", {"sceneUuid": u, "newSceneName": VERT_SCENE}),
            )
        elif not spare:
            plan.do(
                "create scene %s on %s" % (VERT_SCENE, cv["canvasName"]),
                lambda: obs.req("CreateScene",
                                {"sceneName": VERT_SCENE, "canvasUuid": cu}),
            )
            plan.warn(
                "%s had to be CREATED rather than renamed, because the canvas "
                "had no scene to rename. The Aitum dock will not list it until "
                "OBS restarts and the plugin re-enumerates the canvas."
                % VERT_SCENE
            )
        else:
            plan.warn(
                "the vertical canvas holds %d scenes (%s) and none is called %s, "
                "so there is no single obvious one to rename. Rename one to %s "
                "in the Aitum dock and re-run."
                % (len(spare), ", ".join(sorted(spare)), VERT_SCENE, VERT_SCENE)
            )
            return
        if a.check:
            # Nothing below can be checked against a scene that is not there yet.
            return
        have = vscenes()
    su = have[VERT_SCENE]

    # --- OverlayV ----------------------------------------------------------
    inputs = {i["inputName"]: i["inputKind"] for i in obs.req("GetInputList")["inputs"]}
    made = False
    for vname in ("OverlayV", "DeerV"):
        if vname not in inputs:
            plan.do(
                "create input %s (browser_source)" % vname,
                lambda n=vname: obs.req(
                    "CreateInput",
                    {"sceneUuid": su, "inputName": n,
                     "inputKind": "browser_source",
                     "inputSettings": browser_settings(n, pw),
                     "sceneItemEnabled": True},
                ),
            )
            made = True
            if not a.check:
                inputs[vname] = "browser_source"
        elif inputs[vname] != "browser_source":
            plan.warn(
                "%s exists as %s, not browser_source -- left alone. Delete it "
                "in OBS and re-run if you want this script to make it."
                % (vname, inputs[vname])
            )
    if made and a.check:
        return

    # Asserted every run, same as Overlay: a stale url, or "Shutdown source when
    # not visible" left ticked, breaks the vertical overlay in ways that look
    # like an overlay bug.
    for vname in ("OverlayV", "DeerV"):
        if inputs.get(vname) != "browser_source":
            continue
        want = browser_settings(vname, pw)
        held = obs.req("GetInputSettings", {"inputName": vname})["inputSettings"]
        diff = {k: v for k, v in want.items() if held.get(k) != v}
        # OBS omits defaults from the settings blob, so absent == the default.
        diff = {k: v for k, v in diff.items() if not (k not in held and v is False)}
        if diff:
            plan.do(
                "%s: set %s" % (vname, ", ".join(sorted(diff))),
                lambda n=vname, d=diff: obs.req(
                    "SetInputSettings", {"inputName": n, "inputSettings": d}),
            )

    # --- contents and z-order ---------------------------------------------
    items = obs.req("GetSceneItemList", {"sceneUuid": su})["sceneItems"]
    by_name = {i["sourceName"]: i for i in items}

    for name in VERT_STACK:
        if name not in by_name and name in inputs:
            plan.do(
                "add %s to %s" % (name, VERT_SCENE),
                lambda n=name: obs.req(
                    "CreateSceneItem",
                    {"sceneUuid": su, "sourceName": n, "sceneItemEnabled": True}),
            )

    strays = sorted(set(by_name) - VERT_MANAGED)
    for name in strays:
        if a.prune:
            plan.do(
                "remove %s from %s" % (name, VERT_SCENE),
                lambda i=by_name[name]["sceneItemId"]: obs.req(
                    "RemoveSceneItem", {"sceneUuid": su, "sceneItemId": i}),
            )
        else:
            plan.warn(
                "%s sits in %s but no hole maps to it. It renders behind the "
                "vertical overlay and shows through whatever hole it happens to "
                "overlap. Re-run with --prune to remove it." % (name, VERT_SCENE)
            )

    if not a.check or all(n in by_name for n in VERT_STACK):
        items = obs.req("GetSceneItemList", {"sceneUuid": su})["sceneItems"]
        by_name = {i["sourceName"]: i for i in items}
        want_order = [n for n in VERT_STACK if n in by_name]
        have_order = [i["sourceName"] for i in
                      sorted(items, key=lambda i: i["sceneItemIndex"])
                      if i["sourceName"] in want_order]
        if have_order != want_order:
            plan.do(
                "restack %s: %s" % (VERT_SCENE, " < ".join(want_order)),
                lambda: [
                    obs.req("SetSceneItemIndex",
                            {"sceneUuid": su,
                             "sceneItemId": by_name[n]["sceneItemId"],
                             "sceneItemIndex": i})
                    for i, n in enumerate(want_order)
                ],
            )

    vertical_output_check(plan)

    # Whether VCOMIC is actually on air cannot be read back: SetCurrentProgramScene
    # refuses a non-main scene ("The specified scene is not from the main
    # canvas"), GetCurrentProgramScene ignores canvasUuid and reports Main's,
    # and none of the plugin's 14 hotkeys switches a scene. So this is reported
    # from the one thing that IS observable -- whether OverlayV has activated.
    # Renaming rather than creating the scene normally makes it moot.
    if not obs.req("GetSourceActive", {"sourceName": "OverlayV"})["videoActive"]:
        plan.warn(
            "OverlayV is not active, which means %s is not on air on the "
            "vertical canvas -- so the vertical overlay is not running at all. "
            "Select %s in the Aitum Vertical dock. This is the one step no "
            "request, vendor or hotkey can perform."
            % (VERT_SCENE, VERT_SCENE)
        )


def vertical_output_check(plan: Plan) -> None:
    """Report on the vertical canvas's own output settings. Never writes.

    Aitum keeps its outputs in its own plugin config, not in the OBS profile, so
    do_encoder cannot reach them and neither can `--export`: that file holds
    your stream key in clear text, which is reason enough for this function to
    be read-only and for the file to stay out of the repo.

    The trap worth naming is that `stream_encoder` is only consulted when
    `stream_advanced_settings` is on. With it off, Aitum picks an encoder itself
    and whatever is stored is inert -- so a config can sit there for months
    reading `ffmpeg_svt_av1` (CPU AV1) and encode on the GPU regardless, right
    up until somebody ticks Advanced.
    """
    cfg = obs_config_dir() / "plugin_config/vertical-canvas/config.json"
    try:
        doc = json.loads(cfg.read_text(errors="replace"))
    except (OSError, ValueError):
        return

    for canvas in doc.get("canvas", []):
        if (canvas.get("width"), canvas.get("height")) != (VERT_W, VERT_H):
            continue
        enc = canvas.get("stream_encoder") or ""
        if not canvas.get("stream_advanced_settings"):
            if enc in SOFTWARE_ENCODERS:
                plan.warn(
                    "the vertical canvas has %r stored as its stream encoder. It "
                    "is inert right now -- Aitum only reads it when Advanced is "
                    "ticked in its output settings -- but tick that and the "
                    "vertical output moves onto the CPU. Set it to a hardware "
                    "encoder there while you are thinking about it." % enc
                )
        elif enc in SOFTWARE_ENCODERS:
            plan.warn(
                "the vertical canvas is set to Advanced and encodes on %r, a "
                "software encoder. That is a second 1080x1920 encode on the CPU, "
                "on top of the program encode. Change it in the Aitum dock's "
                "output settings." % enc
            )


def available_encoders() -> set:
    """Video encoder IDs this OBS actually registered, read out of its own log.

    obs-websocket has no request for this. GetVersion reports requests and image
    formats; GetInputKindList reports sources. Nothing reports encoders, so the
    log is the only place OBS says which ones the hardware and the installed
    plugins gave it. It prints the list at every startup:

        Available Encoders:
          Video Encoders:
            - obs_nvenc_h264_tex (NVIDIA NVENC H.264)
            - obs_x264 (x264)
          Audio Encoders:

    Newest log first, skipping any that has no such block -- the very newest is
    often a two-line crash stub from the previous run. An empty set means "could
    not tell", never "none available", and every caller treats it that way.
    """
    logs = obs_config_dir() / "logs"
    try:
        files = sorted(logs.glob("*.txt"), key=lambda f: f.stat().st_mtime, reverse=True)
    except OSError:
        return set()
    for f in files[:12]:
        found, inside = set(), False
        try:
            text = f.read_text(errors="replace")
        except OSError:
            continue
        for line in text.splitlines():
            body = line.split(": ", 1)[-1]
            if body.strip() == "Video Encoders:":
                inside = True
                continue
            if inside:
                stripped = body.strip()
                if stripped.startswith("- "):
                    found.add(stripped[2:].split(" (", 1)[0])
                    continue
                break
        if found:
            return found
    return set()


# Profile keys per output mode. Simple mode stores a short token, Advanced the
# encoder ID itself, which is why every read goes through resolve_encoder().
ENCODER_KEYS = {
    False: ("AdvOut", "Encoder", "RecEncoder"),       # Advanced
    True: ("SimpleOutput", "StreamEncoder", "RecEncoder"),
}


def resolve_encoder(raw: str, simple: bool) -> str:
    """Whatever the profile holds -> the canonical modern encoder ID."""
    if not raw:
        return "obs_x264"   # OBS's own default, in both modes
    if simple:
        return SIMPLE_ID.get(raw, raw)
    return DEPRECATED_ENCODERS.get(raw, raw)


def do_encoder(obs, plan: Plan, a) -> None:
    """Assert the video encoder for the stream and recording outputs.

    Two very different jobs, deliberately kept apart:

    - A deprecated ID is *renamed* on an ordinary run. jim_nvenc and
      obs_nvenc_h264_tex are the same encoder with the same settings; OBS maps
      one to the other and logs a deprecation warning per output per launch. So
      this is a repair, in the same spirit as fixing a stale browser URL.

    - Switching encoder -- x264 to NVENC, say -- is never done unasked, because
      x264 can be a deliberate choice (a second PC, a recording you want CPU
      quality for) and this script does not overwrite deliberate choices. It
      warns, and `--encoder auto` performs it. The README's new-machine
      walkthrough calls that flag out, which is what makes a fresh install end
      up on the GPU without anybody clicking through Settings -> Output.
    """
    mode = obs.req("GetProfileParameter",
                   {"parameterCategory": "Output",
                    "parameterName": "Mode"}).get("parameterValue")
    simple = (mode or "Simple").lower() != "advanced"
    cat, stream_key, rec_key = ENCODER_KEYS[simple]

    have = available_encoders()
    want = None
    if a.encoder == "auto":
        if not have:
            plan.warn(
                "--encoder auto could not read an encoder list out of OBS's "
                "log, so it cannot tell what this machine has and has changed "
                "nothing. Pick one: --encoder nvenc / qsv / amd / apple / x264."
            )
            return
        want = next((e for e in HW_PREFERENCE if e in have), None)
    elif a.encoder:
        want = ENCODER_CHOICES[a.encoder]
        if have and want not in have:
            plan.warn(
                "--encoder %s asks for %s, which this OBS did not register. It "
                "has: %s. Nothing changed."
                % (a.encoder, want, ", ".join(sorted(have)))
            )
            return

    touched = False
    for label, key in (("stream", stream_key), ("recording", rec_key)):
        raw = obs.req("GetProfileParameter",
                      {"parameterCategory": cat,
                       "parameterName": key}).get("parameterValue")
        # Whatever is there now, as a modern ID. With no --encoder that is also
        # the target: the only change an ordinary run makes is spelling.
        cur = resolve_encoder(raw, simple)
        target = want or cur
        written = SIMPLE_TOKEN.get(target, target) if simple else target

        # An unset key is OBS's default, which resolve_encoder already reports
        # as obs_x264. Writing that default back would be noise.
        if written != raw and (raw or want):
            touched = True
            plan.do(
                "%s encoder: %s -> %s%s"
                % (label, raw or "(OBS default)", written,
                   "" if want else "   deprecated ID, same encoder"),
                lambda c=cat, k=key, v=written: obs.req(
                    "SetProfileParameter",
                    {"parameterCategory": c, "parameterName": k,
                     "parameterValue": v}),
            )

        # Only when nothing was asked for. If you passed --encoder x264 you do
        # not need to be told there is a GPU in the machine.
        if not a.encoder and cur in SOFTWARE_ENCODERS and have:
            better = next((e for e in HW_PREFERENCE
                           if e in have and e not in SOFTWARE_ENCODERS), None)
            if better:
                plan.warn(
                    "%s output is on %s, a software encoder, but this machine "
                    "registered %s. The pan is a 7680x4320 CSS transform inside "
                    "CEF and Source Record adds an output per source -- the CPU "
                    "has enough to do. `--encoder auto` switches it."
                    % (label, cur, better)
                )

    if touched and not a.check:
        plan.warn(
            "OBS reads the encoder when an output starts, so this takes effect "
            "on your next Start Streaming / Start Recording. Settings -> Output "
            "may keep showing the old value until you reopen it, and the profile "
            "is written to disk when OBS quits cleanly."
        )


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
                "mascot/placement-vertical.json",
                "mascot/deer/manifest.json", "overlay.html", "vertical.html"):
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

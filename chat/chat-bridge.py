#!/usr/bin/env python3
"""
chat-bridge -- reads Restream chat aloud.

Connects to the socket Restream's own chat embed uses, turns every chat event
into {platform, name, text}, filters it, queues it, and speaks it with Piper
as "{name} says: {message}. On {platform}." One line at a time; a flood drops
the oldest waiting lines rather than reading for minutes.

The audio plays in OBS, not here: the bridge serves chat/tts.html on
127.0.0.1:4461, the `Tts` browser source loads it, and each line is pushed to
the page over Server-Sent Events. The page reports when a line has finished,
which is what holds the queue to one line at a time. No page connected, no
speech -- a line is dropped rather than queued for an OBS that is not there.

Normally started by start.py at the repo root, alongside the mascot bridge.

    chat/.venv/Scripts/python chat/chat-bridge.py
    chat/.venv/Scripts/python chat/chat-bridge.py --play       hear it here instead
    chat/.venv/Scripts/python chat/chat-bridge.py --say "hi"   one line, then exit
    chat/.venv/Scripts/python chat/chat-bridge.py --raw        dump every frame

It will not start without a blocklist (chat/blocklist.txt, which is
gitignored -- copy it across when you move machines). --no-blocklist
overrides that, and reads everything.

The embed token is not stored here. It is read out of the `Chat` browser
source in OBS, so there is exactly one copy: regenerate the embed URL in
Restream, paste it into Chat, and the bridge picks it up on its next
reconnect. See CLAUDE.md "Chat TTS" for why the embed socket rather than
Restream's documented API, and for what Piper costs.

Runs from chat/.venv, the one place in the repo with pip dependencies (Piper).
Nothing is imported from tools/ -- the OBS client below duplicates about sixty
lines of obs-setup.py so that chat/ can be lifted into its own project without
untangling anything.
"""

from __future__ import annotations

import argparse
import base64
import collections
import ctypes
import hashlib
import io
import json
import os
import re
import socket
import ssl
import struct
import sys
import threading
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
import wave
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parent

# Next to the mascot bridge's 4460. Must match TTS_PORT in tools/obs-setup.py
# and in start.py.
TTS_PORT = 4461
PAGE = HERE / "tts.html"

EMBED_HOST = "backend.chat.restream.io"
# Read out of the embed's own bundle: WS_CHAT_HOST + "/ws/embed?token=…".
# Undocumented, so it can move without notice -- the symptom is a reconnect
# loop in this log and silence on stream, never an error anywhere else.
EMBED_PATH = "/ws/embed"
EMBED_ORIGIN = "https://chat.restream.io"

CHAT_SOURCE = "Chat"

# Restream numbers event *types* per platform, so the type alone says where a
# message came from and eventSourceId is never needed for chat. These are the
# types that carry a line of chat; 7 is a Super Chat, whose text is optional.
CHAT_TYPES = {4: "Twitch", 5: "YouTube", 7: "YouTube", 25: "Kick"}

# eventSourceId, for naming connections in the log. From Restream's Event
# Sources table.
SOURCES = {1: "Restream", 2: "Twitch", 13: "YouTube", 19: "Facebook",
           20: "Facebook page", 24: "DLive", 25: "Discord", 26: "LinkedIn",
           27: "Trovo", 28: "X", 29: "Kick", 33: "Rumble"}

# A frame of any kind proves the socket is alive. Measured: Restream sends
# heartbeats in pairs about 45s apart, so 95s is two missed pairs -- the TCP
# connection died without a close frame, which is how a sleep or a router
# drop presents.
SILENCE_LIMIT = 95.0

# Your own accounts are never read back to you. Compared with everything but
# letters and digits squashed out, so the Kick handle `thedeepeffect`, the
# Twitch/YouTube `thedeepeffect_`, and a YouTube channel name like "The Deep
# Effect" are all one entry. Same handles as `socials` in core/contract.js.
OWN_NAMES = {"thedeepeffect"}

# The channel YouTubeChat reads when Restream cannot. Same handle as SOCIALS.
YT_HANDLE = "thedeepeffect_"

VOICE = HERE / "voices" / "en_US-lessac-medium.onnx"
BLOCKLIST = HERE / "blocklist.txt"

# Piper normalises every line to full scale -- measured peak 1.00 on the Tts
# meter, louder than anything else in the mix. Half is -6 dB, which leaves the
# OBS fader as the taste dial rather than an emergency brake.
VOLUME = 0.5

MAX_CHARS = 200      # 13s of lessac; longer is cut at a word boundary
QUEUE_MAX = 5        # lines waiting; past this the oldest is dropped
MAX_AGE = 60.0       # a line that waited longer than this is stale -- dropped


def log(msg: str) -> None:
    print(time.strftime("%H:%M:%S ") + msg, flush=True)


# ---------------------------------------------------------------------------
# a very small websocket client, ws:// and wss://


class WS:
    def __init__(self, url: str, headers: dict | None = None,
                 timeout: float = 10.0) -> None:
        u = urllib.parse.urlsplit(url)
        tls = u.scheme == "wss"
        port = u.port or (443 if tls else 80)
        sock = socket.create_connection((u.hostname, port), timeout=timeout)
        if tls:
            sock = ssl.create_default_context().wrap_socket(
                sock, server_hostname=u.hostname)
        self.sock = sock
        path = (u.path or "/") + ("?" + u.query if u.query else "")
        lines = ["GET %s HTTP/1.1" % path, "Host: %s" % u.hostname,
                 "Upgrade: websocket", "Connection: Upgrade",
                 "Sec-WebSocket-Key: " + base64.b64encode(os.urandom(16)).decode(),
                 "Sec-WebSocket-Version: 13"]
        lines += ["%s: %s" % kv for kv in (headers or {}).items()]
        sock.sendall(("\r\n".join(lines) + "\r\n\r\n").encode())
        head = b""
        while b"\r\n\r\n" not in head:
            chunk = sock.recv(1)
            if not chunk:
                raise ConnectionError("server closed during handshake")
            head += chunk
        status = head.split(b"\r\n")[0].decode(errors="replace")
        if " 101 " not in status + " ":
            # Never echo the request line back: the token is in it.
            raise ConnectionError("handshake refused: " + status)
        self.buf = b""

    def _exact(self, n: int) -> bytes:
        while len(self.buf) < n:
            chunk = self.sock.recv(65536)
            if not chunk:
                raise ConnectionError("server closed")
            self.buf += chunk
        out, self.buf = self.buf[:n], self.buf[n:]
        return out

    def _frame(self, opcode: int, payload: bytes) -> None:
        n = len(payload)
        head = bytearray([0x80 | opcode])
        if n < 126:
            head.append(0x80 | n)
        elif n < 1 << 16:
            head.append(0x80 | 126)
            head += struct.pack(">H", n)
        else:
            head.append(0x80 | 127)
            head += struct.pack(">Q", n)
        mask = os.urandom(4)
        self.sock.sendall(bytes(head) + mask +
                          bytes(b ^ mask[i % 4] for i, b in enumerate(payload)))

    def send(self, obj) -> None:
        self._frame(0x1, json.dumps(obj).encode())

    def recv(self):
        """Next message, decoded. Raises socket.timeout when the line is quiet."""
        parts = []
        while True:
            b0, b1 = self._exact(2)
            opcode, fin = b0 & 0x0F, b0 & 0x80
            n = b1 & 0x7F
            if n == 126:
                n = struct.unpack(">H", self._exact(2))[0]
            elif n == 127:
                n = struct.unpack(">Q", self._exact(8))[0]
            data = self._exact(n) if n else b""
            if opcode == 0x9:
                self._frame(0xA, data)  # pong echoes the ping's payload
                continue
            if opcode == 0xA:
                continue
            if opcode == 0x8:
                raise ConnectionError("server closed the socket")
            parts.append(data)
            if fin:
                return json.loads(b"".join(parts))

    def close(self) -> None:
        try:
            self.sock.close()
        except Exception:
            pass


# ---------------------------------------------------------------------------
# OBS: only to read the embed token out of the Chat source


def obs_password() -> str:
    if sys.platform.startswith("win"):
        base = Path(os.environ.get("APPDATA", "")) / "obs-studio"
    elif sys.platform == "darwin":
        base = Path.home() / "Library/Application Support/obs-studio"
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME",
                                   Path.home() / ".config")) / "obs-studio"
    try:
        cfg = base / "plugin_config/obs-websocket/config.json"
        return json.loads(cfg.read_text()).get("server_password", "")
    except Exception:
        return ""


def embed_token(host: str, port: int, password: str) -> str:
    ws = WS("ws://%s:%d" % (host, port))
    try:
        hello = ws.recv()
        d = {"rpcVersion": 1, "eventSubscriptions": 0}
        auth = hello["d"].get("authentication")
        if auth:
            secret = base64.b64encode(hashlib.sha256(
                (password + auth["salt"]).encode()).digest()).decode()
            d["authentication"] = base64.b64encode(hashlib.sha256(
                (secret + auth["challenge"]).encode()).digest()).decode()
        ws.send({"op": 1, "d": d})
        if ws.recv().get("op") != 2:
            raise ConnectionError("obs-websocket refused the password")
        ws.send({"op": 6, "d": {"requestType": "GetInputSettings",
                                "requestId": "chat",
                                "requestData": {"inputName": CHAT_SOURCE}}})
        while True:
            m = ws.recv()
            if m.get("op") == 7 and m["d"]["requestId"] == "chat":
                break
    finally:
        ws.close()
    if not m["d"]["requestStatus"]["result"]:
        raise LookupError("OBS has no input called %r" % CHAT_SOURCE)
    url = m["d"]["responseData"]["inputSettings"].get("url", "")
    u = urllib.parse.urlsplit(url)
    token = urllib.parse.parse_qs(u.query).get("token", [""])[0]
    if u.hostname != "chat.restream.io" or not token:
        raise LookupError("%s is not a Restream chat embed (%s)"
                          % (CHAT_SOURCE, u.hostname or "no url"))
    return token


# ---------------------------------------------------------------------------
# what gets read, and how it is said


def normalise(p: dict) -> dict | None:
    """One chat event -> {platform, name, text, bot}, or None if not chat."""
    platform = CHAT_TYPES.get(p.get("eventTypeId"))
    if platform is None:
        return None
    ev = p.get("eventPayload") or {}
    a = ev.get("author") or {}
    # Twitch: displayName, which may be null -> name. YouTube: displayName.
    # Kick: username -- a Kick author carries nothing else. One order covers
    # all three.
    name = a.get("displayName") or a.get("username") or a.get("name") or ""
    return {"platform": platform, "name": name,
            "text": (ev.get("text") or "").strip(), "bot": bool(ev.get("bot"))}


# Letter swaps the blocklist sees through. Deliberately short: every class
# added here widens what an innocent word can be mistaken for. `*` stands in
# for any vowel, because a self-censored "f*ck" is still read out as one.
LEET = {"a": "a4@*", "e": "e3*", "i": "i1!|*", "o": "o0*", "u": "u*",
        "s": "s5$", "t": "t7"}


class Blocklist:
    """blocklist.txt, recompiled whenever the file changes.

    A line is a word or phrase, matched as whole words, case-insensitive,
    with LEET swaps and stretched letters ("fuuuck") folded in. A trailing *
    also matches longer words that start with it. Spaced-out letters are not
    caught; nothing cheap catches those without flagging ordinary sentences.
    """

    def __init__(self, path: Path, required: bool = True) -> None:
        self.path, self.mtime, self.required = path, None, required
        self.words = self.symbols = None

    def ready(self) -> bool:
        """False when the list is required and missing or empty.

        Checked on every line, not just at startup: a list deleted or emptied
        mid-stream must stop speech, not quietly turn the filter off.
        """
        self._compile()
        return not self.required or bool(self.words or self.symbols)

    def _compile(self) -> None:
        try:
            mtime = self.path.stat().st_mtime
        except OSError:
            self.mtime, self.words, self.symbols = None, None, None
            return
        if mtime == self.mtime:
            return
        words, symbols = [], []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            w = line.strip().lower()
            if not w or w.startswith("#"):
                continue
            prefix = w.endswith("*")
            w = w.rstrip("*").strip()
            body = ""
            for ch in w:
                if ch.isspace():
                    body += r"[\W_]+"
                elif ch in LEET:
                    body += "[%s]+" % re.escape(LEET[ch])
                else:
                    body += "%s+" % re.escape(ch)
            if body:
                body += "" if prefix else r"(?![a-z0-9])"
                (words if re.search("[a-z]", w) else symbols).append(body)
        rx = lambda alts: (re.compile(r"(?<![a-z0-9])(?:%s)" % "|".join(alts))
                           if alts else None)
        self.words, self.symbols = rx(words), rx(symbols)
        self.mtime = mtime
        n = len(words) + len(symbols)
        log("blocklist: %d entr%s" % (n, "y" if n == 1 else "ies"))

    def _hit(self, t: str) -> bool:
        # A word entry never counts when the match is nothing but digits.
        # LEET turns `ass` into [a4@*]+[s5$]+[s5$]+, which "455 damage"
        # satisfies with digits alone -- while "@$$" must still count, so the
        # test is digits, not letters. Entries with no letters of their own
        # (1488, an emoji) live in `symbols` and are matched as written.
        if self.words and any(not m.group().isdigit()
                              for m in self.words.finditer(t)):
            return True
        return bool(self.symbols and self.symbols.search(t))

    def hit(self, *texts: str) -> bool:
        self._compile()
        return any(self._hit(t.lower()) for t in texts)


URL = re.compile(r"(?i)\b(?:https?://|www\.)\S+"
                 r"|\b[\w-]+\.(?:com|net|org|tv|gg|io|ly|co|me|be|xyz|app|dev)\b\S*")
KICK_EMOTE = re.compile(r"\[emote:\d+:[^\]]*\]")
LINKS = re.compile(r"(?:\ba link\b[\s,.]*){2,}")


def say_name(name: str) -> str:
    # Underscores are read aloud as "underscore"; spaces are not.
    n = re.sub(r"[_\s]+", " ", name.lstrip("@")).strip()
    return n or "someone"


def clean(text: str) -> str:
    """Chat text -> something worth hearing, or "" when nothing is left."""
    t = KICK_EMOTE.sub(" ", text)          # [emote:37226:KEKW] reads as noise
    t = URL.sub(" a link ", t)
    t = LINKS.sub("some links ", t)
    # Emoji, skin tones, joiners, variation selectors: espeak would either
    # skip them or read their Unicode names, and neither is chat.
    t = "".join(c for c in t if unicodedata.category(c) not in
                ("So", "Sk", "Cf", "Co", "Cs", "Cn") and c not in "︎️")
    t = re.sub(r"@(\w+)", r"\1", t)
    t = t.replace("_", " ")
    t = re.sub(r"(.)\1{3,}", r"\1\1\1", t)  # "lolllllll" -> "lolll"
    t = re.sub(r"(?i)\b(\w+)(?:\s+\1\b){3,}", r"\1 \1 \1", t)  # "gg gg gg gg gg"
    t = re.sub(r"\s+", " ", t).strip()
    if len(t) > MAX_CHARS:
        cut = t.rfind(" ", 0, MAX_CHARS)
        t = t[:cut if cut > MAX_CHARS // 2 else MAX_CHARS].rstrip(" ,;:-")
    return t if re.search(r"\w", t) else ""


def decide(line: dict, blocklist: Blocklist, read_own: bool = False):
    """-> (sentence, None) to speak, or (None, reason) to skip."""
    if line["bot"]:
        return None, "bot"
    text = line["text"]
    if text.startswith("!"):
        return None, "command"
    if not read_own and re.sub(r"[^a-z0-9]", "", line["name"].lower()) in OWN_NAMES:
        return None, "own account"
    if not blocklist.ready():
        return None, "blocklist missing or empty -- nothing is read without one"
    if blocklist.hit(line["name"], text):
        return None, "blocklist"
    said = clean(text)
    if not said:
        return None, "nothing to say"
    end = "" if said[-1] in ".!?" else "."
    return "%s says: %s%s On %s." % (say_name(line["name"]), said, end,
                                     line["platform"]), None


# ---------------------------------------------------------------------------
# Piper, and the one-at-a-time queue in front of it


def below_normal() -> None:
    """Drop the whole process below normal priority, so a game always wins."""
    if sys.platform.startswith("win"):
        k32 = ctypes.WinDLL("kernel32")
        k32.GetCurrentProcess.restype = ctypes.c_void_p
        k32.SetPriorityClass(ctypes.c_void_p(k32.GetCurrentProcess()),
                             0x00004000)  # BELOW_NORMAL_PRIORITY_CLASS
    else:
        os.nice(5)


class Voice:
    def __init__(self, model: Path) -> None:
        try:
            import onnxruntime
            from piper import PiperVoice
            from piper.config import PiperConfig, SynthesisConfig
        except ImportError:
            raise SystemExit("error: Piper is not installed for this python.\n"
                             "       run with chat/.venv/Scripts/python")
        if not model.exists():
            raise SystemExit("error: no voice at %s" % model)
        # One thread, built here because PiperVoice.load cannot be told. The
        # default pool is a thread per core, and restricting affinity without
        # restricting threads is the worst setting there is -- measured 13x
        # slower and 3x the CPU of no cap at all (CLAUDE.md, "Chat TTS").
        # No affinity: the scheduler finds an idle core better than a pin can.
        so = onnxruntime.SessionOptions()
        so.intra_op_num_threads = 1
        so.inter_op_num_threads = 1
        t = time.perf_counter()
        self.piper = PiperVoice(
            session=onnxruntime.InferenceSession(
                str(model), sess_options=so, providers=["CPUExecutionProvider"]),
            config=PiperConfig.from_dict(json.loads(
                Path(str(model) + ".json").read_text(encoding="utf-8"))),
            download_dir=HERE)
        self.syn = SynthesisConfig(volume=VOLUME)
        log("voice %s loaded in %.1fs" % (model.stem, time.perf_counter() - t))

    def wav(self, text: str) -> tuple[bytes, float]:
        buf = io.BytesIO()
        with wave.open(buf, "wb") as w:
            self.piper.synthesize_wav(text, w, syn_config=self.syn)
        data = buf.getvalue()
        with wave.open(io.BytesIO(data), "rb") as r:
            return data, r.getnframes() / r.getframerate()


class Reader:
    """Speaks one line at a time, on its own thread, so the feed never waits.

    `play(wav, seconds)` must return when the line has finished playing --
    that is what keeps the queue serial.
    """

    def __init__(self, voice: Voice, play, wav_dir: Path | None = None) -> None:
        self.voice, self.play, self.wav_dir = voice, play, wav_dir
        self.q: collections.deque = collections.deque()
        self.cv = threading.Condition()
        self.n = 0

    def push(self, sentence: str) -> None:
        with self.cv:
            self.q.append((time.time(), sentence))
            dropped = 0
            while len(self.q) > QUEUE_MAX:
                self.q.popleft()
                dropped += 1
            waiting = len(self.q)
            self.cv.notify()
        if dropped:
            log("  queue full -- dropped the oldest %d" % dropped)
        log("  queued (%d waiting)" % waiting)

    def say(self, sentence: str) -> None:
        t = time.perf_counter()
        data, secs = self.voice.wav(sentence)
        log("speak %dms -> %.1fs: %s" % ((time.perf_counter() - t) * 1000,
                                         secs, sentence))
        if self.wav_dir:
            self.n += 1
            self.wav_dir.mkdir(parents=True, exist_ok=True)
            (self.wav_dir / ("%04d.wav" % self.n)).write_bytes(data)
        self.play(data, secs)

    def run(self) -> None:
        while True:
            with self.cv:
                while not self.q:
                    self.cv.wait()
                queued_at, sentence = self.q.popleft()
            if time.time() - queued_at > MAX_AGE:
                log("  stale after %ds -- dropped: %s"
                    % (time.time() - queued_at, sentence))
                continue
            try:
                self.say(sentence)
            except Exception as e:  # one bad line must not kill the reader
                log("  could not speak: %s" % e)

    def start(self) -> None:
        threading.Thread(target=self.run, name="reader", daemon=True).start()


def play_here(data: bytes, secs: float) -> None:
    import winsound
    winsound.PlaySound(data, winsound.SND_MEMORY)


# ---------------------------------------------------------------------------
# the Tts browser source: chat/tts.html, fed over Server-Sent Events


class Browser:
    """Plays a line on every connected tts.html and waits for it to finish.

    The page fetches /line/<n>.wav, plays it, and POSTs /done/<n> when it ends
    or fails. Waiting on that, rather than on the clip's duration, is what
    keeps lines from overlapping when the page is slow to load one. A page
    that never answers costs the clip's length plus GRACE, then the queue
    moves on.
    """

    GRACE = 5.0
    KEEP = 4          # clips held for late fetches

    def __init__(self) -> None:
        self.cv = threading.Condition()
        self.clients = 0
        self.seq = 0
        self.clips: dict[int, bytes] = {}
        self.done: set[int] = set()

    def play(self, data: bytes, secs: float) -> None:
        with self.cv:
            if not self.clients:
                log("  no Tts page connected -- not heard")
                return
            self.seq += 1
            n = self.seq
            self.clips[n] = data
            for old in [k for k in self.clips if k <= n - self.KEEP]:
                del self.clips[old]
            self.cv.notify_all()
            deadline = time.time() + secs + self.GRACE
            while n not in self.done and time.time() < deadline:
                self.cv.wait(deadline - time.time())
            if n not in self.done:
                log("  the page never finished line %d -- moving on" % n)
            self.done.discard(n)

    def finished(self, n: int) -> None:
        with self.cv:
            self.done.add(n)
            self.cv.notify_all()


class Handler(BaseHTTPRequestHandler):
    """Four routes and nothing else: chat/ also holds the blocklist and the
    venv, so the folder is never served as a directory."""

    browser: Browser = None           # set in main

    def log_message(self, *_a) -> None:
        pass                          # quiet; this runs behind OBS

    def _send(self, code: int, body: bytes = b"", ctype: str = "text/plain") -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        path = self.path.split("?")[0]
        if path in ("/", "/tts.html"):
            return self._send(200, PAGE.read_bytes(), "text/html; charset=utf-8")
        if path == "/events":
            return self._events()
        m = re.fullmatch(r"/line/(\d+)\.wav", path)
        if m:
            data = self.browser.clips.get(int(m.group(1)))
            return self._send(200, data, "audio/wav") if data else self._send(404)
        if path == "/status":
            b = self.browser
            return self._send(200, json.dumps(
                {"pages": b.clients, "lines": b.seq}).encode(), "application/json")
        self._send(404)

    def do_POST(self) -> None:
        m = re.fullmatch(r"/done/(\d+)", self.path.split("?")[0])
        if not m:
            return self._send(404)
        self.browser.finished(int(m.group(1)))
        self._send(204)

    def _events(self) -> None:
        b = self.browser
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Connection", "keep-alive")
        # The page is file://, a different origin; without this the
        # EventSource is refused and the page waits forever, silently.
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        with b.cv:
            b.clients += 1
            last = b.seq
        log("Tts page connected (%d)" % b.clients)
        try:
            while True:
                with b.cv:
                    b.cv.wait_for(lambda: b.seq != last, timeout=15)
                    new = list(range(last + 1, b.seq + 1))
                    last = b.seq
                # A comment line every 15s is how a page OBS has closed gets
                # noticed: the write fails, and it stops counting as a listener.
                msg = "".join('data: {"n": %d}\n\n' % n for n in new) or ": ping\n\n"
                self.wfile.write(msg.encode())
                self.wfile.flush()
        except OSError:
            pass                      # OBS closed the source; normal
        finally:
            with b.cv:
                b.clients -= 1
            log("Tts page disconnected (%d)" % b.clients)


# ---------------------------------------------------------------------------
# the feed


class Throttled(Exception):
    """YouTube answered 429; logged once, and every read waits out the hold."""


class YouTubeChat:
    """YouTube live chat read straight from youtube.com, while Restream can't.

    Restream can hold on to a YouTube chat that has ended and keep reporting
    `youtube_livechat_ended` on every fresh connection, with the broadcast
    live and its chat open -- seen 2026-10-30, live 22 minutes with YouTube
    silent. Nothing over Restream's socket fixes that, so while Restream says
    YouTube is anything but connected, this polls the channel's own live chat
    the way the popout chat does: the "Live chat" view, every message, not
    "Top chat". It stops the moment Restream reports YouTube connected, so a
    line is never read from both. Undocumented like the embed socket: when
    YouTube moves it, this logs and retries and Restream is no worse off.

    YouTube answers an address that reads too much with 429, and the limit is
    per address, not per request -- so one 429 holds every read from every
    thread, a minute at first and doubling to fifteen while they keep coming.
    """

    UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
          "(KHTML, like Gecko) Chrome/127.0 Safari/537.36")
    HOLD_MIN, HOLD_MAX = 60.0, 900.0

    def __init__(self, on_line) -> None:
        self.on_line = on_line
        self.wanted = threading.Event()
        self.lock = threading.Lock()
        self.hold = self.HOLD_MIN
        self.hold_until = 0.0
        self.done: set[str] = set()   # videos that can never be live again

    def want(self, on: bool) -> None:
        if on != self.wanted.is_set():
            log("YouTube direct read %s" % ("on -- Restream cannot reach it"
                                            if on else "off -- Restream has it"))
        (self.wanted.set if on else self.wanted.clear)()

    def _req(self, url: str, body: dict | None = None):
        while (wait := self.hold_until - time.time()) > 0:
            time.sleep(wait)
        h = {"User-Agent": self.UA, "Accept-Language": "en-US,en;q=0.9",
             "Cookie": "CONSENT=YES+1"}
        data = None
        if body is not None:
            data = json.dumps(body).encode()
            h["Content-Type"] = "application/json"
        req = urllib.request.Request(url, data=data, headers=h)
        try:
            with urllib.request.urlopen(req, timeout=15) as r:
                raw = r.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            if e.code != 429:
                raise
            with self.lock:
                # Threads that sent together all get the 429; the first one
                # back sets the hold, and the rest must not double it again.
                if self.hold_until <= time.time():
                    after = e.headers.get("Retry-After", "")
                    hold = max(self.hold, float(after) if after.isdigit() else 0)
                    self.hold_until = time.time() + hold
                    self.hold = min(self.hold * 2, self.HOLD_MAX)
                    log("YouTube is rate-limiting this address (429) -- "
                        "holding every read for %ds" % hold)
            raise Throttled() from None
        self.hold = self.HOLD_MIN
        return json.loads(raw) if body is not None else raw

    def _live_videos(self, skip: set[str]) -> list[str]:
        """Every broadcast live on the channel and not in `skip`.

        With the vertical output that is two -- the main one and the Shorts
        one, each with its own chat -- and /live names only one of them. So
        the channel's feed is walked too, asking each recent video whether it
        is live now. Each answer is a watch page of over a megabyte, so one is
        never asked twice: not while it is being followed, and never again once
        it is over. Asking all six every minute is the likeliest reason this
        address drew a 429 on 2026-10-30.
        """
        page = self._req("https://www.youtube.com/@%s/live" % YT_HANDLE)
        vids = []
        m = re.search(r'<link rel="canonical" href="https://www\.youtube\.com/'
                      r'watch\?v=([\w-]{11})"', page)
        if m and '"isLive":true' in page and m.group(1) not in skip:
            vids.append(m.group(1))
        cid = re.search(r'"(?:channelId|externalId)":"(UC[\w-]{22})"', page)
        if cid:
            feed = self._req("https://www.youtube.com/feeds/videos.xml"
                             "?channel_id=" + cid.group(1))
            for vid in re.findall(r"<yt:videoId>([\w-]{11})<", feed)[:6]:
                if vid in vids or vid in skip or vid in self.done:
                    continue
                watch = self._req("https://www.youtube.com/watch?v=" + vid)
                if '"isLiveNow":true' in watch:
                    vids.append(vid)
                elif '"videoDetails"' in watch and '"isUpcoming":true' not in watch:
                    # A real watch page, neither live nor scheduled: an ended
                    # broadcast or an upload. Anything else is asked again.
                    self.done.add(vid)
        return vids

    @staticmethod
    def _line(item: dict) -> dict | None:
        r = (item.get("liveChatTextMessageRenderer")
             or item.get("liveChatPaidMessageRenderer"))
        if not r:
            return None
        # Emoji runs carry no text and are dropped anyway when cleaned.
        text = "".join(run.get("text", "")
                       for run in (r.get("message") or {}).get("runs", []))
        name = (r.get("authorName") or {}).get("simpleText", "").lstrip("@")
        return {"platform": "YouTube", "name": name, "text": text.strip(),
                "bot": False}

    def _follow(self, vid: str) -> None:
        page = self._req("https://www.youtube.com/live_chat?is_popout=1&v=" + vid)
        ver = re.search(r'"INNERTUBE_CLIENT_VERSION":"([^"]+)"', page).group(1)
        # The view selector's second entry is "Live chat"; the page itself
        # opens on "Top chat", which YouTube filters.
        conts = re.findall(r'"reloadContinuationData":\{"continuation":"([^"]+)"',
                           page)
        cont = conts[1] if len(conts) > 1 else \
            re.search(r'"continuation":"([^"]+)"', page).group(1)
        ctx = {"client": {"clientName": "WEB", "clientVersion": ver, "hl": "en"}}
        log("YouTube direct read following %s" % vid)
        first = True
        while self.wanted.is_set():
            try:
                d = self._req("https://www.youtube.com/youtubei/v1/live_chat/"
                              "get_live_chat?prettyPrint=false",
                              {"context": ctx, "continuation": cont})
            except Throttled:
                # Same continuation once the hold lapses, rather than the
                # popout page again. A hold is a minute or more, so what piled
                # up meanwhile is stale: skipped like the backlog.
                first = True
                continue
            lc =(d.get("continuationContents") or {}).get("liveChatContinuation")
            if not lc:
                log("YouTube chat %s ended" % vid)
                return
            for a in lc.get("actions", []):
                line = self._line((a.get("addChatItemAction") or {})
                                  .get("item") or {})
                # The first answer to a reload is the backlog: already said.
                if line and not first:
                    self.on_line(line)
            first = False
            c = (lc.get("continuations") or [{}])[0]
            nxt = (c.get("invalidationContinuationData")
                   or c.get("timedContinuationData") or {})
            if not nxt.get("continuation"):
                return
            cont = nxt["continuation"]
            # At the pace YouTube's answer asks for, never ahead of it.
            time.sleep(min(max(nxt.get("timeoutMs", 5000), 1000), 10000) / 1000)

    def run(self) -> None:
        # One thread per live broadcast; the channel is re-read every minute
        # so a broadcast that starts later is picked up too.
        following: set[str] = set()
        lock = threading.Lock()

        def follow(vid: str) -> None:
            try:
                self._follow(vid)
            except Throttled:
                pass                  # _req has said so, once per hold
            except Exception as e:
                log("YouTube direct read of %s failed: %r" % (vid, e))
            with lock:
                following.discard(vid)

        while True:
            self.wanted.wait()
            try:
                with lock:
                    skip = set(following)
                vids = self._live_videos(skip)
                if not vids and not skip:
                    log("YouTube direct read: @%s is not live" % YT_HANDLE)
                for vid in vids:
                    with lock:
                        if vid in following:
                            continue
                        following.add(vid)
                    threading.Thread(target=follow, args=(vid,), name="yt-" + vid,
                                     daemon=True).start()
            except Throttled:
                pass
            except Exception as e:
                log("YouTube direct read failed: %r" % e)
            time.sleep(60)


class Feed:
    def __init__(self, raw: bool, yt: YouTubeChat) -> None:
        self.raw = raw
        self.yt = yt
        self.conns: dict[str, int] = {}   # connectionUuid -> eventSourceId
        self.seen_types: set[int] = set()

    def handle(self, msg: dict) -> dict | None:
        if self.raw:
            log("raw " + json.dumps(msg, ensure_ascii=False))
        action, p = msg.get("action"), msg.get("payload") or {}
        if action == "connection_info":
            src = p.get("eventSourceId")
            self.conns[p.get("connectionUuid")] = src
            why = (": " + p["reason"]) if p.get("reason") else ""
            log("%s %s%s" % (SOURCES.get(src, "source %s" % src),
                             p.get("status"), why))
            if src == 13:
                self.yt.want(p.get("status") != "connected")
        elif action == "connection_closed":
            src = self.conns.pop(p.get("connectionUuid"), None)
            log("%s closed" % SOURCES.get(src, "a connection"))
        elif action == "event":
            line = normalise(p)
            if line is not None:
                return line
            t = p.get("eventTypeId")
            if t not in self.seen_types:
                self.seen_types.add(t)
                log("(event type %s from %s is not chat -- ignored)"
                    % (t, SOURCES.get(p.get("eventSourceId"), "?")))
        return None


def run(a: argparse.Namespace, reader: Reader, blocklist: Blocklist) -> None:
    def speak(line: dict) -> None:
        # Isolated: a message that trips a bug here is one lost line,
        # not a dropped socket -- and a reconnect replays nothing.
        try:
            log("chat %-7s %s%s: %s" % (
                line["platform"], line["name"],
                " (bot)" if line["bot"] else "", line["text"]))
            sentence, why = decide(line, blocklist, a.read_own)
            if sentence:
                reader.push(sentence)
            else:
                log("  skipped: " + why)
        except Exception as e:
            log("  could not handle that line: %r" % e)

    yt = YouTubeChat(speak)
    threading.Thread(target=yt.run, name="youtube", daemon=True).start()
    feed = Feed(a.raw, yt)
    token = a.token
    backoff = 1.0
    while True:
        if not a.token:
            try:
                token = embed_token(a.obs_host, a.obs_port,
                                    a.obs_password or obs_password())
            except (OSError, ConnectionError, LookupError) as e:
                if not token:
                    log("waiting for OBS: %s" % e)
                    time.sleep(min(backoff, 30))
                    backoff = min(backoff * 2, 30)
                    continue
                # OBS gone mid-session: the last token still works.
        url = "wss://%s%s?token=%s" % (EMBED_HOST, EMBED_PATH,
                                       urllib.parse.quote(token))
        started = time.time()
        ws = None
        try:
            ws = WS(url, {"Origin": EMBED_ORIGIN, "User-Agent": "Mozilla/5.0"},
                    timeout=SILENCE_LIMIT)
            log("connected to Restream chat")
            while True:
                line = feed.handle(ws.recv())
                if line:
                    speak(line)
        except socket.timeout:
            log("no frame for %ds -- reconnecting" % SILENCE_LIMIT)
        except (OSError, ConnectionError, ValueError) as e:
            log("disconnected: %s" % e)
        finally:
            if ws:
                ws.close()
        feed.conns.clear()
        if time.time() - started > 60:
            backoff = 1.0
        log("retrying in %ds" % backoff)
        time.sleep(backoff)
        backoff = min(backoff * 2, 60)


def main() -> None:
    ap = argparse.ArgumentParser(prog="chat-bridge")
    ap.add_argument("--play", action="store_true",
                    help="speak on this machine's default output instead of "
                         "through the Tts browser source")
    ap.add_argument("--port", type=int, default=TTS_PORT)
    ap.add_argument("--no-blocklist", action="store_true",
                    help="run without chat/blocklist.txt, reading everything")
    ap.add_argument("--say", metavar="TEXT",
                    help="speak one line as if from Twitch chat, then exit")
    ap.add_argument("--read-own", action="store_true",
                    help="read your own accounts too, for testing")
    ap.add_argument("--wav-dir", type=Path,
                    help="also write every spoken line here as a WAV")
    ap.add_argument("--voice", type=Path, default=VOICE)
    ap.add_argument("--raw", action="store_true",
                    help="log every frame from Restream as it arrives")
    ap.add_argument("--token", default=os.environ.get("RESTREAM_EMBED_TOKEN", ""),
                    help="embed token; default reads it from OBS's Chat source")
    ap.add_argument("--obs-host", default="127.0.0.1")
    ap.add_argument("--obs-port", type=int, default=4455)
    ap.add_argument("--obs-password", default=os.environ.get("OBS_WS_PASSWORD", ""),
                    help="defaults to $OBS_WS_PASSWORD, then OBS's own config file")
    a = ap.parse_args()

    # Piped or redirected on Windows, stdout is cp1252, and the first emoji in
    # chat raises UnicodeEncodeError -- a ValueError, which the feed loop would
    # take for a bad frame and reconnect over.
    sys.stdout.reconfigure(errors="backslashreplace", line_buffering=True)
    below_normal()
    blocklist = Blocklist(BLOCKLIST, required=not a.no_blocklist)
    if not blocklist.ready():
        # Exit 2 tells start.py this is a setup problem, not a crash -- there
        # is no point restarting into the same missing file.
        print("error: %s is missing or has no entries, and TTS reads nothing\n"
              "       without one. It is gitignored: copy it from your other\n"
              "       machine, or pass --no-blocklist to read everything."
              % BLOCKLIST, flush=True)
        sys.exit(2)

    browser = Browser()
    play = play_here if (a.play or a.say is not None) else browser.play
    reader = Reader(Voice(a.voice), play, a.wav_dir)
    if a.say is not None:
        sentence, why = decide({"platform": "Twitch", "name": "tester",
                                "text": a.say, "bot": False}, blocklist)
        if sentence:
            reader.say(sentence)
        else:
            log("skipped: " + why)
        return

    Handler.browser = browser
    try:
        # 127.0.0.1, never 0.0.0.0 -- binding to all interfaces trips the
        # Windows Firewall dialog on every new machine.
        srv = ThreadingHTTPServer(("127.0.0.1", a.port), Handler)
    except OSError as e:
        print("error: cannot listen on 127.0.0.1:%d (%s) -- is another "
              "chat-bridge already running?" % (a.port, e), flush=True)
        sys.exit(2)
    srv.daemon_threads = True
    threading.Thread(target=srv.serve_forever, name="http", daemon=True).start()
    log("Tts page at http://127.0.0.1:%d/tts.html" % a.port)

    reader.start()
    try:
        run(a, reader, blocklist)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()

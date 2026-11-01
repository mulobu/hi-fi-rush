#!/usr/bin/env python3
"""
start -- everything that has to be running while you stream, in one command.

    python3 start.py                 Windows: py -3 start.py
    python3 start.py --overlay hi-fi-rush
                                     today's show: OBS on that overlay's
                                     scene collection
    python3 start.py --overlay hi-fi-rush --profile vALO
                                     ...and on that Restream setup
    python3 start.py --display 1     mascot follows the cursor on display 1
    python3 start.py --only chat     just one bridge: mascot or chat
    python3 start.py --no-obs        do not launch OBS

Starts, in this order:

    mascot  mascot/bridge/cursor-bridge.py   127.0.0.1:4460   Mascot, MascotV
    chat    chat/chat-bridge.py              127.0.0.1:4461   Tts
    OBS     only if it is not already running, once both bridges listen

With --overlay, OBS launches straight into the overlay's scene collection
(overlays/<name>/overlay.json), and an OBS that is already running is
switched to it over the websocket -- never while anything is live, since a
collection switch reloads every source. --profile does the same for the
profile, which picks the Restream setup and so the game. An overlay with no
mascot gets no mascot bridge. Without --overlay, OBS opens on whatever it
had last, as before.

Bridges first, so each browser source finds its page on the first try rather
than on a retry. Every line a bridge prints comes out here prefixed with its
name. A bridge that crashes after running a while is restarted with backoff;
one that dies in its first seconds -- a missing file, a port already taken --
is reported and left down, because restarting into the same problem only
fills the log. A bridge already listening on its port is left alone.

Ctrl-C stops both bridges. OBS is left running: closing it is not this
script's call. On Windows the bridges live in a job object that dies with
this process, so even a hard kill cannot leave one behind holding its port.

The first run on a machine also builds what the chat bridge needs and git does
not carry: chat/.venv with Piper, and the lessac voice from Hugging Face,
checksum verified. The one thing it cannot fetch is chat/blocklist.txt -- it
is gitignored and personal, so copy it across; without it the chat bridge
refuses to start and says why.

Standard library only.
"""

from __future__ import annotations

import argparse
import ctypes
import hashlib
import importlib.util
import json
import os
import shutil
import socket
import subprocess
import sys
import threading
import time
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parent
WIN = sys.platform.startswith("win")


def load_contract() -> dict:
    """core/contract.js, whose body is strict JSON (docs/adr/0004)."""
    text = (REPO / "core" / "contract.js").read_text(encoding="utf-8")
    start = text.index("=", text.index("window.OVERLAY_CONTRACT")) + 1
    return json.loads(text[start:text.rindex("}") + 1])


PORTS = load_contract()["ports"]
MASCOT_PORT = PORTS["mascot"]
TTS_PORT = PORTS["chat"]              # chat-bridge.py's default must match
OBS_WS_PORT = PORTS["obs"]

CHAT = REPO / "chat"
VENV = CHAT / ".venv"
VENV_PY = VENV / ("Scripts/python.exe" if WIN else "bin/python")
PIPER = "piper-tts==1.8.0"
VOICE_URL = ("https://huggingface.co/rhasspy/piper-voices/resolve/main/"
             "en/en_US/lessac/medium/")
VOICE_FILES = {                       # name -> (bytes, md5), from voices.json
    "en_US-lessac-medium.onnx": (63201294, "2fc642b535197b6305c7c8f92dc8b24f"),
    "en_US-lessac-medium.onnx.json": (4885, "c1f2b7bddefe113f3255ff9ef234cfd3"),
}

MIN_UPTIME = 8.0                      # died sooner than this: setup problem
OBS_EXE = Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / \
    "obs-studio/bin/64bit/obs64.exe"

print_lock = threading.Lock()


def say(tag: str, msg: str) -> None:
    with print_lock:
        print("%-7s %s" % ("[%s]" % tag, msg), flush=True)


def listening(port: int) -> bool:
    s = socket.socket()
    s.settimeout(0.3)
    try:
        s.connect(("127.0.0.1", port))
        return True
    except OSError:
        return False
    finally:
        s.close()


# ---------------------------------------------------------------------------
# Windows: a job object, so the bridges cannot outlive this process


class Job:
    """JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE. The handle closes when this process
    exits however it exits -- Ctrl-C, the window closed, Task Manager -- and
    Windows kills everything assigned to it."""

    def __init__(self) -> None:
        self.h = None
        if not WIN:
            return
        k32 = ctypes.WinDLL("kernel32", use_last_error=True)
        k32.CreateJobObjectW.restype = ctypes.c_void_p
        k32.OpenProcess.restype = ctypes.c_void_p

        class Basic(ctypes.Structure):
            _fields_ = [("PerProcessUserTimeLimit", ctypes.c_int64),
                        ("PerJobUserTimeLimit", ctypes.c_int64),
                        ("LimitFlags", ctypes.c_uint32),
                        ("MinimumWorkingSetSize", ctypes.c_size_t),
                        ("MaximumWorkingSetSize", ctypes.c_size_t),
                        ("ActiveProcessLimit", ctypes.c_uint32),
                        ("Affinity", ctypes.c_size_t),
                        ("PriorityClass", ctypes.c_uint32),
                        ("SchedulingClass", ctypes.c_uint32)]

        class IO(ctypes.Structure):
            _fields_ = [(n, ctypes.c_uint64) for n in (
                "ReadOperationCount", "WriteOperationCount", "OtherOperationCount",
                "ReadTransferCount", "WriteTransferCount", "OtherTransferCount")]

        class Extended(ctypes.Structure):
            _fields_ = [("BasicLimitInformation", Basic), ("IoInfo", IO),
                        ("ProcessMemoryLimit", ctypes.c_size_t),
                        ("JobMemoryLimit", ctypes.c_size_t),
                        ("PeakProcessMemoryUsed", ctypes.c_size_t),
                        ("PeakJobMemoryUsed", ctypes.c_size_t)]

        info = Extended()
        info.BasicLimitInformation.LimitFlags = 0x2000  # KILL_ON_JOB_CLOSE
        h = k32.CreateJobObjectW(None, None)
        if h and k32.SetInformationJobObject(
                ctypes.c_void_p(h), 9,  # JobObjectExtendedLimitInformation
                ctypes.byref(info), ctypes.sizeof(info)):
            self.h, self.k32 = h, k32

    def add(self, pid: int) -> None:
        if not self.h:
            return
        hp = self.k32.OpenProcess(0x0101, False, pid)  # SET_QUOTA | TERMINATE
        if hp:
            self.k32.AssignProcessToJobObject(ctypes.c_void_p(self.h),
                                              ctypes.c_void_p(hp))
            self.k32.CloseHandle(ctypes.c_void_p(hp))


# ---------------------------------------------------------------------------
# first run: what the chat bridge needs that git does not carry


def md5(path: Path) -> str:
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def ensure_chat() -> bool:
    """Build chat/.venv and fetch the voice if missing. False: cannot run."""
    if not VENV_PY.exists():
        say("setup", "creating chat/.venv")
        subprocess.check_call([sys.executable, "-m", "venv", str(VENV)])
    if subprocess.run([str(VENV_PY), "-c", "import piper"],
                      capture_output=True).returncode:
        say("setup", "installing %s into chat/.venv (one time, ~50 MB)" % PIPER)
        subprocess.check_call([str(VENV_PY), "-m", "pip", "install",
                               "--disable-pip-version-check", "-q", PIPER])
    voices = CHAT / "voices"
    voices.mkdir(exist_ok=True)
    for name, (size, digest) in VOICE_FILES.items():
        dest = voices / name
        if dest.exists() and dest.stat().st_size == size:
            continue
        say("setup", "downloading %s (%.0f MB)" % (name, size / 1e6))
        part = dest.with_suffix(dest.suffix + ".part")
        with urllib.request.urlopen(VOICE_URL + name, timeout=60) as r, \
                open(part, "wb") as f:
            shutil.copyfileobj(r, f)
        if md5(part) != digest:
            part.unlink()
            say("setup", "%s failed its checksum -- not used" % name)
            return False
        part.replace(dest)
    if not (CHAT / "blocklist.txt").exists():
        say("chat", "chat/blocklist.txt is missing -- it is gitignored, so copy "
                    "it from your other machine. Chat TTS stays off until then.")
        return False
    return True


# ---------------------------------------------------------------------------
# supervision


class Bridge:
    def __init__(self, tag: str, cmd: list, port: int, job: Job) -> None:
        self.tag, self.cmd, self.port, self.job = tag, cmd, port, job
        self.proc = None
        self.stopping = False

    def _pipe(self, proc) -> None:
        for line in proc.stdout:
            say(self.tag, line.rstrip())

    def _spawn(self):
        env = dict(os.environ, PYTHONUNBUFFERED="1", PYTHONIOENCODING="utf-8")
        flags = {}
        if WIN:
            # Its own process group: the console's Ctrl-C reaches only this
            # script, which then stops the bridges itself -- otherwise a bridge
            # dies of the same Ctrl-C and gets "restarted" on the way out.
            flags["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
        else:
            flags["start_new_session"] = True
        proc = subprocess.Popen(self.cmd, cwd=str(REPO), env=env,
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                text=True, encoding="utf-8", errors="replace",
                                **flags)
        self.job.add(proc.pid)
        threading.Thread(target=self._pipe, args=(proc,), daemon=True).start()
        return proc

    def run(self) -> None:
        backoff = 1.0
        while not self.stopping:
            started = time.time()
            self.proc = self._spawn()
            code = self.proc.wait()
            if self.stopping:
                return
            up = time.time() - started
            if up < MIN_UPTIME:
                say(self.tag, "exited %d after %.0fs -- a setup problem, not a "
                              "crash; not restarting. See the lines above."
                    % (code, up))
                return
            if up > 60:
                backoff = 1.0
            say(self.tag, "exited %d -- restarting in %ds" % (code, backoff))
            time.sleep(backoff)
            backoff = min(backoff * 2, 30)

    def start(self) -> threading.Thread:
        t = threading.Thread(target=self.run, name=self.tag, daemon=True)
        t.start()
        return t

    def stop(self) -> None:
        self.stopping = True
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(5)
            except subprocess.TimeoutExpired:
                self.proc.kill()


# ---------------------------------------------------------------------------
# OBS


def obs_running() -> bool:
    if listening(OBS_WS_PORT):
        return True
    try:
        if WIN:
            out = subprocess.run(["tasklist", "/FI", "IMAGENAME eq obs64.exe", "/NH"],
                                 capture_output=True, text=True).stdout
            return "obs64.exe" in out
        if sys.platform == "darwin":
            return subprocess.run(["pgrep", "-x", "OBS"],
                                  capture_output=True).returncode == 0
        return subprocess.run(["pgrep", "-x", "obs"],
                              capture_output=True).returncode == 0
    except OSError:
        return False


def launch_obs(flags: list) -> None:
    """Detached: OBS must outlive this script, and must not get its Ctrl-C.
    `flags` are OBS's own: --collection, --profile."""
    if WIN:
        if not OBS_EXE.exists():
            say("obs", "not found at %s -- start it yourself" % OBS_EXE)
            return
        # OBS has to start in its own bin folder or it cannot find its locale
        # files and quits.
        subprocess.Popen([str(OBS_EXE)] + flags, cwd=str(OBS_EXE.parent),
                         creationflags=0x00000008 | 0x00000200,  # DETACHED | NEW_GROUP
                         close_fds=True)
    elif sys.platform == "darwin":
        subprocess.Popen(["open", "-a", "OBS"] + (["--args"] + flags if flags else []))
    else:
        exe = shutil.which("obs")
        if not exe:
            say("obs", "not on PATH -- start it yourself")
            return
        subprocess.Popen([exe] + flags, start_new_session=True)
    say("obs", "launched" + (" " + " ".join(flags) if flags else ""))


def switch_obs(collection: str, profile: str) -> None:
    """Put a running OBS on this collection and profile, over the websocket.
    Borrows obs-setup.py's client rather than carrying a second one. Refused
    while anything is live: either switch reloads sources or outputs."""
    spec = importlib.util.spec_from_file_location("obs_setup", REPO / "tools/obs-setup.py")
    setup = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(setup)
    try:
        obs = setup.OBS("127.0.0.1", OBS_WS_PORT, setup.discover_password())
    except OSError as e:
        say("obs", "running, but the websocket is not reachable (%s) -- switch "
                   "the collection by hand" % e)
        return
    try:
        cl = obs.req("GetSceneCollectionList")
        pl = obs.req("GetProfileList")
        moves = []
        if collection and cl["currentSceneCollectionName"] != collection:
            if collection not in cl["sceneCollections"]:
                say("obs", "no scene collection %r yet -- build it with "
                           "tools/obs-setup.py --overlay" % collection)
            else:
                moves.append("collection")
        if profile and pl["currentProfileName"] != profile:
            if profile not in pl["profiles"]:
                say("obs", "no profile %r -- have: %s"
                    % (profile, ", ".join(pl["profiles"])))
            else:
                moves.append("profile")
        if not moves:
            say("obs", "already on %s" % ", ".join(
                filter(None, [collection and "collection %r" % collection,
                              profile and "profile %r" % profile])))
            return
        live = setup.outputs_live(obs)
        if live:
            say("obs", "%s is running, so the %s stays as it is -- switching "
                       "would reload it mid-stream" % (" and ".join(live),
                                                       " and ".join(moves)))
            return
        if "collection" in moves:
            obs.req("SetCurrentSceneCollection", {"sceneCollectionName": collection})
            say("obs", "switched to scene collection %r" % collection)
        if "profile" in moves:
            obs.switch_profile(profile)
            say("obs", "switched to profile %r" % profile)
    finally:
        obs.ws.close()


# ---------------------------------------------------------------------------


def main() -> None:
    sys.stdout.reconfigure(errors="backslashreplace")
    ap = argparse.ArgumentParser(prog="start", description=__doc__.split("\n\n")[0])
    ap.add_argument("--display", type=int, default=0,
                    help="mascot: which display the cursor is read from "
                         "(see mascot/bridge/cursor-bridge.py --list-displays)")
    ap.add_argument("--only", choices=["mascot", "chat"],
                    help="start just one bridge")
    ap.add_argument("--no-obs", action="store_true",
                    help="do not launch OBS if it is not running")
    ap.add_argument("--overlay", default="", metavar="NAME",
                    help="today's overlay: OBS on overlays/NAME's scene collection")
    ap.add_argument("--profile", default="", metavar="NAME",
                    help="today's OBS profile, i.e. Restream setup")
    a = ap.parse_args()

    collection, mascot = "", True
    if a.overlay:
        cfg_file = REPO / "overlays" / a.overlay / "overlay.json"
        try:
            cfg = json.loads(cfg_file.read_text(encoding="utf-8"))
        except (OSError, ValueError) as e:
            raise SystemExit("start: cannot read %s (%s)" % (cfg_file, e))
        collection, mascot = cfg["collection"], bool(cfg.get("mascot"))
        say("start", "overlay %s -- collection %r%s" % (
            a.overlay, collection, "" if mascot else ", no mascot"))

    job = Job()
    bridges = []
    if a.only in (None, "mascot") and not mascot:
        say("mascot", "this overlay has none -- not started")
    elif a.only in (None, "mascot"):
        if listening(MASCOT_PORT):
            say("mascot", "already listening on %d -- leaving it" % MASCOT_PORT)
        else:
            bridges.append(Bridge("mascot", [sys.executable, "-u",
                                  str(REPO / "mascot/bridge/cursor-bridge.py"),
                                  "--display", str(a.display)], MASCOT_PORT, job))
    if a.only in (None, "chat"):
        if listening(TTS_PORT):
            say("chat", "already listening on %d -- leaving it" % TTS_PORT)
        elif ensure_chat():
            bridges.append(Bridge("chat", [str(VENV_PY), "-u",
                                  str(CHAT / "chat-bridge.py")], TTS_PORT, job))

    threads = [b.start() for b in bridges]

    flags = ((["--collection", collection] if collection else []) +
             (["--profile", a.profile] if a.profile else []))
    if not a.no_obs and not obs_running():
        deadline = time.time() + 15
        while time.time() < deadline and not all(listening(b.port) for b in bridges):
            time.sleep(0.25)
        launch_obs(flags)
    elif not a.no_obs and flags:
        switch_obs(collection, a.profile)

    if not bridges:
        say("start", "nothing to supervise")
        return
    say("start", "running %s -- Ctrl-C to stop" % " + ".join(b.tag for b in bridges))
    try:
        # A supervisor thread ends only when its bridge is given up on.
        while any(t.is_alive() for t in threads):
            time.sleep(0.5)
        say("start", "every bridge is down")
    except KeyboardInterrupt:
        pass
    finally:
        for b in bridges:
            b.stop()
        say("start", "stopped")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
hero-asset.py -- turn a Seedance look-around video into a scrubbable sprite sheet.

Runs identically on macOS and Windows. Depends on ffmpeg/ffprobe being on PATH.
Only the `plate` subcommand needs anything else (rembg), and only if your source
image does not already have an alpha channel.

Subcommands
  plate   source image        -> flat-chroma plate to upload to Seedance
  probe   generated video     -> dimensions, fps, frame count, duration
  scrub   generated video     -> timestamped stills, for picking the loop in/out
  build   generated video     -> keyed frames + sprite sheet + manifest.json
  verify  sprite folder       -> mapping and smoothness diagnostics

See README.md for the full workflow.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

# ---------------------------------------------------------------------------
# chroma

COLORS = {
    "green": {"hex": "0x00FF00", "despill": "green"},
    "blue": {"hex": "0x0000FF", "despill": "blue"},
    # despill only knows green and blue; magenta keys clean but gets no despill
    "magenta": {"hex": "0xFF00FF", "despill": None},
}

INSTALL = {
    "darwin": "  brew install ffmpeg",
    "win32": "  winget install Gyan.FFmpeg      (or: choco install ffmpeg)",
}

# ---------------------------------------------------------------------------
# plumbing


def die(msg: str) -> "None":
    sys.stderr.write("error: " + msg + "\n")
    sys.exit(1)


def need(name: str) -> str:
    found = shutil.which(name)
    if found:
        return found
    hint = INSTALL.get(sys.platform, "  install it from https://ffmpeg.org/download.html")
    die("'%s' is not on your PATH.\n%s" % (name, hint))
    return ""


def run(args: list, check: bool = True) -> subprocess.CompletedProcess:
    """Run a command, capture stderr (ffmpeg logs there), fail loudly."""
    proc = subprocess.run(
        args,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if check and proc.returncode != 0:
        sys.stderr.write((proc.stderr or "")[-4000:])
        die("%s exited %d" % (Path(args[0]).name, proc.returncode))
    return proc


def run_bytes(args: list) -> bytes:
    """Run a command and return raw stdout. Used for rawvideo pipes."""
    proc = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if proc.returncode != 0:
        sys.stderr.write(proc.stderr.decode("utf-8", "replace")[-4000:])
        die("%s exited %d" % (Path(args[0]).name, proc.returncode))
    return proc.stdout


def step(msg: str) -> None:
    print("  -> " + msg, flush=True)


def probe_video(path: Path) -> dict:
    out = run([
        need("ffprobe"), "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "stream=width,height,r_frame_rate,nb_read_frames,duration",
        "-count_frames",
        "-of", "json", str(path),
    ]).stdout
    streams = json.loads(out).get("streams") or []
    if not streams:
        die("no video stream in %s" % path)
    s = streams[0]
    num, _, den = (s.get("r_frame_rate") or "0/1").partition("/")
    fps = float(num) / float(den or 1) if float(den or 1) else 0.0
    return {
        "width": int(s["width"]),
        "height": int(s["height"]),
        "fps": fps,
        "frames": int(s.get("nb_read_frames") or 0),
        "duration": float(s.get("duration") or 0.0),
    }


def trim_args(start, end) -> list:
    a = []
    if start is not None:
        a += ["-ss", str(start)]
    if end is not None:
        a += ["-to", str(end)]
    return a


def interp_chain(a: argparse.Namespace) -> str:
    fps = float(getattr(a, "interp_fps", 0.0) or 0.0)
    if fps <= 0:
        return ""
    return "minterpolate=fps=%g," % fps


def join_filters(*parts: str) -> str:
    return ",".join(p.strip(",") for p in parts if p)


def norm_angle(deg: float) -> float:
    return deg % 360.0


def shortest_angle(a: float, b: float) -> float:
    return ((b - a + 540.0) % 360.0) - 180.0


def circular_mean(angles: list) -> float:
    sx = sum(math.cos(math.radians(a)) for a in angles)
    sy = sum(math.sin(math.radians(a)) for a in angles)
    return math.degrees(math.atan2(sy, sx)) % 360.0


NAMED_ANGLES = {
    "up": 0.0,
    "upper-right": 45.0,
    "upright": 45.0,
    "right-up": 45.0,
    "right": 90.0,
    "lower-right": 135.0,
    "bottom-right": 135.0,
    "down-right": 135.0,
    "down": 180.0,
    "bottom": 180.0,
    "lower-left": 225.0,
    "bottom-left": 225.0,
    "down-left": 225.0,
    "left": 270.0,
    "upper-left": 315.0,
    "upleft": 315.0,
    "left-up": 315.0,
}


def parse_calibration(specs: "list | None", frames: int) -> list:
    pairs = []
    for spec in specs or []:
        for part in spec.split(","):
            part = part.strip()
            if not part:
                continue
            name, sep, frame = part.partition("=")
            if not sep:
                die("--calibrate entries must look like direction=frame, got %r" % part)
            key = name.strip().lower()
            if key in NAMED_ANGLES:
                angle = NAMED_ANGLES[key]
            else:
                try:
                    angle = float(key)
                except ValueError:
                    die("unknown calibration direction %r" % name)
            try:
                idx = int(frame) - 1
            except ValueError:
                die("calibration frame must be a number, got %r" % frame)
            if idx < 0 or idx >= frames:
                die("calibration frame %d is outside 1..%d" % (idx + 1, frames))
            pairs.append((idx, angle, part))
    return pairs


def calibrated_angles(frames: int, pairs: list) -> tuple:
    dpf = 360.0 / frames
    candidates = []
    for direction, name in ((1, "clockwise"), (-1, "counterclockwise")):
        offsets = [norm_angle(angle - direction * idx * dpf)
                   for idx, angle, _label in pairs]
        offset = circular_mean(offsets)
        errors = [abs(shortest_angle(norm_angle(offset + direction * idx * dpf), angle))
                  for idx, angle, _label in pairs]
        candidates.append((sum(errors), max(errors), offset, direction, name, errors))
    _total, _worst, offset, direction, name, errors = min(candidates)
    angles = [round(norm_angle(offset + direction * i * dpf), 2)
              for i in range(frames)]
    return angles, name, errors


HEX_RE = re.compile(r"^0x[0-9A-Fa-f]{6}$")


def key_chain(color: str, sim: float, blend: float, despill: bool,
              key_hex: "str | None" = None) -> str:
    spec = COLORS[color]
    if key_hex:
        # Generators almost never produce exactly 0x00FF00; keying the colour
        # that is actually there beats forcing the plate to match the default.
        spec = dict(spec, hex=key_hex)
    # chromakey works in YUV; everything downstream (despill, alphaextract, the
    # PNG encoder) wants a packed RGBA frame, and will not negotiate it alone.
    chain = "chromakey=%s:%s:%s,format=rgba" % (spec["hex"], sim, blend)
    if despill and spec["despill"]:
        chain += ",despill=type=%s" % spec["despill"]
    return chain


BBOX = re.compile(r"x1:(\d+)\s+x2:(\d+)\s+y1:(\d+)\s+y2:(\d+)")


def sample_patch(path: Path, x: str, y: str, n: int = 32) -> list:
    """Raw pixels of one n-by-n square of the first frame, as (r,g,b) tuples."""
    proc = subprocess.run([
        need("ffmpeg"), "-v", "error", "-i", str(path),
        "-vf", "crop=%d:%d:%s:%s,format=rgb24" % (n, n, x, y),
        "-frames:v", "1", "-f", "rawvideo", "-",
    ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    raw = proc.stdout
    if proc.returncode != 0 or len(raw) < n * n * 3:
        sys.stderr.write(proc.stderr.decode("utf-8", "replace")[-2000:])
        die("could not sample %s" % path)
    return [(raw[i], raw[i + 1], raw[i + 2]) for i in range(0, n * n * 3, 3)]


def patch_stats(px: list) -> tuple:
    """(average as 0xRRGGBB, worst per-channel min-max range) for one patch."""
    n = len(px)
    avg = tuple(sum(p[i] for p in px) // n for i in range(3))
    rng = max(max(p[i] for p in px) - min(p[i] for p in px) for i in range(3))
    return "0x%02X%02X%02X" % avg, rng


def cmd_bg(a: argparse.Namespace) -> None:
    src = Path(a.source)
    if not src.is_file():
        die("no such file: %s" % src)

    m, n = a.margin, a.size
    corners = [
        ("top-left", str(m), str(m)),
        ("top-right", "iw-%d-in_w" % m, str(m)),
        ("bottom-left", str(m), "ih-%d-in_h" % m),
        ("bottom-right", "iw-%d-in_w" % m, "ih-%d-in_h" % m),
    ]

    hexes, ranges = [], []
    print("  corner          average    local range")
    for name, x, y in corners:
        h, r = patch_stats(sample_patch(src, x, y, n))
        hexes.append(h)
        ranges.append(r)
        print("  %-14s %s   %3d" % (name, h, r))

    rgb = [tuple(int(h[2 + i * 2:4 + i * 2], 16) for i in range(3)) for h in hexes]
    # corner-to-corner drift catches gradients and vignettes
    drift = max(max(c[i] for c in rgb) - min(c[i] for c in rgb) for i in range(3))
    # per-pixel range inside a patch catches grain, noise, and paper texture
    texture = max(ranges)

    print("\n  corner drift    %3d / 255   (gradient or vignette)" % drift)
    print("  local texture   %3d / 255   (grain, noise, paper)" % texture)

    if drift <= 6 and texture <= 10:
        print("\n  FLAT. skip `plate` and key it directly:")
        print("    --key-hex %s" % hexes[0])
    elif drift <= 20 and texture <= 30:
        print("\n  SLIGHTLY UNEVEN. try:")
        print("    --key-hex %s --similarity 0.20" % hexes[0])
        print("  if that leaves patches behind, run `plate` instead.")
    else:
        why = []
        if drift > 20:
            why.append("a gradient or vignette (drift %d)" % drift)
        if texture > 30:
            why.append("grain or texture (local range %d)" % texture)
        print("\n  NOT FLAT -- %s." % " and ".join(why))
        print("  chromakey will leave patches. run `plate` to cut the subject")
        print("  out and rebuild the background clean.")


def image_alpha_bbox(path: Path) -> "tuple | None":
    """Bounding box of an image's opaque pixels, or None if it has no alpha."""
    proc = run([
        need("ffmpeg"), "-hide_banner", "-nostats", "-i", str(path),
        "-vf", "format=rgba,alphaextract,bbox=min_val=16", "-f", "null", "-",
    ], check=False)
    m = BBOX.search(proc.stderr or "")
    if not m:
        return None
    x1, x2, y1, y2 = (int(g) for g in m.groups())
    return x2 - x1 + 1, y2 - y1 + 1, x1, y1


# ---------------------------------------------------------------------------
# plate


def cmd_plate(a: argparse.Namespace) -> None:
    src = Path(a.source)
    if not src.is_file():
        die("no such file: %s" % src)
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)

    cut = src
    tmp = None
    if not a.keep_alpha:
        if not shutil.which("rembg"):
            die('rembg is not on your PATH.\n  pip install "rembg[cli]"\n'
                "  (or pass --keep-alpha if your source image already has transparency)")
        tmp = out.with_name(out.stem + "-cut.png")
        step("cutting out the subject (first run downloads a model, be patient)")
        run(["rembg", "i", str(src), str(tmp)])
        cut = tmp

    # rembg keeps the original canvas and fills the margin with transparency,
    # so trim to the subject first -- otherwise --fill scales the padding too.
    box = image_alpha_bbox(cut)
    trim = "crop=%d:%d:%d:%d," % box if box else ""
    if box:
        step("subject measures %dx%d" % (box[0], box[1]))

    size = a.size
    fit = int(size * a.fill)
    step("compositing onto flat %s at %dx%d" % (a.color, size, size))
    run([
        need("ffmpeg"), "-hide_banner", "-y",
        "-f", "lavfi", "-i", "color=c=%s:s=%dx%d" % (COLORS[a.color]["hex"], size, size),
        "-i", str(cut),
        "-filter_complex",
        "[1:v]format=rgba,{t}scale=w='if(gt(a,1),{f},-1)':h='if(gt(a,1),-1,{f})'"
        ":flags=lanczos[c];"
        "[0:v][c]overlay=(W-w)/2:(H-h)/2".format(t=trim, f=fit),
        "-frames:v", "1", str(out),
    ])

    if tmp and not a.keep_cutout:
        tmp.unlink(missing_ok=True)

    print("\nplate written: %s" % out)
    print("upload this to Seedance. see README.md for the prompt.")


# ---------------------------------------------------------------------------
# probe


def cmd_probe(a: argparse.Namespace) -> None:
    info = probe_video(Path(a.video))
    print("resolution  %dx%d" % (info["width"], info["height"]))
    print("fps         %.3f" % info["fps"])
    print("frames      %d" % info["frames"])
    print("duration    %.3f s" % info["duration"])
    if info["frames"] and info["frames"] < 72:
        print("\nnote: only %d source frames. 72 sprite frames will repeat poses."
              % info["frames"])


# ---------------------------------------------------------------------------
# scrub


def cmd_scrub(a: argparse.Namespace) -> None:
    vid = Path(a.video)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    for old in out.glob("t_*.png"):
        old.unlink()

    step("dumping stills at %g fps" % a.rate)
    run([
        need("ffmpeg"), "-hide_banner", "-y", "-i", str(vid),
        "-vf", "fps=%s" % a.rate, "-fps_mode", "passthrough",
        str(out / "t_%04d.png"),
    ])

    n = len(list(out.glob("t_*.png")))
    print("\n%d stills in %s" % (n, out))
    print("timestamp of t_NNNN.png  =  (NNNN - 1) / %g seconds" % a.rate)
    print("\nfind where the gaze passes 12 o'clock going in and coming out,")
    print("then pass those two numbers to `build --start / --end`.")


# ---------------------------------------------------------------------------
# build


def alpha_bbox(vid: Path, a: argparse.Namespace, src: dict) -> tuple:
    """Union of the keyed subject's bounding box across every frame in range.

    This is why the crop is safe: it covers the frames where the head is turned
    hardest left and hardest right, not just the resting pose.
    """
    proc = run([
        need("ffmpeg"), "-hide_banner", "-nostats",
    ] + trim_args(a.start, a.end) + [
        "-i", str(vid),
        "-vf", "%s,alphaextract,bbox=min_val=%d" % (
            join_filters(
                interp_chain(a),
                key_chain(a.color, a.similarity, a.blend, False, a.key_hex),
            ),
            a.min_alpha),
        "-f", "null", "-",
    ])

    hits = BBOX.findall(proc.stderr or "")
    if not hits:
        die("the key matched nothing. the background may not be flat, or "
            "--similarity (%s) is too tight. try --similarity 0.20." % a.similarity)

    x1 = min(int(h[0]) for h in hits)
    x2 = max(int(h[1]) for h in hits)
    y1 = min(int(h[2]) for h in hits)
    y2 = max(int(h[3]) for h in hits)

    covered = ((x2 - x1 + 1) * (y2 - y1 + 1)) / float(src["width"] * src["height"])
    if covered > 0.95 and not a.allow_full_frame:
        die("the key matched almost nothing -- the subject measures %.0f%% of the "
            "frame.\n  that usually means --color (%s) is not the background "
            "colour.\n  check the plate, or pass --allow-full-frame to proceed anyway."
            % (covered * 100, a.color))

    x1 = max(0, x1 - a.pad)
    y1 = max(0, y1 - a.pad)
    x2 = min(src["width"] - 1, x2 + a.pad)
    y2 = min(src["height"] - 1, y2 + a.pad)

    w = (x2 - x1 + 1) & ~1
    h = (y2 - y1 + 1) & ~1
    return w, h, x1, y1, len(hits)


def angle_track(vid: Path, a: argparse.Namespace, crop: tuple) -> list:
    """Per-frame gaze angle, in degrees clockwise from 12 o'clock.

    Tracks the centroid of the head's silhouette. Yaw swings it much further
    than pitch does, so the path is an ellipse rather than a circle -- each
    axis is normalised by its own range before the angle is taken.
    """
    cw, ch, cx, cy = crop
    bh = max(8, int(ch * a.head_frac))
    tw = 96
    th = max(16, round(tw * bh / cw))

    chain = key_chain(a.color, a.similarity, a.blend, False, a.key_hex)
    raw = run_bytes([
        need("ffmpeg"), "-hide_banner", "-v", "error",
    ] + trim_args(a.start, a.end) + [
        "-i", str(vid),
        "-vf", "%s,crop=%d:%d:%d:%d,alphaextract,format=gray,scale=%d:%d"
               % (join_filters(interp_chain(a), chain), cw, bh, cx, cy, tw, th),
        "-fps_mode", "passthrough", "-f", "rawvideo", "-pix_fmt", "gray", "-",
    ])

    fs = tw * th
    n = len(raw) // fs
    if n < 2:
        die("angle tracking decoded %d frames" % n)

    pts = []
    for f in range(n):
        off = f * fs
        sx = sy = c = 0
        for i in range(fs):
            if raw[off + i] > 128:
                sx += i % tw
                sy += i // tw
                c += 1
        pts.append((sx / c, sy / c) if c else pts[-1] if pts else (tw / 2, th / 2))

    xs = [q[0] for q in pts]
    ys = [q[1] for q in pts]
    rx = (max(xs) - min(xs)) / 2.0
    ry = (max(ys) - min(ys)) / 2.0
    cxm = (max(xs) + min(xs)) / 2.0
    cym = (max(ys) + min(ys)) / 2.0
    if rx < 0.5:
        die("the head barely moves horizontally -- nothing to track.")
    if ry / rx < 0.12:
        die("the head moves %.0fx more horizontally than vertically (%.2f vs "
            "%.2f px).\n  that is a left-right sweep, not a rotation, so there "
            "is no angle to map.\n  regenerate, or drop --angle-uniform and set "
            "--start/--end by hand." % (rx / max(ry, 1e-6), rx, ry))

    ang = []
    for f in range(n):
        u = (xs[f] - cxm) / rx
        v = (ys[f] - cym) / ry
        ang.append(math.degrees(math.atan2(u, -v)) % 360.0)

    un = [ang[0]]
    for f in range(1, n):
        d = ang[f] - ang[f - 1]
        while d > 180:
            d -= 360
        while d < -180:
            d += 360
        un.append(un[-1] + d)
    return un


def find_rotation(un: list, tol: float) -> tuple:
    """Longest run that advances one way, and the sub-span covering 360 deg."""
    seq = un if un[-1] >= un[0] else [-v for v in un]

    best = (0, 0)
    s = 0
    peak = seq[0]
    for i in range(1, len(seq)):
        if seq[i] < peak - tol:          # a real reversal, not jitter
            if i - 1 - s > best[1] - best[0]:
                best = (s, i - 1)
            s = i
            peak = seq[i]
        else:
            peak = max(peak, seq[i])
    if len(seq) - 1 - s > best[1] - best[0]:
        best = (s, len(seq) - 1)

    lo, hi = best
    if seq[hi] - seq[lo] < 358:
        die("the clip never completes a full rotation -- the longest continuous "
            "sweep is %.0f degrees.\n  regenerate with the timed-keyframe prompt, "
            "or drop --angle-uniform." % (seq[hi] - seq[lo]))

    # tightest window inside that run which still covers a full turn
    for i in range(lo, hi + 1):
        for j in range(i + 1, hi + 1):
            if seq[j] - seq[i] >= 360:
                return i, j, (un[-1] >= un[0])
    return lo, hi, (un[-1] >= un[0])


def pick_by_angle(un: list, lo: int, hi: int, n: int, rising: bool) -> list:
    """Frame nearest each of n evenly spaced angles across one full turn."""
    seq = un if rising else [-v for v in un]
    base = seq[lo]
    out = []
    for k in range(n):
        target = base + k * 360.0 / n
        j = min(range(lo, hi + 1), key=lambda f: abs(seq[f] - target))
        out.append(j)
    return out


def grid_for(n: int) -> tuple:
    cols = math.ceil(math.sqrt(n))
    return cols, math.ceil(n / cols)


def cmd_build(a: argparse.Namespace) -> None:
    vid = Path(a.video)
    if not vid.is_file():
        die("no such file: %s" % vid)
    out = Path(a.out)
    frames_dir = out / "frames"
    raw_dir = out / ".raw"
    for d in (frames_dir, raw_dir):
        d.mkdir(parents=True, exist_ok=True)
    for d in (frames_dir, raw_dir):
        for old in d.glob("*.png"):
            old.unlink()

    src = probe_video(vid)
    print("source: %dx%d @ %.2f fps, %.2f s" % (
        src["width"], src["height"], src["fps"], src["duration"]))

    # --- pass A: find the crop -------------------------------------------
    step("measuring the subject across every frame")
    cw, ch, cx, cy, seen = alpha_bbox(vid, a, src)
    print("     crop %dx%d at %d,%d (from %d frames)" % (cw, ch, cx, cy, seen))

    # --- pass A2: angle track ---------------------------------------------
    picks = None
    angles = None
    tracked_angles = None
    source_frames = None
    direction = "clockwise"
    if a.angle_uniform:
        step("tracking the gaze angle across every frame")
        un = angle_track(vid, a, (cw, ch, cx, cy))
        lo, hi, rising = find_rotation(un, a.angle_tol)
        direction = "clockwise" if rising else "counterclockwise"
        seq = un if rising else [-v for v in un]
        print("     full turn spans frames %d-%d of %d (%.0f deg)"
              % (lo + 1, hi + 1, len(un), seq[hi] - seq[lo]))
        # Per-half-second sweep rate. A near-zero window is a real dwell, so
        # report the range rather than a ratio that divides by it.
        rates = sorted(abs(seq[f + 12] - seq[f]) * 2
                       for f in range(lo, max(lo, hi - 12)))
        if rates:
            print("     pacing %.0f to %.0f deg/s (median %.0f) -- angle "
                  "selection cancels this"
                  % (rates[0], rates[-1], rates[len(rates) // 2]))
        picks = pick_by_angle(un, lo, hi, a.frames, rising)
        step_deg = 360.0 / a.frames
        base = seq[lo]
        tracked_angles = [round(un[j] % 360.0, 2) for j in picks]
        if rising:
            angles = [round((base + k * step_deg) % 360.0, 2)
                      for k in range(a.frames)]
        else:
            angles = [round((-(base + k * step_deg)) % 360.0, 2)
                      for k in range(a.frames)]

    calibration = parse_calibration(a.calibrate, a.frames)
    if calibration:
        step("calibrating manifest angles from %d visual anchors" % len(calibration))
        angles, direction, errors = calibrated_angles(a.frames, calibration)
        worst = max(errors) if errors else 0.0
        print("     direction %s, worst anchor error %.2f deg" % (direction, worst))

    # --- pass B: key, crop, scale, write every frame ----------------------
    scale = a.cell / max(cw, ch)
    sw, sh = max(1, round(cw * scale)), max(1, round(ch * scale))

    step("keying and writing frames at %dx%d" % (sw, sh))
    run([
        need("ffmpeg"), "-hide_banner", "-y",
    ] + trim_args(a.start, a.end) + [
        "-i", str(vid),
        "-vf", "%s,crop=%d:%d:%d:%d,scale=%d:%d:flags=lanczos" % (
            join_filters(
                interp_chain(a),
                key_chain(a.color, a.similarity, a.blend, not a.no_despill, a.key_hex),
            ),
            cw, ch, cx, cy, sw, sh),
        "-fps_mode", "passthrough",
        str(raw_dir / "%05d.png"),
    ])

    raw = sorted(raw_dir.glob("*.png"))
    if not raw:
        die("no frames decoded from the selected range")
    if len(raw) < a.frames:
        die("only %d frames in the selected range, need %d. widen --start/--end, "
            "or lower --frames." % (len(raw), a.frames))

    if picks is not None:
        # One cell per equal slice of angle. Source pacing stops mattering:
        # a dwell collapses to a single cell instead of eating a dozen.
        if max(picks) >= len(raw):
            die("angle track and frame write disagree (%d vs %d frames)"
                % (max(picks) + 1, len(raw)))
        step("selecting %d frames by angle, one every %.1f degrees"
             % (a.frames, 360.0 / a.frames))
        dup = a.frames - len(set(picks))
        if dup:
            print("     note: %d cells reuse a neighbouring frame (the source "
                  "moves fast there)" % dup)
        source_frames = [j + 1 for j in picks]
        for i, j in enumerate(picks):
            shutil.copyfile(raw[j], frames_dir / ("f_%03d.png" % (i + 1)))
    else:
        # The sequence is a closed loop, so sampling [0, total) rather than
        # [0, total-1] avoids duplicating the 12 o'clock pose at both ends.
        step("selecting %d of %d frames by time" % (a.frames, len(raw)))
        source_frames = []
        for i in range(a.frames):
            j = round(i * len(raw) / a.frames)
            source_frames.append(j + 1)
            shutil.copyfile(raw[j], frames_dir / ("f_%03d.png" % (i + 1)))

    if angles is None:
        step_deg = 360.0 / a.frames
        angles = [round(k * step_deg, 2) for k in range(a.frames)]

    # --- pass C: tile ------------------------------------------------------
    cols, rows = grid_for(a.frames)
    sheet_w, sheet_h = cols * sw, rows * sh
    step("tiling %dx%d -> %dx%d sheet" % (cols, rows, sheet_w, sheet_h))
    if max(sheet_w, sheet_h) > a.max_dim:
        die("sheet would be %dx%d, over the %dpx texture limit.\n"
            "  lower --cell (currently %d) or --frames (currently %d)."
            % (sheet_w, sheet_h, a.max_dim, a.cell, a.frames))

    sheet_png = out / "sheet.png"
    run([
        need("ffmpeg"), "-hide_banner", "-y",
        "-start_number", "1", "-i", str(frames_dir / "f_%03d.png"),
        "-filter_complex", "tile=%dx%d:color=black@0.0" % (cols, rows),
        "-frames:v", "1", "-pix_fmt", "rgba", str(sheet_png),
    ])

    # --- webp, best effort -------------------------------------------------
    # Plenty of ffmpeg builds ship without libwebp, so this never blocks the
    # run. sheet.png is the real deliverable; webp is just smaller.
    sheet_webp = out / "sheet.webp"
    webp_ok = run([
        need("ffmpeg"), "-hide_banner", "-y", "-i", str(sheet_png),
        "-c:v", "libwebp", "-lossless", "1", "-q:v", "100",
        "-frames:v", "1", str(sheet_webp),
    ], check=False).returncode == 0

    if not webp_ok and shutil.which("cwebp"):
        step("ffmpeg has no libwebp; falling back to cwebp")
        webp_ok = run([shutil.which("cwebp"), "-lossless", "-quiet",
                       str(sheet_png), "-o", str(sheet_webp)],
                      check=False).returncode == 0

    if not webp_ok:
        sheet_webp.unlink(missing_ok=True)
        print("     note: no webp encoder available, so sheet.png is the output.")
        print("           optional: brew install webp   /   winget install Google.WebP")

    # --- manifest ----------------------------------------------------------
    manifest = {
        "source": vid.name,
        "sheet": sheet_webp.name if webp_ok else sheet_png.name,
        "frames": a.frames,
        "cols": cols,
        "rows": rows,
        "cell": {"w": sw, "h": sh},
        "sheet_size": {"w": sheet_w, "h": sheet_h},
        "degrees_per_frame": round(360.0 / a.frames, 4),
        "direction": direction,
        "selection": "angle" if picks is not None else "time",
        "angles": angles,
        "tracked_angles": tracked_angles,
        "source_frames": source_frames,
        "calibration": [{"frame": idx + 1, "angle": angle, "label": label}
                        for idx, angle, label in calibration],
        "interp_fps": float(a.interp_fps or 0.0),
        "order": "runtime selects the nearest manifest angle for the cursor "
                 "direction; generated from a %s source rotation" % direction,
        "key": {"color": a.key_hex or COLORS[a.color]["hex"],
                "similarity": a.similarity, "blend": a.blend},
        "crop": {"w": cw, "h": ch, "x": cx, "y": cy},
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")

    if not a.keep_raw:
        shutil.rmtree(raw_dir, ignore_errors=True)

    print("\ndone. %s" % out)
    print("  sheet.png      %dx%d" % (sheet_w, sheet_h))
    if webp_ok:
        print("  sheet.webp     lossless, alpha")
    print("  frames/        %d stills" % a.frames)
    print("  manifest.json  grid + cell size for the overlay")
    print("\ncheck the seam: frames/f_001.png and f_%03d.png are adjacent angles"
          % a.frames)
    print("and should look nearly identical.")


# ---------------------------------------------------------------------------
# verify


CARDINALS = [
    ("up", 0.0),
    ("upper-right", 45.0),
    ("right", 90.0),
    ("lower-right", 135.0),
    ("down", 180.0),
    ("lower-left", 225.0),
    ("left", 270.0),
    ("upper-left", 315.0),
]


def nearest_frame(angles: list, deg: float) -> tuple:
    best = min(range(len(angles)),
               key=lambda i: abs(shortest_angle(float(angles[i]), deg)))
    return best, abs(shortest_angle(float(angles[best]), deg))


def gap_stats(angles: list) -> tuple:
    gaps = [abs(shortest_angle(float(angles[i]), float(angles[(i + 1) % len(angles)])))
            for i in range(len(angles))]
    gaps_sorted = sorted(gaps)
    return min(gaps), gaps_sorted[len(gaps_sorted) // 2], max(gaps)


def write_contact(frames_dir: Path, cols: int, rows: int, out: Path, width: int) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    run([
        need("ffmpeg"), "-hide_banner", "-y", "-framerate", "8",
        "-i", str(frames_dir / "f_%03d.png"),
        "-vf", "scale=%d:-1,tile=%dx%d" % (width, cols, rows),
        "-frames:v", "1", str(out),
    ], check=False)


def write_cardinals(frames_dir: Path, manifest: dict, out: Path, width: int) -> None:
    angles = manifest.get("angles") or []
    if len(angles) != manifest.get("frames"):
        return
    out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="hero-cardinals.") as tmp_name:
        tmp = Path(tmp_name)
        for i, (_name, deg) in enumerate(CARDINALS, 1):
            idx, _dist = nearest_frame(angles, deg)
            shutil.copyfile(frames_dir / ("f_%03d.png" % (idx + 1)),
                            tmp / ("f_%03d.png" % i))
        run([
            need("ffmpeg"), "-hide_banner", "-y", "-framerate", "8",
            "-i", str(tmp / "f_%03d.png"),
            "-vf", "scale=%d:-1,tile=8x1" % width,
            "-frames:v", "1", str(out),
        ], check=False)


def cmd_verify(a: argparse.Namespace) -> None:
    root = Path(a.sprite)
    manifest_path = root / "manifest.json"
    frames_dir = root / "frames"
    if not manifest_path.is_file():
        die("no manifest.json in %s" % root)
    if not frames_dir.is_dir():
        die("no frames/ directory in %s" % root)

    manifest = json.loads(manifest_path.read_text())
    frames = int(manifest.get("frames") or 0)
    angles = manifest.get("angles") or []
    print("sprite      %s" % root)
    print("sheet       %s" % manifest.get("sheet", "-"))
    print("frames      %d" % frames)
    print("selection   %s" % manifest.get("selection", "-"))
    print("direction   %s" % manifest.get("direction", "-"))
    print("interp_fps  %s" % manifest.get("interp_fps", 0))

    source_frames = manifest.get("source_frames") or []
    if source_frames:
        dup = len(source_frames) - len(set(source_frames))
        print("source      %d unique / %d cells (%d duplicates)"
              % (len(set(source_frames)), len(source_frames), dup))

    tracked = manifest.get("tracked_angles") or []
    if len(tracked) == frames:
        lo, mid, hi = gap_stats(tracked)
        print("tracked gap %.2f min / %.2f median / %.2f max deg"
              % (lo, mid, hi))

    if len(angles) == frames:
        lo, mid, hi = gap_stats(angles)
        print("manifest gap %.2f min / %.2f median / %.2f max deg"
              % (lo, mid, hi))
        print("\ncardinal mapping")
        for name, deg in CARDINALS:
            idx, dist = nearest_frame(angles, deg)
            print("  %-12s frame %3d   angle %7.2f   error %.2f"
                  % (name, idx + 1, float(angles[idx]), dist))
    else:
        print("manifest has no complete angles[] array")

    cols = int(manifest.get("cols") or math.ceil(math.sqrt(frames)))
    rows = int(manifest.get("rows") or math.ceil(frames / max(cols, 1)))
    contact = Path(a.contact_out) if a.contact_out else root / "verify-frames.jpg"
    cardinals = Path(a.cardinals_out) if a.cardinals_out else root / "verify-cardinals.jpg"
    write_contact(frames_dir, cols, rows, contact, a.thumb)
    write_cardinals(frames_dir, manifest, cardinals, a.thumb)
    print("\nwrote      %s" % contact)
    print("wrote      %s" % cardinals)


# ---------------------------------------------------------------------------
# cli


def main() -> None:
    p = argparse.ArgumentParser(
        prog="hero-asset",
        description="Seedance look-around video -> scrubbable sprite sheet.")
    sub = p.add_subparsers(dest="cmd", required=True)

    # plate
    sp = sub.add_parser("plate", help="build a flat-chroma plate from an image")
    sp.add_argument("source")
    sp.add_argument("--out", default="assets/plate.png")
    sp.add_argument("--color", choices=sorted(COLORS), default="green")
    sp.add_argument("--size", type=int, default=1024, help="square canvas, px")
    sp.add_argument("--fill", type=float, default=0.72,
                    help="fraction of the canvas the subject fills (0-1)")
    sp.add_argument("--keep-alpha", action="store_true",
                    help="source already has transparency; skip rembg")
    sp.add_argument("--keep-cutout", action="store_true")
    sp.set_defaults(func=cmd_plate)

    # bg
    sp = sub.add_parser("bg", help="report an image or video's background colour")
    sp.add_argument("source")
    sp.add_argument("--margin", type=int, default=8, help="inset from each corner, px")
    sp.add_argument("--size", type=int, default=48, help="sample square edge, px")
    sp.set_defaults(func=cmd_bg)

    # probe
    sp = sub.add_parser("probe", help="report the generated video's properties")
    sp.add_argument("video")
    sp.set_defaults(func=cmd_probe)

    # scrub
    sp = sub.add_parser("scrub", help="dump timestamped stills to pick the loop")
    sp.add_argument("video")
    sp.add_argument("--out", default="assets/scrub")
    sp.add_argument("--rate", type=float, default=8.0, help="stills per second")
    sp.set_defaults(func=cmd_scrub)

    # build
    sp = sub.add_parser("build", help="key, normalize, and pack the sprite sheet")
    sp.add_argument("video")
    sp.add_argument("--out", default="assets/hero")
    sp.add_argument("--start", type=float, help="loop in, seconds")
    sp.add_argument("--end", type=float, help="loop out, seconds")
    sp.add_argument("--frames", type=int, default=72,
                    help="sprite frames; 72 = 5 degrees each")
    sp.add_argument("--cell", type=int, default=400, help="max cell edge, px")
    sp.add_argument("--color", choices=sorted(COLORS), default="green",
                    help="which despill to apply; overridden for keying by --key-hex")
    sp.add_argument("--key-hex", metavar="0xRRGGBB",
                    help="key this exact colour instead of the --color default. "
                         "get it from the `bg` subcommand")
    sp.add_argument("--similarity", type=float, default=0.12,
                    help="raise if the key leaves speckles, lower if it eats the subject")
    sp.add_argument("--blend", type=float, default=0.06)
    sp.add_argument("--no-despill", action="store_true",
                    help="skip despill if it is washing out the subject")
    sp.add_argument("--pad", type=int, default=8, help="px of slack around the crop")
    sp.add_argument("--min-alpha", type=int, default=16,
                    help="alpha threshold for the crop measurement, 0-255")
    sp.add_argument("--max-dim", type=int, default=4096)
    sp.add_argument("--angle-uniform", action="store_true",
                    help="pick frames at equal ANGLES rather than equal times. "
                         "immune to the source dwelling at some directions")
    sp.add_argument("--head-frac", type=float, default=0.55,
                    help="top fraction of the subject treated as the head, for tracking")
    sp.add_argument("--angle-tol", type=float, default=8.0,
                    help="degrees of backtrack tolerated before it counts as a reversal")
    sp.add_argument("--interp-fps", type=float, default=0.0,
                    help="motion-interpolate the generated video before tracking and sampling")
    sp.add_argument("--calibrate", action="append",
                    help="visual angle anchors, e.g. down=1,left=19,up=37,right=55. "
                         "May be repeated; names may be up/right/down/left and diagonals")
    sp.add_argument("--allow-full-frame", action="store_true",
                    help="skip the sanity check that the key actually removed a background")
    sp.add_argument("--keep-raw", action="store_true")
    sp.set_defaults(func=cmd_build)

    # verify
    sp = sub.add_parser("verify", help="diagnose a built sprite folder")
    sp.add_argument("sprite")
    sp.add_argument("--contact-out", help="write the full-frame contact sheet here")
    sp.add_argument("--cardinals-out", help="write the cardinal-pose sheet here")
    sp.add_argument("--thumb", type=int, default=140, help="contact sheet cell width")
    sp.set_defaults(func=cmd_verify)

    a = p.parse_args()
    if getattr(a, "key_hex", None) and not HEX_RE.match(a.key_hex):
        die("--key-hex must look like 0xRRGGBB, got %r" % a.key_hex)
    a.func(a)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(130)

#!/usr/bin/env python3
"""Generate the camera grade LUT for the `Cam` input.

A "Sam Kolder look" is a split tone -- teal shadows, amber highlights -- over a
faded film curve: the black point lifted off zero, the highlights rolled short
of clipping, greens rotated toward cyan and desaturated so foliage never reads
lime. None of that is reachable with OBS's Color Correction filter, which is
global: it has one saturation and one hue shift, and a split tone needs shadows
and highlights moved in *opposite* directions. That takes a lookup table.

Output is a `LUT_3D_SIZE 32` `.cube`, which is what OBS 32's "Apply LUT" filter
(`clut_filter`) reads -- verified against its own shipped `grayscale.cube`,
which is exactly that format. `.cube` is plain text, so this needs no Pillow and
no pip install, the same constraint `obs-setup.py` keeps. The PNG LUT form OBS
also accepts is a 512x512 8x8 tile grid of a 64-cube; it would need an encoder
here and buys nothing.

Strength is deliberately baked at 1.0 and dialled *live* instead: the filter's
own `clut_amount` slider blends against the ungraded image, so the look is
adjustable in OBS without regenerating anything. `--strength` exists for baking
a permanently softer table.

What a LUT physically cannot do, and what the look is also made of: vignette,
halation, grain, and bloom are all spatial -- they need neighbouring pixels, and
a per-pixel table has none. Those want an overlay image or a shader plugin.
"""

import argparse
import colorsys
import pathlib
import sys

CUBE_SIZE = 32

# Three points on one axis, not three different grades. `strong` is what the
# look actually is on footage with real shadows in it; `soft` is for a bright
# flat room where there is little shadow for the teal to occupy and pushing
# harder only blows the wall out further. The filter's Amount slider blends
# between any of these and the raw image, so pick the nearest and dial down.
LOOKS = {
    #                 lift   ceil  contr  pivot  teal x   amber x
    "soft":     dict(lift=0.030, ceil=0.980, contrast=1.18, pivot=1.000,
                     tint=0.70, sat=1.04),
    "standard": dict(lift=0.042, ceil=0.965, contrast=1.30, pivot=0.995,
                     tint=1.00, sat=1.07),
    "strong":   dict(lift=0.058, ceil=0.930, contrast=1.48, pivot=0.985,
                     tint=1.55, sat=1.12),
}

# --- tone curve ---------------------------------------------------------
# LIFT is the whole "faded" half of the look: the black point never reaches 0,
# so shadows read as washed film rather than crushed digital. It is also the
# reason this filter must sit ABOVE `CAM OFF` in the chain -- that kill switch
# multiplies by zero to get opaque black, and a table that maps 0 to 0.042
# would hand it back a dim teal rectangle instead.
#
# CEIL matters more than it looks on a webcam pointed at a white wall: rolling
# the top down is what stops a blown highlight reading as digital clipping.

# --- split tone ---------------------------------------------------------
# Signed RGB offsets, applied weighted by luma. Shadows cool, highlights warm.
# Green must carry roughly half of blue's weight or the shadows read navy
# rather than teal -- measured on a dark office chair, which went denim blue
# at (-0.022, 0.014, 0.054) and cyan-slate once green came up.
SHADOW_TINT = (-0.024, 0.030, 0.052)    # teal
HIGH_TINT = (0.040, 0.011, -0.032)      # amber
SHADOW_FALLOFF = 2.0                    # higher = tint confined to deeper shadows
HIGH_FALLOFF = 2.2

# --- hue work -----------------------------------------------------------
GREEN_LO, GREEN_HI = 68.0, 168.0        # degrees; the band rotated toward cyan
GREEN_PUSH = 17.0                       # degrees toward cyan
GREEN_DESAT = 0.70
SKIN_LO, SKIN_HI = 11.0, 46.0           # protected from the saturation lift
SKIN_SATURATION = 1.0

L = LOOKS["standard"]                   # replaced by --look in main()


def sigmoid_contrast(x: float, a: float) -> float:
    """S-curve that is exactly the identity at a == 1 and fixes 0, 0.5 and 1."""
    if a == 1.0 or x <= 0.0 or x >= 1.0:
        return x
    xa = x ** a
    return xa / (xa + (1.0 - x) ** a)


def tone(x: float) -> float:
    y = sigmoid_contrast(x, L["contrast"])
    if L["pivot"] != 1.0:
        y = y ** L["pivot"]
    return L["lift"] + y * (L["ceil"] - L["lift"])


def in_band(deg: float, lo: float, hi: float) -> float:
    """1.0 in the middle of the band, easing to 0 at its edges."""
    if not (lo <= deg <= hi):
        return 0.0
    half = (hi - lo) / 2.0
    t = 1.0 - abs(deg - (lo + half)) / half
    return t * t * (3.0 - 2.0 * t)          # smoothstep


def grade(r: float, g: float, b: float) -> tuple:
    r, g, b = tone(r), tone(g), tone(b)

    # Hue work in HSV. Greens rotate toward cyan and lose saturation; skin is
    # held at unity so the warm midtones do not go orange and plastic.
    h, s, v = colorsys.rgb_to_hsv(r, g, b)
    deg = h * 360.0
    if s > 0.004:
        w = in_band(deg, GREEN_LO, GREEN_HI)
        if w:
            deg += GREEN_PUSH * w
            s *= 1.0 + (GREEN_DESAT - 1.0) * w
        skin = in_band(deg, SKIN_LO, SKIN_HI)
        sat = SKIN_SATURATION * skin + L["sat"] * (1.0 - skin)
        # Roll the lift off as saturation rises so nothing turns neon.
        s = min(1.0, s * (1.0 + (sat - 1.0) * (1.0 - s * s)))
        r, g, b = colorsys.hsv_to_rgb((deg % 360.0) / 360.0, s, v)

    # Split tone, weighted by luma so the two tints do not cancel in the mids.
    lum = 0.2126 * r + 0.7152 * g + 0.0722 * b
    ws = (1.0 - lum) ** SHADOW_FALLOFF
    wh = lum ** HIGH_FALLOFF
    t = L["tint"]
    r += (SHADOW_TINT[0] * ws + HIGH_TINT[0] * wh) * t
    g += (SHADOW_TINT[1] * ws + HIGH_TINT[1] * wh) * t
    b += (SHADOW_TINT[2] * ws + HIGH_TINT[2] * wh) * t

    return (min(1.0, max(0.0, r)),
            min(1.0, max(0.0, g)),
            min(1.0, max(0.0, b)))


def build(size: int, strength: float) -> str:
    # .cube order is red fastest, then green, then blue.
    out = ["LUT_3D_SIZE %d" % size]
    d = size - 1
    for bi in range(size):
        for gi in range(size):
            for ri in range(size):
                r0, g0, b0 = ri / d, gi / d, bi / d
                r, g, b = grade(r0, g0, b0)
                if strength != 1.0:
                    r = r0 + (r - r0) * strength
                    g = g0 + (g - g0) * strength
                    b = b0 + (b - b0) * strength
                out.append("%.6g %.6g %.6g" % (r, g, b))
    return "\n".join(out) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("-o", "--out", default="assets/luts/kolder.cube",
                    help="output .cube path (default: %(default)s)")
    ap.add_argument("--look", choices=sorted(LOOKS), default="standard",
                    help="how hard to push it (default: %(default)s)")
    ap.add_argument("--size", type=int, default=CUBE_SIZE,
                    help="cube edge; 32 is what OBS ships (default: %(default)s)")
    ap.add_argument("--strength", type=float, default=1.0,
                    help="bake a softer table; prefer the filter's own Amount "
                         "slider, which does this live (default: %(default)s)")
    a = ap.parse_args()

    global L
    L = LOOKS[a.look]

    path = pathlib.Path(a.out)
    path.parent.mkdir(parents=True, exist_ok=True)
    text = build(a.size, a.strength)
    path.write_text(text, encoding="ascii")

    # Report the two values that decide whether the chain is still correct.
    black = grade(0.0, 0.0, 0.0)
    white = grade(1.0, 1.0, 1.0)
    print("wrote %s  (%s, %d entries, %.0f KB)"
          % (path, a.look, a.size ** 3, len(text) / 1024))
    print("  black 0,0,0 -> %.3f %.3f %.3f   <- lifted, so this filter must sit "
          "ABOVE CAM OFF" % black)
    print("  white 1,1,1 -> %.3f %.3f %.3f" % white)
    return 0


if __name__ == "__main__":
    sys.exit(main())

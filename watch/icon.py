#!/usr/bin/env python3
"""
icon.py -- the watch app's icon, drawn rather than stored.

    python3 watch/icon.py

Writes HeartRate/Assets.xcassets/AppIcon.appiconset/icon-1024.png: Fitness
Friday's yellow heart on its royal sheet, with the blueprint grid behind it
(overlays/fitness-friday/blueprint.css). Standard library only -- a PNG is
a few zlib-compressed scanlines, and 30 lines of them beats a dependency
or a committed blob nothing can regenerate.
"""

import struct
import zlib
from pathlib import Path

N = 1024
ROYAL, DEEP, INK = (0x1C, 0x41, 0xD4), (0x0F, 0x26, 0x90), (0xFF, 0xD6, 0x0A)
GRID = 64            # px between blueprint lines
HEART = 0.56         # of the face: a watch icon is cropped to a circle
AA = 3               # samples a side -- the heart is the only curved edge


def heart(x, y):
    """The classic (x^2+y^2-1)^3 <= x^2 y^3 heart, centred and upright."""
    return (x * x + y * y - 1) ** 3 <= x * x * y * y * y


def mix(a, b, t):
    return tuple(round(p + (q - p) * t) for p, q in zip(a, b))


def main() -> None:
    rows = []
    for py in range(N):
        row = bytearray()
        for px in range(N):
            # The sheet: royal at the top, deeper towards the bottom corners.
            dx, dy = (px - N / 2) / (N / 2), py / N
            c = mix(ROYAL, DEEP, min(1.0, (dy * 0.8 + abs(dx) * 0.35)))
            # The grid, a touch lighter than the sheet.
            if px % GRID == 0 or py % GRID == 0:
                c = mix(c, (0xF4, 0xF7, 0xFF), 0.10)
            # The heart. y is flipped, and lifted a little off centre so the
            # cleft and the point sit evenly inside the circular crop.
            # Supersampled, because a hard curve at 1024 reads as stairs
            # once watchOS scales it down to 44 px.
            hits = sum(
                heart((px + (i + 0.5) / AA - N / 2) / (N * HEART / 2),
                      (N / 2 - (py + (j + 0.5) / AA) + N * 0.035) / (N * HEART / 2))
                for i in range(AA) for j in range(AA))
            if hits:
                c = mix(c, INK, hits / (AA * AA))
            row += bytes(c)
        rows.append(bytes(row))

    raw = b"".join(b"\x00" + r for r in rows)

    def chunk(kind, data):
        return (struct.pack(">I", len(data)) + kind + data
                + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF))

    png = (b"\x89PNG\r\n\x1a\n"
           + chunk(b"IHDR", struct.pack(">IIBBBBB", N, N, 8, 2, 0, 0, 0))
           + chunk(b"IDAT", zlib.compress(raw, 9))
           + chunk(b"IEND", b""))

    out = Path(__file__).resolve().parent / "HeartRate/Assets.xcassets/AppIcon.appiconset/icon-1024.png"
    out.write_bytes(png)
    print("%s, %d x %d, %.0f KB" % (out.name, N, N, len(png) / 1024))


if __name__ == "__main__":
    main()

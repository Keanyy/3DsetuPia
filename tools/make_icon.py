#!/usr/bin/env python3
"""Draw the 3DsetuPia icon (a cube on a teal tile) and write src/ayarci/ayarci.ico.

Pure numpy + zlib, no image library needed. Usage: python tools/make_icon.py
"""
import os
import struct
import zlib

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "src", "ayarci", "ayarci.ico")
SIZES = (16, 24, 32, 48, 64, 128, 256)
TEAL = (0, 137, 123)
FACES = [  # (polygon in unit coordinates, colour)
    ([(0.5, 0.18), (0.80, 0.35), (0.5, 0.52), (0.20, 0.35)], (255, 255, 255)),
    ([(0.20, 0.35), (0.5, 0.52), (0.5, 0.86), (0.20, 0.69)], (204, 236, 232)),
    ([(0.5, 0.52), (0.80, 0.35), (0.80, 0.69), (0.5, 0.86)], (140, 205, 196)),
]


def _inside(px, py, poly):
    inside = np.zeros(px.shape, bool)
    n = len(poly)
    for i in range(n):
        x1, y1 = poly[i]
        x2, y2 = poly[(i + 1) % n]
        cond = ((y1 > py) != (y2 > py)) & (px < (x2 - x1) * (py - y1) / ((y2 - y1) or 1e-12) + x1)
        inside ^= cond
    return inside


def render(size, ss=4):
    n = size * ss
    c = (np.arange(n) + 0.5) / n
    px, py = np.meshgrid(c, c)
    rgba = np.zeros((n, n, 4), float)
    r = 0.2                                      # rounded tile
    dx = np.maximum(np.abs(px - 0.5) - (0.5 - r), 0)
    dy = np.maximum(np.abs(py - 0.5) - (0.5 - r), 0)
    tile = dx * dx + dy * dy <= r * r
    rgba[tile, :3] = TEAL
    rgba[tile, 3] = 255
    for poly, colour in FACES:
        m = _inside(px, py, poly) & tile
        rgba[m, :3] = colour
    # down-sample (box filter) for smooth edges
    rgba = rgba.reshape(size, ss, size, ss, 4).mean(axis=(1, 3))
    return np.clip(rgba + 0.5, 0, 255).astype(np.uint8)


def png(img):
    h, w, _ = img.shape
    raw = b"".join(b"\x00" + img[y].tobytes() for y in range(h))

    def chunk(tag, data):
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0)) +
            chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b""))


def main():
    images = [png(render(s)) for s in SIZES]
    header = struct.pack("<HHH", 0, 1, len(images))
    offset = 6 + 16 * len(images)
    entries, blobs = b"", b""
    for s, data in zip(SIZES, images):
        entries += struct.pack("<BBBBHHII", s % 256, s % 256, 0, 0, 1, 32, len(data), offset + len(blobs))
        blobs += data
    with open(OUT, "wb") as fh:
        fh.write(header + entries + blobs)
    with open(os.path.join(ROOT, "docs", "img", "icon.png"), "wb") as fh:
        fh.write(images[-1])
    print("wrote", OUT)


if __name__ == "__main__":
    main()

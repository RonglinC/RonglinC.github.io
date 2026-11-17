#!/usr/bin/env python3
"""Write Qingqing mascot PNG icons for the news PWA (no Pillow required)."""

from __future__ import annotations

import math
import struct
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "news" / "icons"


def png(path: Path, size: int, rgba: bytes) -> None:
    def chunk(tag: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data))
            + tag
            + data
            + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        )

    raw = bytearray()
    stride = size * 4
    for y in range(size):
        raw.append(0)
        raw.extend(rgba[y * stride : (y + 1) * stride])
    path.write_bytes(
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(bytes(raw), 9))
        + chunk(b"IEND", b"")
    )


def mix(a: tuple[int, int, int], b: tuple[int, int, int], t: float) -> tuple[int, int, int]:
    return (
        int(a[0] + (b[0] - a[0]) * t),
        int(a[1] + (b[1] - a[1]) * t),
        int(a[2] + (b[2] - a[2]) * t),
    )


def ellipse(nx: float, ny: float, cx: float, cy: float, rx: float, ry: float) -> float:
    return ((nx - cx) ** 2) / (rx * rx) + ((ny - cy) ** 2) / (ry * ry)


def pixel(x: int, y: int, size: int) -> tuple[int, int, int, int]:
    nx = (x + 0.5) / size * 2 - 1
    ny = (y + 0.5) / size * 2 - 1

    # Circular sticker backdrop
    sticker = math.hypot(nx, ny)
    if sticker > 0.98:
        return (0, 0, 0, 0)
    cream = mix((255, 246, 234), (232, 244, 236), (ny + 1) / 2)
    if sticker > 0.92:
        return (*mix(cream, (126, 191, 179), 0.55), 255)

    col = cream
    # Sprout leaves
    if ellipse(nx, ny, -0.22, -0.72, 0.16, 0.09) <= 1 and nx < 0.05:
        col = (127, 196, 176)
    if ellipse(nx, ny, 0.24, -0.72, 0.16, 0.09) <= 1 and nx > -0.05:
        col = (94, 168, 152)
    if abs(nx) < 0.03 and -0.72 < ny < -0.42:
        col = (95, 143, 134)

    # Body
    if ellipse(nx, ny, 0, 0.08, 0.62, 0.66) <= 1:
        t = max(0.0, 1 - math.hypot(nx + 0.18, ny + 0.2) / 0.9)
        col = mix((110, 168, 158), (214, 242, 233), t)
    # Belly
    if ellipse(nx, ny, 0, 0.28, 0.36, 0.3) <= 1:
        col = (255, 247, 238)
    # Blush
    if ellipse(nx, ny, -0.38, 0.16, 0.11, 0.07) <= 1 or ellipse(nx, ny, 0.38, 0.16, 0.11, 0.07) <= 1:
        col = mix(col, (244, 179, 184), 0.7)
    # Eyes
    if ellipse(nx, ny, -0.18, 0.0, 0.09, 0.12) <= 1 or ellipse(nx, ny, 0.18, 0.0, 0.09, 0.12) <= 1:
        col = (44, 44, 44)
    if ellipse(nx, ny, -0.15, -0.04, 0.03, 0.03) <= 1 or ellipse(nx, ny, 0.21, -0.04, 0.03, 0.03) <= 1:
        col = (255, 255, 255)
    # Smile
    smile = math.hypot(nx, ny - 0.18)
    if 0.11 < smile < 0.16 and ny > 0.16 and abs(nx) < 0.14:
        col = (92, 74, 58)
    # Sparkle
    if math.hypot(nx - 0.52, ny + 0.28) < 0.055:
        col = (247, 226, 124)

    return (*col, 255)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for size, name in ((192, "icon-192.png"), (512, "icon-512.png"), (180, "apple-touch-icon.png")):
        buf = bytearray(size * size * 4)
        i = 0
        for y in range(size):
            for x in range(size):
                r, g, b, a = pixel(x, y, size)
                buf[i : i + 4] = bytes((r, g, b, a))
                i += 4
        dest = OUT / name
        png(dest, size, bytes(buf))
        print(f"wrote {dest.relative_to(ROOT)}")


if __name__ == "__main__":
    main()

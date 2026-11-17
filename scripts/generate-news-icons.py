#!/usr/bin/env python3
"""Write Qingqing mascot PNG icons (no Pillow required)."""

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
    sticker = math.hypot(nx, ny)
    if sticker > 0.98:
        return (0, 0, 0, 0)
    cream = mix((255, 246, 238), (255, 228, 232), max(0.0, (ny + 1) / 2))
    if sticker > 0.9:
        return (*mix(cream, (59, 50, 44), 0.55), 255)

    col = cream
    if ellipse(nx, ny, -0.24, -0.7, 0.18, 0.1) <= 1:
        col = (158, 224, 200)
    if ellipse(nx, ny, 0.26, -0.7, 0.18, 0.1) <= 1:
        col = (125, 207, 182)
    if abs(nx) < 0.035 and -0.7 < ny < -0.38:
        col = (90, 168, 136)
    if ellipse(nx, ny, 0.0, 0.12, 0.66, 0.7) <= 1:
        t = max(0.0, 1 - math.hypot(nx + 0.2, ny + 0.15) / 0.95)
        col = mix((125, 207, 182), (255, 247, 251), t)
    if ellipse(nx, ny, 0.0, 0.32, 0.36, 0.28) <= 1:
        col = (255, 247, 240)
    if ellipse(nx, ny, -0.4, 0.18, 0.13, 0.08) <= 1 or ellipse(nx, ny, 0.4, 0.18, 0.13, 0.08) <= 1:
        col = (255, 179, 193)
    if ellipse(nx, ny, -0.2, 0.02, 0.12, 0.15) <= 1 or ellipse(nx, ny, 0.2, 0.02, 0.12, 0.15) <= 1:
        col = (43, 36, 32)
    if ellipse(nx, ny, -0.16, -0.03, 0.045, 0.045) <= 1 or ellipse(nx, ny, 0.24, -0.03, 0.045, 0.045) <= 1:
        col = (255, 255, 255)
    smile = math.hypot(nx / 0.9, ny - 0.22)
    if 0.12 < smile < 0.175 and ny > 0.2 and abs(nx) < 0.16:
        col = (90, 64, 56)
    if math.hypot(nx - 0.55, ny + 0.32) < 0.07:
        col = (255, 213, 107)
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

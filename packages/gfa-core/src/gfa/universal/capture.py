"""Screen capture and image encoding (Windows, stdlib only)."""

from __future__ import annotations

import base64
import ctypes
import struct
import zlib
from ctypes import wintypes
from dataclasses import dataclass

user32 = ctypes.windll.user32
gdi32 = ctypes.windll.gdi32

SRCCOPY = 0x00CC0020
CAPTUREBLT = 0x40000000
DIB_RGB_COLORS = 0
BI_RGB = 0


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [
        ("biSize", wintypes.DWORD),
        ("biWidth", ctypes.c_long),
        ("biHeight", ctypes.c_long),
        ("biPlanes", wintypes.WORD),
        ("biBitCount", wintypes.WORD),
        ("biCompression", wintypes.DWORD),
        ("biSizeImage", wintypes.DWORD),
        ("biXPelsPerMeter", ctypes.c_long),
        ("biYPelsPerMeter", ctypes.c_long),
        ("biClrUsed", wintypes.DWORD),
        ("biClrImportant", wintypes.DWORD),
    ]


@dataclass
class CapturedFrame:
    width: int
    height: int
    png_bytes: bytes
    raw_bgra: bytes | None = None

    def to_base64(self) -> str:
        return base64.b64encode(self.png_bytes).decode("ascii")

    def data_url(self) -> str:
        return f"data:image/png;base64,{self.to_base64()}"


def _capture_bgra(x: int, y: int, w: int, h: int) -> bytes:
    if w <= 0 or h <= 0:
        raise ValueError("invalid capture size")
    hdc_screen = user32.GetDC(0)
    hdc_mem = gdi32.CreateCompatibleDC(hdc_screen)
    hbmp = gdi32.CreateCompatibleBitmap(hdc_screen, w, h)
    gdi32.SelectObject(hdc_mem, hbmp)
    gdi32.BitBlt(hdc_mem, 0, 0, w, h, hdc_screen, x, y, SRCCOPY | CAPTUREBLT)

    bmi = BITMAPINFOHEADER()
    bmi.biSize = ctypes.sizeof(BITMAPINFOHEADER)
    bmi.biWidth = w
    bmi.biHeight = -h  # top-down
    bmi.biPlanes = 1
    bmi.biBitCount = 32
    bmi.biCompression = BI_RGB

    buf_size = w * h * 4
    buf = (ctypes.c_ubyte * buf_size)()
    gdi32.GetDIBits(hdc_mem, hbmp, 0, h, buf, ctypes.byref(bmi), DIB_RGB_COLORS)

    # cleanup
    gdi32.DeleteObject(hbmp)
    gdi32.DeleteDC(hdc_mem)
    user32.ReleaseDC(0, hdc_screen)
    return bytes(buf)


def _resize_bgra(src: bytes, sw: int, sh: int, dw: int, dh: int) -> bytes:
    if (sw, sh) == (dw, dh):
        return src
    out = bytearray(dw * dh * 4)
    for y in range(dh):
        sy = int(y * sh / dh)
        for x in range(dw):
            sx = int(x * sw / dw)
            si = (sy * sw + sx) * 4
            di = (y * dw + x) * 4
            out[di:di + 4] = src[si:si + 4]
    return bytes(out)


def _encode_png_rgb(width: int, height: int, bgra: bytes) -> bytes:
    # Convert BGRA -> RGB
    raw = bytearray()
    for y in range(height):
        raw.append(0)  # filter byte
        for x in range(width):
            i = (y * width + x) * 4
            b = bgra[i]
            g = bgra[i + 1]
            r = bgra[i + 2]
            raw += bytes((r, g, b))
    compressed = zlib.compress(bytes(raw), level=6)

    def chunk(typ: bytes, data: bytes) -> bytes:
        return (struct.pack(">I", len(data)) + typ + data +
                struct.pack(">I", zlib.crc32(typ + data) & 0xFFFFFFFF))

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    out = b"\x89PNG\r\n\x1a\n"
    out += chunk(b"IHDR", ihdr)
    out += chunk(b"IDAT", compressed)
    out += chunk(b"IEND", b"")
    return out


def capture_screen(x: int = 0, y: int = 0, width: int | None = None, height: int | None = None,
                   scale: float = 1.0) -> CapturedFrame:
    if width is None or height is None:
        width = user32.GetSystemMetrics(0)
        height = user32.GetSystemMetrics(1)
    bgra = _capture_bgra(x, y, width, height)
    if scale != 1.0 and 0 < scale < 1:
        nw = max(1, int(width * scale))
        nh = max(1, int(height * scale))
        bgra = _resize_bgra(bgra, width, height, nw, nh)
        width, height = nw, nh
    png = _encode_png_rgb(width, height, bgra)
    return CapturedFrame(width=width, height=height, png_bytes=png, raw_bgra=bgra)


def capture_window(hwnd: int, client_only: bool = True, scale: float = 1.0) -> CapturedFrame:
    from gfa.universal.windows import get_client_rect, get_window_rect
    if client_only:
        l, t, r, b = get_client_rect(hwnd)
    else:
        l, t, r, b = get_window_rect(hwnd)
    w = r - l
    h = b - t
    return capture_screen(l, t, w, h, scale=scale)


def frame_diff_ratio(a: bytes, b: bytes) -> float:
    """Rough change ratio between two raw BGRA buffers of same size."""
    if not a or not b or len(a) != len(b):
        return 1.0
    diff = sum(1 for i in range(0, len(a), 4) if a[i:i + 4] != b[i:i + 4])
    return diff / (len(a) // 4)
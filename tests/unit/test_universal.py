import ctypes

from gfa.universal.capture import _encode_png_rgb, capture_screen
from gfa.universal.windows import list_windows, find_windows


def test_png_encoder_produces_valid_png():
    # 2x2 red image
    bgra = bytes([0, 0, 255, 255] * 4)  # BGRA
    png = _encode_png_rgb(2, 2, bgra)
    assert png[:8] == b"\x89PNG\r\n\x1a\n"
    assert b"IHDR" in png
    assert b"IDAT" in png
    assert b"IEND" in png


def test_list_windows_returns_list():
    wins = list_windows()
    assert isinstance(wins, list)
    # at least one visible window (desktop has something)
    # not asserting non-empty to avoid flakiness


def test_find_windows_substring():
    # Should not crash; may be empty
    res = find_windows("NONEXISTENT_WINDOW_TITLE_XYZ")
    assert isinstance(res, list)
    assert res == []


def test_capture_screen_returns_frame():
    # This requires an interactive display; skip if unavailable
    try:
        user32 = ctypes.windll.user32
        if user32.GetSystemMetrics(0) <= 0:
            return
    except Exception:
        return
    frame = capture_screen(scale=0.25)
    assert frame.width > 0 and frame.height > 0
    assert frame.png_bytes[:8] == b"\x89PNG\r\n\x1a\n"
    assert len(frame.to_base64()) > 100
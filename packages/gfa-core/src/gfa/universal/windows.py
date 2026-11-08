"""Window enumeration and management (Windows)."""

from __future__ import annotations

import ctypes
import time
from ctypes import wintypes
from dataclasses import dataclass

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32


@dataclass
class WindowInfo:
    hwnd: int
    title: str
    rect: tuple[int, int, int, int]  # left, top, right, bottom
    pid: int | None = None


def _get_pid(hwnd: int) -> int | None:
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    return pid.value or None


def list_windows(visible_only: bool = True) -> list[WindowInfo]:
    result: list[WindowInfo] = []

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def callback(hwnd, _lparam):
        if visible_only and not user32.IsWindowVisible(hwnd):
            return True
        length = user32.GetWindowTextLengthW(hwnd)
        title = ""
        if length > 0:
            buf = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buf, length + 1)
            title = buf.value
        if not title:
            return True
        rect = wintypes.RECT()
        user32.GetWindowRect(hwnd, ctypes.byref(rect))
        result.append(WindowInfo(hwnd=hwnd, title=title, rect=(rect.left, rect.top, rect.right, rect.bottom),
                                pid=_get_pid(hwnd)))
        return True

    user32.EnumWindows(callback, 0)
    return result


def find_windows(title_substring: str) -> list[WindowInfo]:
    needle = title_substring.lower()
    return [w for w in list_windows() if needle in w.title.lower()]


def get_window_rect(hwnd: int) -> tuple[int, int, int, int]:
    rect = wintypes.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(rect))
    return rect.left, rect.top, rect.right, rect.bottom


def get_client_rect(hwnd: int) -> tuple[int, int, int, int]:
    rect = wintypes.RECT()
    user32.GetClientRect(hwnd, ctypes.byref(rect))
    # convert top-left to screen coords
    pt = wintypes.POINT(0, 0)
    user32.ClientToScreen(hwnd, ctypes.byref(pt))
    return pt.x, pt.y, pt.x + rect.right, pt.y + rect.bottom


def focus_window(hwnd: int) -> bool:
    try:
        user32.ShowWindow(hwnd, 9)  # SW_RESTORE
        fg = user32.GetForegroundWindow()
        if fg == hwnd:
            return True
        cur = kernel32.GetCurrentThreadId()
        fg_thread = user32.GetWindowThreadProcessId(fg, None)
        attached = False
        if fg_thread and fg_thread != cur:
            user32.AttachThreadInput(fg_thread, cur, True)
            attached = True
        user32.BringWindowToTop(hwnd)
        user32.SetForegroundWindow(hwnd)
        if attached:
            user32.AttachThreadInput(fg_thread, cur, False)
        time.sleep(0.2)
        return user32.GetForegroundWindow() == hwnd
    except Exception:  # noqa: BLE001
        return False


def is_window_valid(hwnd: int) -> bool:
    return bool(user32.IsWindow(hwnd))
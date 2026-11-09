"""Foreground window capture for game detection (Windows, ctypes)."""

from __future__ import annotations

import ctypes
from dataclasses import dataclass

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32
psapi = ctypes.windll.psapi

PROCESS_QUERY_LIMITED_INFORMATION = 0x1000


@dataclass
class ForegroundWindow:
    """The currently focused window: title + owning process."""

    hwnd: int
    title: str
    pid: int
    process_name: str = ""


def get_foreground_window() -> ForegroundWindow | None:
    """Return the foreground (focused) window, or None if unavailable.

    Uses GetForegroundWindow + GetWindowText + process name via
    GetModuleBaseName. Best-effort: returns None on any failure instead of
    raising, so game detection never breaks other flows.
    """
    try:
        hwnd = user32.GetForegroundWindow()
        if not hwnd:
            return None
        length = user32.GetWindowTextLengthW(hwnd)
        buf = ctypes.create_unicode_buffer(max(1, length + 1))
        user32.GetWindowTextW(hwnd, buf, len(buf))
        title = buf.value or ""
        pid = ctypes.c_ulong()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        process_name = _process_name(pid.value)
        return ForegroundWindow(hwnd=int(hwnd), title=title, pid=int(pid.value),
                                process_name=process_name)
    except Exception:  # noqa: BLE001
        return None


def _process_name(pid: int) -> str:
    try:
        handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if not handle:
            return ""
        try:
            buf = ctypes.create_unicode_buffer(260)
            if psapi.GetModuleBaseNameW(handle, None, buf, len(buf)):
                return buf.value or ""
            return ""
        finally:
            kernel32.CloseHandle(handle)
    except Exception:  # noqa: BLE001
        return ""

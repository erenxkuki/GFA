"""Synchronous keyboard+mouse input for games requiring simultaneous inputs."""

from __future__ import annotations

import ctypes
import time
from ctypes import wintypes
from dataclasses import dataclass, field
from typing import Any

user32 = ctypes.windll.user32

INPUT_KEYBOARD = 1
INPUT_MOUSE = 0
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_UNICODE = 0x0004
MOUSEEVENTF_MOVE = 0x0001
MOUSEEVENTF_ABSOLUTE = 0x8000
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_RIGHTDOWN = 0x0008
MOUSEEVENTF_RIGHTUP = 0x0010
MOUSEEVENTF_MIDDLEDOWN = 0x0020
MOUSEEVENTF_MIDDLEUP = 0x0040
MOUSEEVENTF_WHEEL = 0x0800

VK = {
    "w": 0x57, "a": 0x41, "s": 0x53, "d": 0x44,
    "e": 0x45, "q": 0x51, "r": 0x52, "f": 0x46,
    "space": 0x20, "shift": 0x10, "ctrl": 0x11, "alt": 0x12,
    "up": 0x26, "down": 0x28, "left": 0x25, "right": 0x27,
    "1": 0x31, "2": 0x32, "3": 0x33, "4": 0x34,
    "enter": 0x0D, "escape": 0x1B, "tab": 0x09,
}


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [("wVk", wintypes.WORD), ("wScan", wintypes.WORD),
                ("dwFlags", wintypes.DWORD), ("time", wintypes.DWORD),
                ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong))]


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [("dx", ctypes.c_long), ("dy", ctypes.c_long),
                ("mouseData", wintypes.DWORD), ("dwFlags", wintypes.DWORD),
                ("time", wintypes.DWORD), ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong))]


class HARDWAREINPUT(ctypes.Structure):
    _fields_ = [("uMsg", wintypes.DWORD), ("wParamL", wintypes.WORD), ("wParamH", wintypes.WORD)]


class INPUT(ctypes.Structure):
    class _I(ctypes.Union):
        _fields_ = [("ki", KEYBDINPUT), ("mi", MOUSEINPUT), ("hi", HARDWAREINPUT)]
    _anonymous_ = ("i",)
    _fields_ = [("type", wintypes.DWORD), ("i", _I)]


@dataclass
class InputState:
    keys_held: set[str] = field(default_factory=set)
    mouse_buttons: set[str] = field(default_factory=set)
    mouse_x: int = 0
    mouse_y: int = 0
    emergency: bool = False


class SyncInputController:
    """Sends keyboard and mouse inputs simultaneously.

    Unlike the basic InputController which sends inputs one at a time with
    delays, this controller batches multiple inputs into a single SendInput
    call, enabling true simultaneous key+mouse actions (e.g., WASD movement
    while looking around with the mouse).
    """

    def __init__(self):
        self.state = InputState()
        self._emergency = False

    @property
    def emergency(self) -> bool:
        return self._emergency

    def trigger_emergency_stop(self) -> None:
        self._emergency = True
        self.release_all()

    def reset_emergency(self) -> None:
        self._emergency = False

    def _check(self) -> None:
        if self._emergency:
            raise RuntimeError("Emergency stop active")

    def _vk(self, key: str) -> int:
        k = key.lower()
        if k in VK:
            return VK[k]
        if len(key) == 1:
            return ord(key.upper())
        return 0

    def _send_batch(self, inputs: list[INPUT]) -> None:
        """Send multiple inputs in a single SendInput call (atomic)."""
        if not inputs:
            return
        arr = (INPUT * len(inputs))(*inputs)
        user32.SendInput(len(inputs), arr, ctypes.sizeof(INPUT))

    def key_down(self, key: str) -> None:
        self._check()
        vk = self._vk(key)
        inp = INPUT(type=INPUT_KEYBOARD)
        inp.ki.wVk = vk
        self._send_batch([inp])
        self.state.keys_held.add(key.lower())

    def key_up(self, key: str) -> None:
        self._check()
        vk = self._vk(key)
        inp = INPUT(type=INPUT_KEYBOARD)
        inp.ki.wVk = vk
        inp.ki.dwFlags = KEYEVENTF_KEYUP
        self._send_batch([inp])
        self.state.keys_held.discard(key.lower())

    def tap_key(self, key: str, hold_ms: float = 20) -> None:
        self.key_down(key)
        time.sleep(hold_ms / 1000.0)
        self.key_up(key)

    def type_text(self, text: str) -> None:
        self._check()
        inputs = []
        for ch in text:
            down = INPUT(type=INPUT_KEYBOARD)
            down.ki.wScan = ord(ch)
            down.ki.dwFlags = KEYEVENTF_UNICODE
            up = INPUT(type=INPUT_KEYBOARD)
            up.ki.wScan = ord(ch)
            up.ki.dwFlags = KEYEVENTF_UNICODE | KEYEVENTF_KEYUP
            inputs.extend([down, up])
        self._send_batch(inputs)

    def move_mouse(self, dx: int, dy: int, absolute: bool = False) -> None:
        self._check()
        if absolute:
            sw = user32.GetSystemMetrics(0)
            sh = user32.GetSystemMetrics(1)
            ax = int(dx * 65535 / max(1, sw - 1))
            ay = int(dy * 65535 / max(1, sh - 1))
            flags = MOUSEEVENTF_MOVE | MOUSEEVENTF_ABSOLUTE
        else:
            ax, ay = dx, dy
            flags = MOUSEEVENTF_MOVE
        inp = INPUT(type=INPUT_MOUSE)
        inp.mi.dx = ax
        inp.mi.dy = ay
        inp.mi.dwFlags = flags
        self._send_batch([inp])
        if absolute:
            self.state.mouse_x, self.state.mouse_y = dx, dy

    def click(self, button: str = "left", hold_ms: float = 30) -> None:
        self._check()
        down_flag, up_flag = {
            "left": (MOUSEEVENTF_LEFTDOWN, MOUSEEVENTF_LEFTUP),
            "right": (MOUSEEVENTF_RIGHTDOWN, MOUSEEVENTF_RIGHTUP),
            "middle": (MOUSEEVENTF_MIDDLEDOWN, MOUSEEVENTF_MIDDLEUP),
        }.get(button, (MOUSEEVENTF_LEFTDOWN, MOUSEEVENTF_LEFTUP))
        down = INPUT(type=INPUT_MOUSE)
        down.mi.dwFlags = down_flag
        up = INPUT(type=INPUT_MOUSE)
        up.mi.dwFlags = up_flag
        self._send_batch([down])
        time.sleep(hold_ms / 1000.0)
        self._send_batch([up])

    def look_and_move(self, look_dx: int, look_dy: int, keys: list[str] | None = None,
                      hold_keys: bool = False) -> None:
        """Simultaneously move mouse (look) and press keys (move).

        This is the core FPS input pattern: look around while moving.
        """
        self._check()
        inputs = []
        # Mouse look
        inp = INPUT(type=INPUT_MOUSE)
        inp.mi.dx = look_dx
        inp.mi.dy = look_dy
        inp.mi.dwFlags = MOUSEEVENTF_MOVE
        inputs.append(inp)
        # Key presses (held)
        for key in (keys or []):
            vk = self._vk(key)
            inp = INPUT(type=INPUT_KEYBOARD)
            inp.ki.wVk = vk
            inputs.append(inp)
            self.state.keys_held.add(key.lower())
        self._send_batch(inputs)
        if not hold_keys:
            # Release keys after a short hold
            time.sleep(0.02)
            release = []
            for key in (keys or []):
                vk = self._vk(key)
                inp = INPUT(type=INPUT_KEYBOARD)
                inp.ki.wVk = vk
                inp.ki.dwFlags = KEYEVENTF_KEYUP
                release.append(inp)
                self.state.keys_held.discard(key.lower())
            if release:
                self._send_batch(release)

    def hold_keys(self, keys: list[str]) -> None:
        """Hold multiple keys down simultaneously."""
        self._check()
        inputs = []
        for key in keys:
            vk = self._vk(key)
            inp = INPUT(type=INPUT_KEYBOARD)
            inp.ki.wVk = vk
            inputs.append(inp)
            self.state.keys_held.add(key.lower())
        self._send_batch(inputs)

    def release_keys(self, keys: list[str]) -> None:
        """Release specific keys."""
        inputs = []
        for key in keys:
            vk = self._vk(key)
            inp = INPUT(type=INPUT_KEYBOARD)
            inp.ki.wVk = vk
            inp.ki.dwFlags = KEYEVENTF_KEYUP
            inputs.append(inp)
            self.state.keys_held.discard(key.lower())
        self._send_batch(inputs)

    def scroll(self, amount: int) -> None:
        self._check()
        inp = INPUT(type=INPUT_MOUSE)
        inp.mi.mouseData = ctypes.c_uint(amount).value
        inp.mi.dwFlags = MOUSEEVENTF_WHEEL
        self._send_batch([inp])

    def release_all(self) -> None:
        # Release all held keys
        for key in list(self.state.keys_held):
            self.key_up(key)
        # Release mouse buttons
        for flag in (MOUSEEVENTF_LEFTUP, MOUSEEVENTF_RIGHTUP, MOUSEEVENTF_MIDDLEUP):
            inp = INPUT(type=INPUT_MOUSE)
            inp.mi.dwFlags = flag
            self._send_batch([inp])
        self.state.keys_held.clear()
        self.state.mouse_buttons.clear()

    def tap_sequence(self, sequence: list[tuple[str, float]]) -> None:
        """Execute a timed sequence of key presses. Each item: (key, hold_seconds)."""
        for key, hold in sequence:
            self.key_down(key)
            time.sleep(hold)
            self.key_up(key)
            time.sleep(0.01)
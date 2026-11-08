"""Input control (keyboard, mouse, controller) via Windows SendInput/XInput."""

from __future__ import annotations

import ctypes
import time
from ctypes import wintypes
from dataclasses import dataclass

user32 = ctypes.windll.user32

INPUT_KEYBOARD = 1
INPUT_MOUSE = 0
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_UNICODE = 0x0004
KEYEVENTF_SCANCODE = 0x0008
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
    "enter": 0x0D, "escape": 0x1B, "space": 0x20, "tab": 0x09, "backspace": 0x08,
    "shift": 0x10, "ctrl": 0x11, "alt": 0x12,
    "up": 0x26, "down": 0x28, "left": 0x25, "right": 0x27,
    "w": 0x57, "a": 0x41, "s": 0x53, "d": 0x44, "e": 0x45, "q": 0x51,
    "f": 0x46, "r": 0x52, "1": 0x31, "2": 0x32, "3": 0x33,
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
    keys_down: set[str]
    mouse_position: tuple[int, int]
    emergency_stop: bool = False


class InputController:
    def __init__(self):
        self.state = InputState(keys_down=set(), mouse_position=(0, 0))
        self._emergency = False

    def trigger_emergency_stop(self) -> None:
        self._emergency = True
        self.release_all()

    def reset_emergency(self) -> None:
        self._emergency = False

    @property
    def emergency(self) -> bool:
        return self._emergency

    def _check(self) -> None:
        if self._emergency:
            raise RuntimeError("Emergency stop active")

    def key_down(self, key: str) -> None:
        self._check()
        vk = VK.get(key.lower(), 0)
        if vk == 0 and len(key) == 1:
            vk = ord(key.upper())
        inp = INPUT(type=INPUT_KEYBOARD)
        inp.ki.wVk = vk
        user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(inp))
        self.state.keys_down.add(key.lower())

    def key_up(self, key: str) -> None:
        self._check()
        vk = VK.get(key.lower(), 0)
        if vk == 0 and len(key) == 1:
            vk = ord(key.upper())
        inp = INPUT(type=INPUT_KEYBOARD)
        inp.ki.wVk = vk
        inp.ki.dwFlags = KEYEVENTF_KEYUP
        user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(inp))
        self.state.keys_down.discard(key.lower())

    def tap_key(self, key: str) -> None:
        self.key_down(key)
        time.sleep(0.05)
        self.key_up(key)

    def type_text(self, text: str) -> None:
        self._check()
        for ch in text:
            # key down unicode
            inp = INPUT(type=INPUT_KEYBOARD)
            inp.ki.wScan = ord(ch)
            inp.ki.dwFlags = KEYEVENTF_UNICODE
            user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(inp))
            inp2 = INPUT(type=INPUT_KEYBOARD)
            inp2.ki.wScan = ord(ch)
            inp2.ki.dwFlags = KEYEVENTF_UNICODE | KEYEVENTF_KEYUP
            user32.SendInput(1, ctypes.byref(inp2), ctypes.sizeof(inp2))

    def move_mouse(self, x: int, y: int, absolute: bool = True) -> None:
        self._check()
        if absolute:
            sw = user32.GetSystemMetrics(0)
            sh = user32.GetSystemMetrics(1)
            ax = int(x * 65535 / max(1, sw - 1))
            ay = int(y * 65535 / max(1, sh - 1))
            flags = MOUSEEVENTF_MOVE | MOUSEEVENTF_ABSOLUTE
        else:
            ax, ay = x, y
            flags = MOUSEEVENTF_MOVE
        inp = INPUT(type=INPUT_MOUSE)
        inp.mi.dx = ax
        inp.mi.dy = ay
        inp.mi.dwFlags = flags
        user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(inp))
        self.state.mouse_position = (x, y)

    def click(self, button: str = "left", x: int | None = None, y: int | None = None, count: int = 1) -> None:
        self._check()
        if x is not None and y is not None:
            self.move_mouse(x, y)
        down_flag, up_flag = {
            "left": (MOUSEEVENTF_LEFTDOWN, MOUSEEVENTF_LEFTUP),
            "right": (MOUSEEVENTF_RIGHTDOWN, MOUSEEVENTF_RIGHTUP),
            "middle": (MOUSEEVENTF_MIDDLEDOWN, MOUSEEVENTF_MIDDLEUP),
        }.get(button, (MOUSEEVENTF_LEFTDOWN, MOUSEEVENTF_LEFTUP))
        for _ in range(max(1, count)):
            for flag in (down_flag, up_flag):
                inp = INPUT(type=INPUT_MOUSE)
                inp.mi.dwFlags = flag
                user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(inp))
            time.sleep(0.05)

    def scroll(self, amount: int) -> None:
        self._check()
        inp = INPUT(type=INPUT_MOUSE)
        inp.mi.mouseData = ctypes.c_uint(amount).value  # WHEEL_DELTA units (120 per notch)
        inp.mi.dwFlags = MOUSEEVENTF_WHEEL
        user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(inp))

    def release_all(self) -> None:
        for k in list(self.state.keys_down):
            try:
                self.key_up(k)
            except Exception:  # noqa: BLE001
                pass
        # release mouse buttons
        for flag in (MOUSEEVENTF_LEFTUP, MOUSEEVENTF_RIGHTUP, MOUSEEVENTF_MIDDLEUP):
            inp = INPUT(type=INPUT_MOUSE)
            inp.mi.dwFlags = flag
            user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(inp))
        self.state.keys_down.clear()

    # Controller (XInput read-only for state; output not supported without ViGEm)
    def xinput_state(self, user_index: int = 0):
        try:
            xinput = ctypes.windll.xinput1_4
        except Exception:  # noqa: BLE001
            return None
        class XINPUT_GAMEPAD(ctypes.Structure):
            _fields_ = [("wButtons", wintypes.WORD), ("bLeftTrigger", ctypes.c_ubyte),
                        ("bRightTrigger", ctypes.c_ubyte), ("sThumbLX", ctypes.c_short),
                        ("sThumbLY", ctypes.c_short), ("sThumbRX", ctypes.c_short),
                        ("sThumbRY", ctypes.c_short)]
        class XINPUT_STATE(ctypes.Structure):
            _fields_ = [("dwPacketNumber", wintypes.DWORD), ("Gamepad", XINPUT_GAMEPAD)]
        state = XINPUT_STATE()
        r = xinput.XInputGetState(user_index, ctypes.byref(state))
        if r != 0:
            return None
        return state.Gamepad
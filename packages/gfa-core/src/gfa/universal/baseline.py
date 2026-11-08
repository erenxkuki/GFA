"""Universal Baseline orchestration."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from gfa.gcl.capabilities import CapabilitySet
from gfa.universal.capture import CapturedFrame, capture_window, frame_diff_ratio
from gfa.universal.input import InputController
from gfa.universal.sync_input import SyncInputController
from gfa.input_profiles.keybinds import KeybindProfile, fps_wasd
from gfa.combat.combos import ComboLibrary, create_default_library
from gfa.spatial.depth import SpatialEstimator
from gfa.spatial.multiview.capture import MultiViewCapture
from gfa.universal.windows import WindowInfo, find_windows, focus_window, is_window_valid


@dataclass
class BaselineConfig:
    target_window_title: str | None = None
    hwnd: int | None = None
    capture_scale: float = 0.5
    capture_interval: float = 1.0
    client_only: bool = True
    keybind_profile: KeybindProfile | None = None


class UniversalBaseline:
    def __init__(self, config: BaselineConfig | None = None):
        self.config = config or BaselineConfig()
        self.input = InputController()
        self.sync_input = SyncInputController()
        self.keybinds = self.config.keybind_profile or fps_wasd()
        self.combos = create_default_library()
        self.spatial = SpatialEstimator()
        self._hwnd: int | None = self.config.hwnd
        self._last_frame: CapturedFrame | None = None
        self._last_raw: bytes | None = None
        self._running = False

    @property
    def hwnd(self) -> int | None:
        return self._hwnd

    def select_window(self, title_substring: str) -> WindowInfo | None:
        wins = find_windows(title_substring)
        if not wins:
            return None
        self._hwnd = wins[0].hwnd
        self.config.target_window_title = title_substring
        return wins[0]

    def ensure_window(self) -> int:
        if self._hwnd is None and self.config.target_window_title:
            self.select_window(self.config.target_window_title)
        if self._hwnd is None:
            raise RuntimeError("No target window selected")
        if not is_window_valid(self._hwnd):
            raise RuntimeError("Target window no longer valid")
        return self._hwnd

    def focus(self) -> bool:
        hwnd = self.ensure_window()
        return focus_window(hwnd)

    def observe(self) -> CapturedFrame:
        hwnd = self.ensure_window()
        self.focus()
        time.sleep(0.1)
        frame = capture_window(hwnd, client_only=self.config.client_only, scale=self.config.capture_scale)
        # diff tracking
        raw = frame.raw_bgra
        if self._last_raw is not None and raw is not None:
            _ = frame_diff_ratio(self._last_raw, raw)
        self._last_raw = raw
        self._last_frame = frame
        return frame

    def emergency_stop(self) -> None:
        self.input.trigger_emergency_stop()
        self.sync_input.trigger_emergency_stop()

    def reset_emergency(self) -> None:
        self.input.reset_emergency()
        self.sync_input.reset_emergency()

    # High-level action helpers used by GCL handlers
    def move(self, direction: str, duration_ms: int = 500) -> dict[str, Any]:
        key_map = {
            "forward": self.keybinds.move_forward_key,
            "backward": self.keybinds.move_backward_key,
            "left": self.keybinds.move_left_key,
            "right": self.keybinds.move_right_key,
            "up": "up", "down": "down",
        }
        key = key_map.get(direction)
        if key is None:
            raise ValueError(f"unknown direction {direction}")
        self.input.key_down(key)
        time.sleep(min(duration_ms, 5000) / 1000.0)
        self.input.key_up(key)
        return {"direction": direction, "duration_ms": duration_ms, "key": key}

    def look(self, dx: int, dy: int) -> dict[str, Any]:
        """Move mouse to look around (camera), applying keybind mouse config."""
        adx, ady = self.keybinds.apply_mouse_delta(dx, dy)
        self.sync_input.move_mouse(adx, ady)
        return {"look_dx": adx, "look_dy": ady}

    def look_and_move(self, look_dx: int, look_dy: int, keys: list[str] | None = None) -> dict[str, Any]:
        """Simultaneously look (mouse) and move (keyboard) — core FPS pattern."""
        self.sync_input.look_and_move(look_dx, look_dy, keys or [])
        return {"look_dx": look_dx, "look_dy": look_dy, "keys": keys or []}

    def hold_keys(self, keys: list[str]) -> dict[str, Any]:
        """Hold multiple keys simultaneously."""
        self.sync_input.hold_keys(keys)
        return {"keys": keys}

    def release_keys(self, keys: list[str]) -> dict[str, Any]:
        self.sync_input.release_keys(keys)
        return {"keys": keys}

    def execute_combo(self, name: str) -> dict[str, Any]:
        combo = self.combos.get(name)
        if combo is None:
            raise ValueError(f"unknown combo: {name}")
        ok = combo.execute(self.sync_input)
        return {"combo": name, "executed": ok}

    def spatial_summary(self, objects: list[dict[str, Any]]) -> str:
        return self.spatial.spatial_summary(objects)

    def look_around(self, angles: list[float] | None = None) -> dict[str, Any]:
        """Capture from multiple angles and build a spatial map."""
        mvc = MultiViewCapture(self, angles=angles)
        smap = mvc.capture_all()
        return {"views": len(smap.views), "objects": smap.estimated_positions,
                "confidence": smap.confidence, "summary": smap.summary}

    def click(self, button: str = "left", x: int | None = None, y: int | None = None, count: int = 1) -> dict[str, Any]:
        self.input.click(button=button, x=x, y=y, count=count)
        return {"button": button, "x": x, "y": y, "count": count}

    def scroll(self, amount: int = 0) -> dict[str, Any]:
        self.input.scroll(amount)
        return {"amount": amount}

    def key(self, key: str, action: str = "tap") -> dict[str, Any]:
        if action == "press":
            self.input.key_down(key)
        elif action == "release":
            self.input.key_up(key)
        else:
            self.input.tap_key(key)
        return {"key": key, "action": action}

    def type_text(self, text: str) -> dict[str, Any]:
        self.input.type_text(text)
        return {"text": text}

    def wait(self, duration_ms: int = 500) -> dict[str, Any]:
        time.sleep(min(duration_ms, 30000) / 1000.0)
        return {"duration_ms": duration_ms}

    def capabilities(self) -> CapabilitySet:
        cs = CapabilitySet.core_capabilities()
        # universal baseline already in core; ensure
        cs.add("universal.screen_capture")
        cs.add("universal.keyboard")
        cs.add("universal.mouse")
        return cs

    def register_gcl_handlers(self, executor) -> None:
        from gfa.gcl.schema import Command
        async def observe_handler(cmd: Command):
            frame = self.observe()
            return {"width": frame.width, "height": frame.height, "captured": True}
        async def move_handler(cmd: Command):
            return self.move(cmd.params.get("direction", "forward"), cmd.params.get("duration_ms", 500))
        async def look_handler(cmd: Command):
            return self.look(cmd.params.get("dx", 0), cmd.params.get("dy", 0))
        async def look_and_move_handler(cmd: Command):
            return self.look_and_move(cmd.params.get("look_dx", 0), cmd.params.get("look_dy", 0),
                                     cmd.params.get("keys"))
        async def hold_keys_handler(cmd: Command):
            return self.hold_keys(cmd.params.get("keys", []))
        async def release_keys_handler(cmd: Command):
            return self.release_keys(cmd.params.get("keys", []))
        async def combo_handler(cmd: Command):
            return self.execute_combo(cmd.params.get("name", ""))
        async def look_around_handler(cmd: Command):
            return self.look_around(cmd.params.get("angles"))
        async def click_handler(cmd: Command):
            return self.click(cmd.params.get("button", "left"), cmd.params.get("x"), cmd.params.get("y"), cmd.params.get("count", 1))
        async def scroll_handler(cmd: Command):
            return self.scroll(cmd.params.get("amount", 0))
        async def key_handler(cmd: Command):
            return self.key(cmd.params.get("key", ""), cmd.params.get("action", "tap"))
        async def type_handler(cmd: Command):
            return self.type_text(cmd.params.get("text", ""))
        async def wait_handler(cmd: Command):
            return self.wait(cmd.params.get("duration_ms", 500))
        async def verify_handler(cmd: Command):
            # basic: capture and report ok
            frame = self.observe()
            return {"verified": True, "frame": (frame.width, frame.height)}
        executor.register_handler("observe", observe_handler)
        executor.register_handler("observe_region", observe_handler)
        executor.register_handler("move", move_handler)
        executor.register_handler("look", look_handler)
        executor.register_handler("look_and_move", look_and_move_handler)
        executor.register_handler("hold_keys", hold_keys_handler)
        executor.register_handler("release_keys", release_keys_handler)
        executor.register_handler("combo", combo_handler)
        executor.register_handler("look_around", look_around_handler)
        executor.register_handler("click", click_handler)
        executor.register_handler("scroll", scroll_handler)
        executor.register_handler("key", key_handler)
        executor.register_handler("type_text", type_handler)
        executor.register_handler("wait", wait_handler)
        executor.register_handler("verify", verify_handler)
        async def estop_handler(cmd):
            self.emergency_stop()
            return {"stopped": True}
        executor.register_handler("emergency_stop", estop_handler)
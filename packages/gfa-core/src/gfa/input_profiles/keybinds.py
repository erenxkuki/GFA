"""Per-game keybinding and mouse profiles.

Different games use different control schemes:
- FPS: WASD + mouse look
- Racing: arrows/WASD + mouse/analog steering
- Platformer: arrow keys + space jump
- Some games: inverted Y, different sensitivity, etc.

This module provides a configurable mapping from abstract actions to physical inputs.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# Abstract action names
ACTIONS = [
    "move_forward", "move_backward", "move_left", "move_right",
    "look", "look_up", "look_down", "look_left", "look_right",
    "jump", "crouch", "sprint", "interact", "shoot", "aim", "reload",
    "use_item", "menu", "pause", "accelerate", "brake", "steer_left", "steer_right",
]


@dataclass
class MouseConfig:
    sensitivity_x: float = 1.0
    sensitivity_y: float = 1.0
    invert_y: bool = False
    invert_x: bool = False
    acceleration: float = 0.0  # 0 = linear, >0 = accelerated
    smoothing: float = 0.0
    dpi: int = 800
    raw_input: bool = True  # use raw input (no OS acceleration)


@dataclass
class KeybindProfile:
    name: str = "default"
    game: str | None = None
    # Maps abstract action -> physical key(s). None = unbound.
    keybinds: dict[str, str | list[str]] = field(default_factory=dict)
    mouse: MouseConfig = field(default_factory=MouseConfig)
    # Movement keys for direct access
    move_forward_key: str = "w"
    move_backward_key: str = "s"
    move_left_key: str = "a"
    move_right_key: str = "d"
    look_sensitivity: float = 1.0

    def get_key(self, action: str) -> str | list[str] | None:
        return self.keybinds.get(action)

    def get_keys_for_action(self, action: str) -> list[str]:
        v = self.keybinds.get(action)
        if v is None:
            return []
        if isinstance(v, list):
            return v
        return [v]

    def apply_mouse_delta(self, dx: int, dy: int) -> tuple[int, int]:
        """Apply sensitivity, inversion, and acceleration to mouse delta."""
        sx = dx * self.mouse.sensitivity_x * self.look_sensitivity
        sy = dy * self.mouse.sensitivity_y * self.look_sensitivity
        if self.mouse.invert_x:
            sx = -sx
        if self.mouse.invert_y:
            sy = -sy
        if self.mouse.acceleration > 0:
            sx = sx * (1 + self.mouse.acceleration * abs(sx) / 100.0)
            sy = sy * (1 + self.mouse.acceleration * abs(sy) / 100.0)
        return (int(sx), int(sy))

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name, "game": self.game,
            "keybinds": self.keybinds, "mouse": {
                "sensitivity_x": self.mouse.sensitivity_x,
                "sensitivity_y": self.mouse.sensitivity_y,
                "invert_y": self.mouse.invert_y,
                "invert_x": self.mouse.invert_x,
                "acceleration": self.mouse.acceleration,
                "smoothing": self.mouse.smoothing,
                "dpi": self.mouse.dpi,
                "raw_input": self.mouse.raw_input,
            },
            "move_forward_key": self.move_forward_key,
            "move_backward_key": self.move_backward_key,
            "move_left_key": self.move_left_key,
            "move_right_key": self.move_right_key,
            "look_sensitivity": self.look_sensitivity,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "KeybindProfile":
        mouse_data = data.get("mouse", {})
        mouse = MouseConfig(**{k: v for k, v in mouse_data.items() if k in MouseConfig.__dataclass_fields__})
        kb = {k: v for k, v in data.items() if k not in ("mouse",) and k in cls.__dataclass_fields__}
        kb["mouse"] = mouse
        if "keybinds" in data:
            kb["keybinds"] = data["keybinds"]
        return cls(**kb)

    def save(self, path: Path) -> None:
        path.write_text(json.dumps(self.to_dict(), indent=2), encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> "KeybindProfile":
        data = json.loads(path.read_text(encoding="utf-8"))
        return cls.from_dict(data)


# ---- Presets ----

def fps_wasd() -> KeybindProfile:
    """Standard FPS: WASD + mouse look."""
    return KeybindProfile(
        name="fps-wasd", game=None,
        keybinds={
            "move_forward": "w", "move_backward": "s", "move_left": "a", "move_right": "d",
            "jump": "space", "crouch": "ctrl", "sprint": "shift", "interact": "e",
            "shoot": "mouse_left", "aim": "mouse_right", "reload": "r",
            "use_item": "f", "menu": "escape", "pause": "escape",
        },
        move_forward_key="w", move_backward_key="s", move_left_key="a", move_right_key="d",
    )


def fps_arrows() -> KeybindProfile:
    """Arrow keys + mouse look."""
    return KeybindProfile(
        name="fps-arrows", game=None,
        keybinds={
            "move_forward": "up", "move_backward": "down", "move_left": "left", "move_right": "right",
            "jump": "space", "interact": "e", "shoot": "mouse_left", "aim": "mouse_right",
        },
        move_forward_key="up", move_backward_key="down", move_left_key="left", move_right_key="right",
    )


def racing_wasd() -> KeybindProfile:
    """Racing: WASD or arrows for steering/throttle."""
    return KeybindProfile(
        name="racing-wasd", game=None,
        keybinds={
            "accelerate": "w", "brake": "s", "steer_left": "a", "steer_right": "d",
            "look_left": "q", "look_right": "e", "menu": "escape",
        },
        move_forward_key="w", move_backward_key="s", move_left_key="a", move_right_key="d",
        mouse=MouseConfig(sensitivity_x=0.5, sensitivity_y=0.5, smoothing=0.3),
    )


def platformer_arrows() -> KeybindProfile:
    """Platformer: arrows + space jump."""
    return KeybindProfile(
        name="platformer-arrows", game=None,
        keybinds={
            "move_left": "left", "move_right": "right", "jump": "space",
            "interact": "up", "crouch": "down", "menu": "escape",
        },
        move_forward_key="right", move_backward_key="left",
        move_left_key="left", move_right_key="right",
    )


PRESETS = {
    "fps-wasd": fps_wasd,
    "fps-arrows": fps_arrows,
    "racing-wasd": racing_wasd,
    "platformer-arrows": platformer_arrows,
}


def get_preset(name: str) -> KeybindProfile | None:
    factory = PRESETS.get(name)
    return factory() if factory else None


def list_presets() -> list[str]:
    return list(PRESETS.keys())
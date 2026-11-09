"""Automatic game detection: foreground window -> known game -> presets."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from gfa.detection.profiles import GameProfile, GameProfileRegistry
from gfa.detection.windows import ForegroundWindow, get_foreground_window

WindowProvider = Callable[[], ForegroundWindow | None]


@dataclass
class DetectedGame:
    """Result of detecting the running game."""

    window: ForegroundWindow | None
    profile: GameProfile | None
    confidence: float
    candidates: list[tuple[str, float]]

    @property
    def game_id(self) -> str | None:
        return self.profile.game_id if self.profile else None

    def to_dict(self) -> dict[str, Any]:
        return {
            "window": {
                "hwnd": self.window.hwnd,
                "title": self.window.title,
                "pid": self.window.pid,
                "process": self.window.process_name,
            } if self.window else None,
            "profile": self.profile.to_dict() if self.profile else None,
            "confidence": self.confidence,
            "candidates": [{"game_id": g, "score": s} for g, s in self.candidates],
        }

    def to_text(self) -> str:
        lines = ["Foreground window: " + (f"'{self.window.title}' ({self.window.process_name})" if self.window else "(unavailable)")]
        if self.profile:
            kb = f", keybinds={self.profile.keybind_preset}" if self.profile.keybind_preset else ""
            lines.append(f"Detected game: {self.profile.name} ({self.profile.game_id}) "
                         f"confidence={self.confidence:.2f}{kb}")
        else:
            lines.append("Detected game: unknown (no matching profile)")
        if self.candidates:
            lines.append("Candidates: " + ", ".join(f"{g}={s:.2f}" for g, s in self.candidates))
        return "\n".join(lines)


class GameDetector:
    """Detects which known game is currently focused.

    A ``window_provider`` can be injected for testing; by default the real
    foreground window is read via Win32.
    """

    def __init__(self, registry: GameProfileRegistry | None = None,
                 window_provider: WindowProvider | None = None, data_dir: Path | None = None):
        self.registry = registry or GameProfileRegistry(data_dir)
        self.window_provider = window_provider or get_foreground_window

    def detect(self) -> DetectedGame:
        """Detect the foreground game (never raises; unknown on failure)."""
        try:
            window = self.window_provider()
        except Exception:  # noqa: BLE001
            window = None
        matches = self.registry.match(window)
        candidates = [(p.game_id, s) for p, s in matches]
        best = matches[0] if matches else None
        profile, confidence = (best if best else (None, 0.0))
        return DetectedGame(window=window, profile=profile, confidence=confidence,
                            candidates=candidates)

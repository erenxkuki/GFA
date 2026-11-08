"""Aim assist and target tracking for shooter games."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any


@dataclass
class AimTarget:
    x: int
    y: int
    label: str = "enemy"
    priority: int = 0


class AimAssist:
    """Smooth aiming toward targets with prediction."""

    def __init__(self, sensitivity: float = 1.0, smoothing: float = 0.3,
                 prediction_ms: int = 100, fov: int = 200):
        self.sensitivity = sensitivity
        self.smoothing = smoothing
        self.prediction_ms = prediction_ms
        self.fov = fov  # field of view radius around crosshair
        self._current_aim: tuple[int, int] = (0, 0)

    def select_target(self, targets: list[AimTarget], crosshair: tuple[int, int]) -> AimTarget | None:
        """Select the best target within FOV, prioritized by priority then distance."""
        candidates = []
        for t in targets:
            dist = math.hypot(t.x - crosshair[0], t.y - crosshair[1])
            if dist <= self.fov:
                candidates.append((t, dist))
        if not candidates:
            return None
        # Sort by priority desc, then distance asc
        candidates.sort(key=lambda c: (-c[0].priority, c[1]))
        return candidates[0][0]

    def compute_aim_delta(self, target: AimTarget, crosshair: tuple[int, int],
                          target_velocity: tuple[float, float] = (0, 0)) -> tuple[int, int]:
        """Compute how much to move the mouse to aim at (predicted) target."""
        # Predict target position
        pred_x = target.x + target_velocity[0] * (self.prediction_ms / 1000.0)
        pred_y = target.y + target_velocity[1] * (self.prediction_ms / 1000.0)
        dx = pred_x - crosshair[0]
        dy = pred_y - crosshair[1]
        # Apply sensitivity and smoothing
        move_x = int(dx * self.sensitivity * (1 - self.smoothing))
        move_y = int(dy * self.sensitivity * (1 - self.smoothing))
        return (move_x, move_y)

    def is_on_target(self, crosshair: tuple[int, int], target: AimTarget, tolerance: int = 15) -> bool:
        return math.hypot(crosshair[0] - target.x, crosshair[1] - target.y) <= tolerance
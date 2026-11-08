"""Steering and input smoothing for racing games."""

from __future__ import annotations

import math


class SteeringController:
    """Smooth steering with deadzone and progressive response."""

    def __init__(self, deadzone: float = 0.05, max_angle: float = 1.0,
                 smoothing: float = 0.4, centering_force: float = 0.1):
        self.deadzone = deadzone
        self.max_angle = max_angle
        self.smoothing = smoothing
        self.centering_force = centering_force
        self._current_steering = 0.0

    def compute(self, target_angle: float, current_speed: float = 1.0) -> float:
        """Compute smoothed steering value (-1.0 to 1.0)."""
        # Apply deadzone
        if abs(target_angle) < self.deadzone:
            target_angle = 0.0
        # Clamp
        target_angle = max(-self.max_angle, min(self.max_angle, target_angle))
        # Speed-sensitive: reduce steering at high speed
        speed_factor = max(0.3, 1.0 - current_speed * 0.3)
        target_angle *= speed_factor
        # Smooth
        self._current_steering += (target_angle - self._current_steering) * (1 - self.smoothing)
        # Centering force
        self._current_steering *= (1 - self.centering_force)
        return self._current_steering

    def to_key_presses(self, steering: float, threshold: float = 0.3) -> list[str]:
        """Convert steering value to key presses."""
        keys = []
        if steering < -threshold:
            keys.append("left")
        elif steering > threshold:
            keys.append("right")
        return keys

    def reset(self) -> None:
        self._current_steering = 0.0
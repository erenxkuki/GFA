"""Motion tracking and prediction for fast-paced games."""

from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any


@dataclass
class TrackedObject:
    label: str
    positions: deque = field(default_factory=lambda: deque(maxlen=10))
    velocities: deque = field(default_factory=lambda: deque(maxlen=5))
    last_seen: float = 0.0
    predicted_pos: tuple[int, int] | None = None

    def update(self, x: int, y: int, t: float | None = None) -> None:
        t = t or time.time()
        if self.positions:
            px, py, pt = self.positions[-1]
            dt = max(0.001, t - pt)
            vx = (x - px) / dt
            vy = (y - py) / dt
            self.velocities.append((vx, vy))
        self.positions.append((x, y, t))
        self.last_seen = t
        self.predicted_pos = self.predict(0.1)

    def velocity(self) -> tuple[float, float]:
        if not self.velocities:
            return (0.0, 0.0)
        vx = sum(v[0] for v in self.velocities) / len(self.velocities)
        vy = sum(v[1] for v in self.velocities) / len(self.velocities)
        return (vx, vy)

    def predict(self, lookahead: float) -> tuple[int, int]:
        if not self.positions:
            return (0, 0)
        x, y, t = self.positions[-1]
        vx, vy = self.velocity()
        return (int(x + vx * lookahead), int(y + vy * lookahead))

    def is_stale(self, timeout: float = 1.0) -> bool:
        return (time.time() - self.last_seen) > timeout


class MotionTracker:
    """Tracks multiple objects and predicts their future positions."""

    def __init__(self, lookahead: float = 0.1):
        self.lookahead = lookahead
        self._objects: dict[str, TrackedObject] = {}

    def update(self, label: str, x: int, y: int) -> TrackedObject:
        if label not in self._objects:
            self._objects[label] = TrackedObject(label=label)
        self._objects[label].update(x, y)
        return self._objects[label]

    def update_many(self, objects: list[dict[str, Any]]) -> None:
        for o in objects:
            self.update(o["label"], o["x"], o["y"])

    def get(self, label: str) -> TrackedObject | None:
        return self._objects.get(label)

    def predict(self, label: str, lookahead: float | None = None) -> tuple[int, int] | None:
        obj = self._objects.get(label)
        if obj is None:
            return None
        return obj.predict(lookahead or self.lookahead)

    def all_tracked(self) -> list[TrackedObject]:
        return list(self._objects.values())

    def prune_stale(self, timeout: float = 2.0) -> None:
        stale = [k for k, v in self._objects.items() if v.is_stale(timeout)]
        for k in stale:
            del self._objects[k]
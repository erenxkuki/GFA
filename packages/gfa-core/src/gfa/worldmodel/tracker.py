"""Object tracking: associate detections across steps and estimate velocity."""

from __future__ import annotations

import time
from dataclasses import dataclass, field


@dataclass
class TrackedObject:
    """One tracked object with position history and velocity estimate."""

    label: str
    x: float
    y: float
    w: float = 0.0
    h: float = 0.0
    vx: float = 0.0  # pixels per update step
    vy: float = 0.0
    last_seen_step: int = 0
    last_seen_ms: float = 0.0
    seen_count: int = 0
    history: list[tuple[float, float]] = field(default_factory=list)

    def distance_to(self, px: float, py: float) -> float:
        return ((self.x - px) ** 2 + (self.y - py) ** 2) ** 0.5

    def predicted_at(self, horizon_steps: float) -> tuple[float, float]:
        return (self.x + self.vx * horizon_steps, self.y + self.vy * horizon_steps)

    def to_dict(self) -> dict:
        return {
            "label": self.label, "x": self.x, "y": self.y, "w": self.w, "h": self.h,
            "vx": round(self.vx, 2), "vy": round(self.vy, 2),
            "last_seen_step": self.last_seen_step, "seen_count": self.seen_count,
        }


class ObjectTracker:
    """Tracks colored-object identities across perception steps.

    Association is by label (perception labels are stable identities), with
    stale objects expiring after ``stale_steps`` unobserved updates. Velocity
    is a smoothed (exponential moving average) per-step displacement.
    """

    def __init__(self, stale_steps: int = 5):
        self.tracked: dict[str, TrackedObject] = {}
        self.stale_steps = stale_steps
        self._step = 0
        self._last_step_observed: dict[str, int] = {}

    def update(self, objects: list, step: int | None = None) -> list[TrackedObject]:
        """Update tracks with this step's detections. Returns current tracks."""
        if step is None:
            self._step += 1
            step = self._step
        else:
            self._step = step
        now_ms = time.monotonic() * 1000.0

        seen_labels: set[str] = set()
        for o in objects or []:
            label = getattr(o, "label", None) or (o.get("label") if isinstance(o, dict) else None)
            if not label:
                continue
            x = float(getattr(o, "x", 0) if not isinstance(o, dict) else o.get("x", 0))
            y = float(getattr(o, "y", 0) if not isinstance(o, dict) else o.get("y", 0))
            w = float(getattr(o, "w", 0) if not isinstance(o, dict) else o.get("w", 0))
            h = float(getattr(o, "h", 0) if not isinstance(o, dict) else o.get("h", 0))
            seen_labels.add(label)
            prev = self.tracked.get(label)
            if prev is None:
                self.tracked[label] = TrackedObject(
                    label=label, x=x, y=y, w=w, h=h,
                    last_seen_step=step, last_seen_ms=now_ms, seen_count=1,
                    history=[(x, y)],
                )
            else:
                dt_steps = max(1, step - prev.last_seen_step)
                nvx = (x - prev.x) / dt_steps
                nvy = (y - prev.y) / dt_steps
                prev.vx = 0.5 * prev.vx + 0.5 * nvx
                prev.vy = 0.5 * prev.vy + 0.5 * nvy
                prev.x, prev.y, prev.w, prev.h = x, y, w, h
                prev.last_seen_step = step
                prev.last_seen_ms = now_ms
                prev.seen_count += 1
                prev.history.append((x, y))
                prev.history = prev.history[-8:]  # keep last 8 positions
            self._last_step_observed[label] = step

        # expire stale tracks
        stale = [k for k in self.tracked if step - self._last_step_observed.get(k, step) > self.stale_steps]
        for k in stale:
            del self.tracked[k]
        return list(self.tracked.values())

    def get(self, label: str) -> TrackedObject | None:
        return self.tracked.get(label)

    def clear(self) -> None:
        self.tracked.clear()
        self._last_step_observed.clear()
        self._step = 0

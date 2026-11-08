"""Perception interface and basic implementations."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from gfa.universal.capture import CapturedFrame


@dataclass
class DetectedObject:
    label: str
    x: int
    y: int
    w: int = 0
    h: int = 0
    confidence: float = 1.0
    color: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class PerceptionEngine(Protocol):
    def analyze(self, frame: CapturedFrame) -> list[DetectedObject]: ...


class ColorBlobPerception:
    """Detects simple colored rectangles by sampling raw frame pixels.

    Useful for controlled test environments (e.g., Tkinter sandbox with
    distinctly colored squares). Not a general vision system.
    """

    def __init__(self, color_map: dict[str, tuple[int, int, int]] | None = None, tolerance: int = 40):
        # color_map: label -> (R,G,B) target
        self.color_map = color_map or {"red": (220, 30, 30), "blue": (30, 30, 220), "green": (30, 200, 30)}
        self.tolerance = tolerance

    def analyze(self, frame: CapturedFrame) -> list[DetectedObject]:
        if frame.raw_bgra is None:
            return []
        raw = frame.raw_bgra
        w, h = frame.width, frame.height
        results: list[DetectedObject] = []
        # downsample scan to find centroids per color
        accum: dict[str, list[tuple[int, int]]] = {k: [] for k in self.color_map}
        for y in range(0, h, 2):
            for x in range(0, w, 2):
                i = (y * w + x) * 4
                if i + 3 >= len(raw):
                    continue
                b, g, r = raw[i], raw[i + 1], raw[i + 2]
                for label, (tr, tg, tb) in self.color_map.items():
                    if (abs(r - tr) < self.tolerance and abs(g - tg) < self.tolerance and
                            abs(b - tb) < self.tolerance):
                        accum[label].append((x, y))
        for label, pts in accum.items():
            if len(pts) < 5:
                continue
            xs = [p[0] for p in pts]
            ys = [p[1] for p in pts]
            cx = sum(xs) // len(xs)
            cy = sum(ys) // len(ys)
            results.append(DetectedObject(label=label, x=cx, y=cy, w=max(xs) - min(xs),
                                          h=max(ys) - min(ys), confidence=min(1.0, len(pts) / 100.0)))
        return results
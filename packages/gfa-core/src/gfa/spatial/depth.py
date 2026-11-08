"""3D spatial awareness from 2D screenshots.

Estimates depth/distance using visual cues:
- Object size (bigger = closer)
- Vertical position (higher on screen = further in many games)
- Perspective lines
- Known object sizes
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any


@dataclass
class SpatialObject:
    label: str
    x: int  # screen x
    y: int  # screen y
    w: int  # width in pixels
    h: int  # height in pixels
    estimated_depth: float = 1.0  # 0 = very close, 1 = far
    confidence: float = 0.5
    velocity: tuple[float, float] = (0.0, 0.0)


class SpatialEstimator:
    """Estimates 3D spatial relationships from 2D frame data."""

    def __init__(self, frame_width: int = 1920, frame_height: int = 1080):
        self.frame_width = frame_width
        self.frame_height = frame_height
        self._known_sizes: dict[str, int] = {}  # label -> typical pixel height at depth 0.5

    def register_known_size(self, label: str, typical_height: int) -> None:
        """Register a known object's typical screen height for depth calibration."""
        self._known_sizes[label] = typical_height

    def estimate_depth(self, obj: dict[str, Any]) -> float:
        """Estimate depth (0=close, 1=far) from object properties.

        Uses multiple cues:
        1. Object size: smaller = further (if known size registered)
        2. Vertical position: higher on screen = further (in most 3D games)
        3. Aspect ratio consistency
        """
        h = obj.get("h", 1)
        y = obj.get("y", self.frame_height // 2)
        label = obj.get("label", "")

        # Cue 1: size-based depth
        size_depth = 0.5
        if label in self._known_sizes and h > 0:
            typical = self._known_sizes[label]
            ratio = typical / max(1, h)
            # ratio > 1 means object is smaller than typical (further)
            size_depth = min(1.0, max(0.0, (ratio - 0.5) / 2.0 + 0.3))

        # Cue 2: vertical position depth (higher = further in most games)
        vpos_depth = y / max(1, self.frame_height)

        # Combine cues (weighted)
        depth = size_depth * 0.6 + vpos_depth * 0.4
        return min(1.0, max(0.0, depth))

    def estimate_distance_px(self, obj: dict[str, Any], reference_depth: float = 0.5) -> float:
        """Estimate pixel distance from center of screen."""
        cx = self.frame_width // 2
        cy = self.frame_height // 2
        dx = obj.get("x", cx) - cx
        dy = obj.get("y", cy) - cy
        return math.hypot(dx, dy)

    def find_nearest(self, objects: list[dict[str, Any]]) -> dict[str, Any] | None:
        """Find the nearest object (lowest depth)."""
        if not objects:
            return None
        scored = [(self.estimate_depth(o), o) for o in objects]
        scored.sort(key=lambda x: x[0])
        return scored[0][1]

    def find_threats(self, objects: list[dict[str, Any]], threat_labels: list[str] | None = None) -> list[dict[str, Any]]:
        """Find objects that are close and likely threats."""
        threats = []
        for o in objects:
            label = o.get("label", "")
            if threat_labels and label not in threat_labels:
                continue
            depth = self.estimate_depth(o)
            dist = self.estimate_distance_px(o)
            # Close + centered = threat
            if depth < 0.4 or dist < self.frame_width * 0.25:
                threats.append({**o, "depth": depth, "screen_dist": dist})
        threats.sort(key=lambda t: t["screen_dist"])
        return threats

    def spatial_summary(self, objects: list[dict[str, Any]]) -> str:
        """Generate a text summary of spatial relationships."""
        if not objects:
            return "No objects detected."
        parts = []
        for o in objects:
            depth = self.estimate_depth(o)
            dist = self.estimate_distance_px(o)
            depth_str = "close" if depth < 0.3 else "medium" if depth < 0.7 else "far"
            parts.append(f"{o.get('label', '?')} at ({o.get('x', 0)},{o.get('y', 0)}) - {depth_str}, screen_dist={dist:.0f}px")
        nearest = self.find_nearest(objects)
        if nearest:
            parts.append(f"Nearest: {nearest.get('label', '?')}")
        return "; ".join(parts)
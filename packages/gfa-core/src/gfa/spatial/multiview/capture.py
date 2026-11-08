"""Multi-view spatial capture: look around to build 3D understanding from 2D.

Instead of guessing depth from a single screenshot, rotate the camera in
increments, capture from multiple angles, and reconstruct a spatial map.
Like a human looking around to build a mental map of the room.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from gfa.universal.baseline import UniversalBaseline
from gfa.vision.perception import VisionPerception, PerceptionResult
from gfa.universal.sync_input import SyncInputController


@dataclass
class ViewCapture:
    """A single captured view from one angle."""
    angle: float  # yaw angle in degrees
    frame: Any  # CapturedFrame
    perception: PerceptionResult
    timestamp: float = field(default_factory=time.time)


@dataclass
class SpatialMap:
    """A reconstructed spatial understanding from multiple views."""
    views: list[ViewCapture] = field(default_factory=list)
    objects: dict[str, list[dict[str, Any]]] = field(default_factory=dict)  # label -> list of detections per view
    estimated_positions: dict[str, tuple[float, float]] = field(default_factory=dict)  # label -> (x, y) in map coords
    confidence: float = 0.0
    summary: str = ""

    def add_view(self, view: ViewCapture) -> None:
        self.views.append(view)
        for obj in view.perception.objects:
            self.objects.setdefault(obj.label, []).append({
                "view_angle": view.angle,
                "x": obj.x, "y": obj.y,
                "w": obj.w, "h": obj.h,
                "confidence": obj.confidence,
            })
        self._reconstruct()

    def _reconstruct(self) -> None:
        """Estimate 2D positions from multi-view detections.

        Uses the principle: an object seen from multiple angles at consistent
        screen positions is likely at a specific world position. Objects seen
        from only one angle are less certain.
        """
        if not self.views:
            return

        n_views = len(self.views)
        self.confidence = min(1.0, n_views / 4.0)  # 4 views = full confidence

        # For each detected object label, estimate position
        for label, detections in self.objects.items():
            if len(detections) == 1:
                # Single view: use screen position as rough estimate
                d = detections[0]
                self.estimated_positions[label] = (float(d["x"]), float(d["y"]))
            else:
                # Multiple views: average screen positions weighted by confidence
                # In a real implementation, this would use triangulation
                # Here we use a simplified weighted average
                total_conf = sum(d["confidence"] for d in detections)
                if total_conf > 0:
                    wx = sum(d["x"] * d["confidence"] for d in detections) / total_conf
                    wy = sum(d["y"] * d["confidence"] for d in detections) / total_conf
                    self.estimated_positions[label] = (wx, wy)

        # Build summary
        parts = [f"Spatial map from {n_views} views."]
        if self.estimated_positions:
            pos_str = ", ".join(f"{k}@({v[0]:.0f},{v[1]:.0f})" for k, v in self.estimated_positions.items())
            parts.append(f"Objects: {pos_str}.")
        parts.append(f"Confidence: {self.confidence:.2f}.")
        self.summary = " ".join(parts)

    def get_object_position(self, label: str) -> tuple[float, float] | None:
        return self.estimated_positions.get(label)

    def object_seen_from(self, label: str) -> int:
        return len(self.objects.get(label, []))


class MultiViewCapture:
    """Captures views from multiple angles by rotating the camera."""

    def __init__(self, baseline: "UniversalBaseline", angles: list[float] | None = None,
                 perception: VisionPerception | None = None, settle_time: float = 0.3):
        self.baseline = baseline
        self.angles = angles or [0, 90, 180, 270]
        self.perception = perception or VisionPerception()
        self.settle_time = settle_time
        self._current_angle = 0.0

    def capture_all(self) -> SpatialMap:
        """Rotate through all angles, capture, and build a spatial map."""
        smap = SpatialMap()
        start_angle = self._current_angle

        for target_angle in self.angles:
            delta = target_angle - self._current_angle
            # Normalize to -180..180
            if delta > 180:
                delta -= 360
            if delta < -180:
                delta += 360

            # Rotate camera
            if abs(delta) > 1:
                # Convert angle to mouse movement (approximate)
                # Typical: 90 degrees ~ 400-800 mouse pixels depending on sensitivity
                mouse_dx = int(delta * 6.0)  # rough conversion
                self.baseline.sync_input.move_mouse(mouse_dx, 0)
                time.sleep(self.settle_time)

            # Capture and perceive
            frame = self.baseline.observe()
            result = self.perception.analyze(frame)
            view = ViewCapture(angle=target_angle, frame=frame, perception=result)
            smap.add_view(view)
            self._current_angle = target_angle

        # Return to starting angle
        delta = start_angle - self._current_angle
        if abs(delta) > 1:
            mouse_dx = int(delta * 6.0)
            self.baseline.sync_input.move_mouse(mouse_dx, 0)
            time.sleep(self.settle_time)
        self._current_angle = start_angle

        return smap

    def capture_single(self, angle: float) -> ViewCapture:
        """Capture from a specific angle."""
        delta = angle - self._current_angle
        if delta > 180:
            delta -= 360
        if delta < -180:
            delta += 360
        if abs(delta) > 1:
            mouse_dx = int(delta * 6.0)
            self.baseline.sync_input.move_mouse(mouse_dx, 0)
            time.sleep(self.settle_time)
        self._current_angle = angle
        frame = self.baseline.observe()
        result = self.perception.analyze(frame)
        return ViewCapture(angle=angle, frame=frame, perception=result)
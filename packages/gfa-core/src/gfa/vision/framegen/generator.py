"""Frame Generation for perception: like DLSS/FSR frame gen for AI vision.

Instead of running expensive perception (OCR, color detection) on every frame,
capture at a reduced rate and "generate" intermediate perception states using
lightweight frame-diff and motion prediction. Full perception only runs when
significant change is detected.

This dramatically reduces token usage and CPU cost while keeping the AI responsive.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from gfa.universal.capture import CapturedFrame, frame_diff_ratio
from gfa.vision.perception import PerceptionResult, VisionPerception


@dataclass
class GeneratedFrame:
    """A perception result that may be real or interpolated."""
    result: PerceptionResult
    is_real: bool  # True if full perception ran, False if interpolated
    confidence: float = 1.0
    timestamp: float = field(default_factory=time.time)
    change_ratio: float = 0.0


class FrameGenerator:
    """Generates perception frames between real captures.

    Strategy:
    1. Always capture the screen (cheap GDI blit).
    2. Run full perception only every `keyframe_interval` frames OR when change > threshold.
    3. Between keyframes, reuse last perception result but update change_ratio.
    4. Predict object positions based on last known velocity (simple extrapolation).
    """

    def __init__(self, perception: VisionPerception, keyframe_interval: int = 5,
                 change_threshold: float = 0.05):
        self.perception = perception
        self.keyframe_interval = keyframe_interval
        self.change_threshold = change_threshold
        self._frame_count = 0
        self._last_keyframe: GeneratedFrame | None = None
        self._last_raw: bytes | None = None
        self._object_velocity: dict[str, tuple[float, float]] = {}

    def process(self, frame: CapturedFrame) -> GeneratedFrame:
        """Process a captured frame, returning a (possibly generated) perception result."""
        self._frame_count += 1
        change_ratio = 0.0
        if self._last_raw is not None and frame.raw_bgra is not None:
            if len(self._last_raw) == len(frame.raw_bgra):
                change_ratio = frame_diff_ratio(self._last_raw, frame.raw_bgra)
        self._last_raw = frame.raw_bgra

        is_keyframe = (
            self._last_keyframe is None
            or self._frame_count % self.keyframe_interval == 0
            or change_ratio >= self.change_threshold
        )

        if is_keyframe:
            result = self.perception.analyze(frame)
            self._update_velocity(result)
            gf = GeneratedFrame(result=result, is_real=True, confidence=1.0,
                                change_ratio=change_ratio)
            self._last_keyframe = gf
            return gf

        # Generate intermediate frame: reuse last result, update change_ratio
        if self._last_keyframe is not None:
            result = self._predict(self._last_keyframe.result, change_ratio)
            gf = GeneratedFrame(result=result, is_real=False,
                                confidence=max(0.3, 1.0 - change_ratio * 2),
                                change_ratio=change_ratio)
            return gf

        # Fallback: run full perception
        result = self.perception.analyze(frame)
        gf = GeneratedFrame(result=result, is_real=True, confidence=1.0, change_ratio=change_ratio)
        self._last_keyframe = gf
        return gf

    def _update_velocity(self, result: PerceptionResult) -> None:
        """Track object velocities for prediction."""
        if self._last_keyframe is None:
            for o in result.objects:
                self._object_velocity[o.label] = (0.0, 0.0)
            return
        prev_map = {o.label: o for o in self._last_keyframe.result.objects}
        for o in result.objects:
            if o.label in prev_map:
                p = prev_map[o.label]
                vx = o.x - p.x
                vy = o.y - p.y
                self._object_velocity[o.label] = (vx * 0.5, vy * 0.5)  # smooth

    def _predict(self, last: PerceptionResult, change_ratio: float) -> PerceptionResult:
        """Predict current perception from last keyframe + velocity."""
        predicted_objects = []
        for o in last.objects:
            vx, vy = self._object_velocity.get(o.label, (0.0, 0.0))
            predicted_objects.append(type(o)(
                label=o.label, x=int(o.x + vx), y=int(o.y + vy),
                w=o.w, h=o.h, confidence=o.confidence * 0.8, color=o.color,
                metadata={**o.metadata, "predicted": True},
            ))
        # Build compact summary noting it's generated
        summary = last.compact_summary
        if change_ratio > 0.01:
            summary += f" [generated frame, change={change_ratio:.2f}]"
        else:
            summary += " [generated frame, no significant change]"
        return PerceptionResult(
            objects=predicted_objects,
            ui_regions=last.ui_regions,
            text_blocks=last.text_blocks,  # reuse OCR text
            compact_summary=summary,
            frame_size=last.frame_size,
        )

    def reset(self) -> None:
        self._frame_count = 0
        self._last_keyframe = None
        self._last_raw = None
        self._object_velocity.clear()
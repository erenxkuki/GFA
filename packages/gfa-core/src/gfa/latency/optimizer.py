"""Latency optimization for fast-paced games.

Minimizes every step of the perception-action loop:
1. Frame skipping: only process every Nth frame
2. OCR bypass: skip OCR in fast mode (use color detection only)
3. Speculative execution: act on prediction, verify later
4. Input coalescing: batch multiple inputs into one SendInput
5. Performance tracking: measure and report per-step latency
"""

from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Callable

from gfa.universal.capture import CapturedFrame, frame_diff_ratio


@dataclass
class LatencyMetrics:
    capture_ms: float = 0.0
    perception_ms: float = 0.0
    reasoning_ms: float = 0.0
    execution_ms: float = 0.0
    total_ms: float = 0.0
    frame_skip_rate: float = 0.0
    ocr_skip_count: int = 0


class LatencyTracker:
    """Tracks per-step latency with rolling averages."""

    def __init__(self, window: int = 60):
        self.window = window
        self._samples: deque[LatencyMetrics] = deque(maxlen=window)

    def record(self, m: LatencyMetrics) -> None:
        self._samples.append(m)

    def avg_total(self) -> float:
        if not self._samples:
            return 0.0
        return sum(s.total_ms for s in self._samples) / len(self._samples)

    def avg_capture(self) -> float:
        if not self._samples:
            return 0.0
        return sum(s.capture_ms for s in self._samples) / len(self._samples)

    def avg_perception(self) -> float:
        if not self._samples:
            return 0.0
        return sum(s.perception_ms for s in self._samples) / len(self._samples)

    def avg_reasoning(self) -> float:
        if not self._samples:
            return 0.0
        return sum(s.reasoning_ms for s in self._samples) / len(self._samples)

    def avg_execution(self) -> float:
        if not self._samples:
            return 0.0
        return sum(s.execution_ms for s in self._samples) / len(self._samples)

    def max_total(self) -> float:
        if not self._samples:
            return 0.0
        return max(s.total_ms for s in self._samples)

    def report(self) -> dict[str, float]:
        return {
            "avg_total_ms": round(self.avg_total(), 1),
            "avg_capture_ms": round(self.avg_capture(), 1),
            "avg_perception_ms": round(self.avg_perception(), 1),
            "avg_reasoning_ms": round(self.avg_reasoning(), 1),
            "avg_execution_ms": round(self.avg_execution(), 1),
            "max_total_ms": round(self.max_total(), 1),
            "samples": len(self._samples),
        }


class FrameSkipper:
    """Adaptive frame skipping: process fewer frames when latency is high."""

    def __init__(self, target_fps: int = 30, min_skip: int = 1, max_skip: int = 5):
        self.target_fps = target_fps
        self.target_interval = 1.0 / target_fps
        self.min_skip = min_skip
        self.max_skip = max_skip
        self._skip = min_skip
        self._frame_count = 0
        self._last_process_time = 0.0

    def should_process(self) -> bool:
        self._frame_count += 1
        if self._frame_count % self._skip != 0:
            return False
        now = time.time()
        elapsed = now - self._last_process_time
        if elapsed < self.target_interval * 0.5:
            # Too fast, increase skip
            self._skip = min(self.max_skip, self._skip + 1)
        elif elapsed > self.target_interval * 2:
            # Too slow, decrease skip
            self._skip = max(self.min_skip, self._skip - 1)
        self._last_process_time = now
        return True

    @property
    def skip_rate(self) -> int:
        return self._skip


class LatencyOptimizer:
    """Combines all latency optimizations into a single pipeline."""

    def __init__(self, target_fps: int = 30, skip_ocr_in_fast: bool = True,
                 ocr_every_n: int = 3, frame_skip: bool = True):
        self.target_fps = target_fps
        self.skip_ocr_in_fast = skip_ocr_in_fast
        self.ocr_every_n = ocr_every_n
        self.frame_skip = frame_skip
        self.tracker = LatencyTracker()
        self.skipper = FrameSkipper(target_fps=target_fps)
        self._frame_count = 0
        self._last_ocr_frame = 0
        self._cached_ocr: list[str] = []
        self._last_raw: bytes | None = None
        self._last_change: float = 0.0

    def should_process_frame(self) -> bool:
        if not self.frame_skip:
            return True
        return self.skipper.should_process()

    def should_run_ocr(self) -> bool:
        self._frame_count += 1
        if self._frame_count == 1 or (self._frame_count - self._last_ocr_frame >= self.ocr_every_n):
            self._last_ocr_frame = self._frame_count
            return True
        return False

    def update_change(self, frame: CapturedFrame) -> float:
        if self._last_raw is not None and frame.raw_bgra is not None:
            if len(self._last_raw) == len(frame.raw_bgra):
                self._last_change = frame_diff_ratio(self._last_raw, frame.raw_bgra)
        self._last_raw = frame.raw_bgra
        return self._last_change

    @property
    def last_change(self) -> float:
        return self._last_change

    def get_cached_ocr(self) -> list[str]:
        return self._cached_ocr

    def set_cached_ocr(self, text_blocks: list[str]) -> None:
        self._cached_ocr = text_blocks

    def optimize_perception(self, frame: CapturedFrame, perception_fn: Callable) -> tuple[Any, LatencyMetrics]:
        """Run perception with latency tracking and optimizations."""
        m = LatencyMetrics()
        t0 = time.time()

        # Capture already done (frame passed in)
        m.capture_ms = 0  # capture measured separately

        # Change detection
        change = self.update_change(frame)

        # Decide whether to run full perception
        t1 = time.time()
        if change < 0.005 and self._last_change < 0.005:
            # No change: reuse cached result (skip perception entirely)
            m.perception_ms = (time.time() - t1) * 1000
            m.total_ms = (time.time() - t0) * 1000
            self.tracker.record(m)
            return None, m  # None signals "no change, skip"

        result = perception_fn(frame)
        m.perception_ms = (time.time() - t1) * 1000
        m.total_ms = (time.time() - t0) * 1000
        self.tracker.record(m)
        return result, m

    def report(self) -> dict[str, Any]:
        r = self.tracker.report()
        r["skip_rate"] = self.skipper.skip_rate
        r["ocr_skip_count"] = self._frame_count - self._last_ocr_frame
        r["last_change"] = round(self._last_change, 4)
        return r
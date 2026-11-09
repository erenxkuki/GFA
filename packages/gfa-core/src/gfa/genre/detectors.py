"""Genre-specific HUD detectors: fast, dependency-free UI element recognition.

Each genre declares elements (see :mod:`gfa.genre.profiles`); this module
detects them directly from frame pixels with specialized heuristics:

- ``crosshair`` — bright compact cluster at screen center
- ``bar`` — horizontal saturated-color band (health/mana bars); also
  estimates the fill ratio ("health ~35%")
- ``dialogue`` — uniform bottom band (dialogue/subtitle box)
- ``marker`` — small high-contrast cluster (quest marker / collectible)
- ``minimap`` — corner square with moderate variance
- ``digits`` — high-variance band (scores, timers, ammo, speedometers)
- ``grid`` — grid-like structure (inventory)
- ``panel`` — broad uniform band (resource/menu bars)

All detection reads ``frame.raw_bgra`` (the same buffer color perception
uses) — no OCR/LLM calls, no dependencies, ~sub-millisecond per element.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from gfa.genre.profiles import GenreProfile, get_genre
from gfa.universal.capture import CapturedFrame


@dataclass
class DetectedElement:
    key: str
    present: bool
    confidence: float
    x: int = 0
    y: int = 0
    w: int = 0
    h: int = 0
    value: str = ""  # e.g. "health ~35%" for bars


class GenreDetector:
    """Runs the specialized detectors for one genre profile on a frame."""

    def __init__(self, genre: str | GenreProfile, sample_step: int = 4):
        self.profile = genre if isinstance(genre, GenreProfile) else get_genre(genre)
        self.sample_step = max(1, sample_step)

    @property
    def genre_name(self) -> str:
        return self.profile.name

    # ------------------------------------------------------------------
    def detect(self, frame: CapturedFrame) -> list[DetectedElement]:
        raw = frame.raw_bgra
        if raw is None or frame.width <= 0 or frame.height <= 0:
            return []
        results: list[DetectedElement] = []
        for cfg in self.profile.elements:
            fn = self._DISPATCH.get(cfg.kind)
            if fn is None:
                continue
            box = self._region_box(frame, cfg.region)
            try:
                element = fn(self, frame, box, cfg.name)
            except Exception:  # noqa: BLE001
                element = DetectedElement(key=cfg.name, present=False, confidence=0.0,
                                          x=box[0], y=box[1], w=box[2], h=box[3])
            results.append(element)
        return results

    def summary(self, elements: list[DetectedElement]) -> str:
        """LLM-readable genre HUD summary, e.g. 'Genre HUD (fps): health ~35%, ammo present'."""
        parts = [f"Genre HUD ({self.genre_name}):"]
        for e in elements:
            if not e.present:
                continue
            if e.value:
                parts.append(f"{e.key} {e.value} (conf {e.confidence:.2f})")
            elif e.confidence > 0:
                parts.append(f"{e.key} present (conf {e.confidence:.2f})")
        return " ".join(parts) if len(parts) > 1 else f"Genre HUD ({self.genre_name}): nothing detected"

    # ------------------------------------------------------------------
    # Region helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _region_box(frame: CapturedFrame, region: str) -> tuple[int, int, int, int]:
        """(x0, y0, w, h) for a named region."""
        w, h = frame.width, frame.height
        cw, ch = w // 2, h // 2
        if region == "center":
            bw, bh = max(20, int(w * 0.06)), max(20, int(h * 0.08))
            return (cw - bw // 2, ch - bh // 2, bw, bh)
        if region == "top_left":
            return (0, 0, max(20, int(w * 0.30)), max(16, int(h * 0.14)))
        if region == "top_right":
            return (w - max(20, int(w * 0.20)), 0, max(20, int(w * 0.20)), max(16, int(h * 0.20)))
        if region == "bottom_left":
            return (0, h - max(16, int(h * 0.20)), max(20, int(w * 0.20)), max(16, int(h * 0.20)))
        if region == "bottom_right":
            return (w - max(20, int(w * 0.25)), h - max(16, int(h * 0.20)),
                    max(20, int(w * 0.25)), max(16, int(h * 0.20)))
        if region == "top_band":
            return (0, 0, w, max(8, int(h * 0.09)))
        if region == "bottom_band":
            return (0, h - max(10, int(h * 0.12)), w, max(10, int(h * 0.12)))
        if region == "right_band":
            return (w - max(20, int(w * 0.15)), 0, max(20, int(w * 0.15)), h)
        return (0, 0, w, h)

    def _sample(self, frame: CapturedFrame, box: tuple[int, int, int, int], step: int | None = None):
        """Sample pixels in a box: returns list of (r, g, b)."""
        x0, y0, bw, bh = box
        raw = frame.raw_bgra
        assert raw is not None
        w = frame.width
        s = step if step is not None else self.sample_step
        samples: list[tuple[int, int, int]] = []
        for y in range(y0, y0 + bh, s):
            for x in range(x0, x0 + bw, s):
                i = (y * w + x) * 4
                if i + 2 < len(raw):
                    samples.append((raw[i + 2], raw[i + 1], raw[i]))
        return samples

    # ------------------------------------------------------------------
    # Detectors
    # ------------------------------------------------------------------
    def _detect_crosshair(self, frame, box, key) -> DetectedElement:
        """Bright compact cluster exactly at the crosshair box center."""
        x0, y0, bw, bh = box
        samples = self._sample(frame, box, step=1)  # tiny box: sample every pixel
        if len(samples) < 5:
            return self._miss(key, box)
        bright = [s for s in samples if sum(s) / 3.0 > 170]
        if not bright:
            return self._miss(key, box)
        # concentration: bright pixels should cluster near the very center
        mid_bright = [s for s in bright if s[0] > 200 and s[1] > 200 and s[2] > 200]
        ratio = len(bright) / max(1, len(samples))
        conf = min(0.99, (len(mid_bright) / max(1, len(bright))) * 0.5 + ratio * 0.5)
        present = ratio >= 0.05
        return DetectedElement(key=key, present=present, confidence=conf if present else 0.0,
                               x=x0, y=y0, w=bw, h=bh)

    def _detect_bar(self, frame, box, key) -> DetectedElement:
        """Horizontal saturated (red/green) band -> health-style bar + fill estimate."""
        x0, y0, bw, bh = box
        if bh < 4 or bw < 16:
            return self._miss(key, box)
        raw = frame.raw_bgra
        assert raw is not None
        w = frame.width
        best_ratio = 0.0
        best_fill = 0.0
        best_row = y0
        for y in range(y0, y0 + bh, 2):
            red = green = 0
            for x in range(x0, x0 + bw, 2):
                i = (y * w + x) * 4
                if i + 2 >= len(raw):
                    continue
                r, g, b = raw[i + 2], raw[i + 1], raw[i]
                if r > 100 and r > g + 30 and r > b + 30:
                    red += 1
                elif g > 100 and g > r + 20 and g > b + 20:
                    green += 1
            total = (bw / 2.0) or 1
            fill = (red + green) / total
            if fill > best_ratio:
                best_ratio = fill
                best_fill = green / max(1.0, (red + green))
                best_row = y
        present = best_ratio >= 0.12
        value = ""
        if present:
            pct = round(best_fill * 100)
            value = f"low (~{pct}%)" if best_fill < 0.5 else f"~{pct}%"
        return DetectedElement(key=key, present=present,
                               confidence=round(min(0.98, best_ratio * 1.5), 2) if present else 0.0,
                               x=x0, y=best_row, w=bw, h=max(4, bh // 2), value=value)

    def _detect_dialogue(self, frame, box, key) -> DetectedElement:
        """Bottom band uniformity -> dialogue/subtitle box present."""
        samples = self._sample(frame, box)
        if len(samples) < 20:
            return self._miss(key, box)
        lums = [sum(s) / 3.0 for s in samples]
        mean = sum(lums) / len(lums)
        var = sum((v - mean) ** 2 for v in lums) / len(lums)
        std = math.sqrt(var)
        # uniform dark/mid bands score high
        uniformity = max(0.0, 45.0 - std) / 45.0
        present = std < 40
        return DetectedElement(key=key, present=present,
                               confidence=round(uniformity, 2) if present else 0.0,
                               x=box[0], y=box[1], w=box[2], h=box[3])

    def _detect_marker(self, frame, box, key) -> DetectedElement:
        """Small high-contrast cluster in a corner box (quest/coin marker)."""
        samples = self._sample(frame, box)
        if len(samples) < 20:
            return self._miss(key, box)
        lums = [sum(s) / 3.0 for s in samples]
        mean = sum(lums) / len(lums)
        var = sum((v - mean) ** 2 for v in lums) / len(lums)
        std = math.sqrt(var)
        present = 15.0 < std < 120.0  # structured but not chaotic
        conf = max(0.0, min(0.9, 1.0 - abs(std - 55.0) / 80.0)) if present else 0.0
        return DetectedElement(key=key, present=present, confidence=round(conf, 2),
                               x=box[0], y=box[1], w=box[2], h=box[3])

    def _detect_minimap(self, frame, box, key) -> DetectedElement:
        """Corner square with moderate variance and edge structure."""
        samples = self._sample(frame, box)
        if len(samples) < 20:
            return self._miss(key, box)
        lums = [sum(s) / 3.0 for s in samples]
        mean = sum(lums) / len(lums)
        var = sum((v - mean) ** 2 for v in lums) / len(lums)
        std = math.sqrt(var)
        present = 10.0 < std < 110.0
        conf = max(0.0, min(0.85, 1.0 - abs(std - 50.0) / 90.0)) if present else 0.0
        return DetectedElement(key=key, present=present, confidence=round(conf, 2),
                               x=box[0], y=box[1], w=box[2], h=box[3])

    def _detect_digits(self, frame, box, key) -> DetectedElement:
        """High-variance band -> numeric readout (score/timer/speed/ammo)."""
        samples = self._sample(frame, box)
        if len(samples) < 20:
            return self._miss(key, box)
        lums = [sum(s) / 3.0 for s in samples]
        mean = sum(lums) / len(lums)
        var = sum((v - mean) ** 2 for v in lums) / len(lums)
        std = math.sqrt(var)
        present = std >= 12.0
        conf = max(0.0, min(0.95, (std - 8.0) / 60.0)) if present else 0.0
        return DetectedElement(key=key, present=present, confidence=round(conf, 2),
                               x=box[0], y=box[1], w=box[2], h=box[3])

    def _detect_grid(self, frame, box, key) -> DetectedElement:
        """Bottom-right inventory: brightness periodic structure (grid cells)."""
        samples = self._sample(frame, box)
        if len(samples) < 30:
            return self._miss(key, box)
        lums = [sum(s) / 3.0 for s in samples]
        mean = sum(lums) / len(lums)
        var = sum((v - mean) ** 2 for v in lums) / len(lums)
        std = math.sqrt(var)
        # grid has both dark and bright cells: bimodal-ish
        darks = sum(1 for v in lums if v < 60)
        brights = sum(1 for v in lums if v > 140)
        bimodal = min(darks, brights) / max(1, len(lums))
        present = std >= 18.0 and bimodal >= 0.05
        conf = max(0.0, min(0.9, (std / 70.0) * 0.6 + bimodal * 0.4)) if present else 0.0
        return DetectedElement(key=key, present=present, confidence=round(conf, 2),
                               x=box[0], y=box[1], w=box[2], h=box[3])

    def _detect_panel(self, frame, box, key) -> DetectedElement:
        """Broad uniform band with structure (resource/menu bars)."""
        samples = self._sample(frame, box)
        if len(samples) < 30:
            return self._miss(key, box)
        lums = [sum(s) / 3.0 for s in samples]
        mean = sum(lums) / len(lums)
        var = sum((v - mean) ** 2 for v in lums) / len(lums)
        std = math.sqrt(var)
        present = std < 50.0
        conf = max(0.0, min(0.85, (50.0 - std) / 50.0)) if present else 0.0
        return DetectedElement(key=key, present=present, confidence=round(conf, 2),
                               x=box[0], y=box[1], w=box[2], h=box[3])

    _DISPATCH = {
        "crosshair": _detect_crosshair,
        "bar": _detect_bar,
        "dialogue": _detect_dialogue,
        "marker": _detect_marker,
        "minimap": _detect_minimap,
        "digits": _detect_digits,
        "grid": _detect_grid,
        "panel": _detect_panel,
    }

    @staticmethod
    def _miss(key: str, box: tuple[int, int, int, int]) -> DetectedElement:
        return DetectedElement(key=key, present=False, confidence=0.0,
                                x=box[0], y=box[1], w=box[2], h=box[3])

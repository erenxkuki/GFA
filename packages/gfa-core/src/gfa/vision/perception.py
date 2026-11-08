"""Enhanced perception: detect UI regions, objects, and text blocks from frames."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from gfa.agent.perception import DetectedObject
from gfa.universal.capture import CapturedFrame


@dataclass
class UIRegion:
    label: str  # "health_bar", "minimap", "dialogue", "menu", "objective"
    x: int
    y: int
    w: int
    h: int
    confidence: float = 0.5
    text: str = ""


@dataclass
class PerceptionResult:
    objects: list[DetectedObject] = field(default_factory=list)
    ui_regions: list[UIRegion] = field(default_factory=list)
    text_blocks: list[str] = field(default_factory=list)
    compact_summary: str = ""
    frame_size: tuple[int, int] = (0, 0)


class VisionPerception:
    """Multi-layer perception: color objects + UI region detection + compact state.

    Designed to reduce token usage by producing a compact text description
    instead of (or in addition to) full screenshots.
    """

    def __init__(self, color_map: dict[str, tuple[int, int, int]] | None = None, tolerance: int = 40):
        from gfa.agent.perception import ColorBlobPerception
        self.color_detector = ColorBlobPerception(color_map=color_map, tolerance=tolerance)
        self._prev_objects: list[DetectedObject] = []

    def analyze(self, frame: CapturedFrame) -> PerceptionResult:
        objects = self.color_detector.analyze(frame)
        ui_regions = self._detect_ui_regions(frame)
        text_blocks = self._detect_text_regions(frame)
        changes = self._compute_changes(objects)
        summary = self._build_compact_summary(frame, objects, ui_regions, text_blocks, changes)
        self._prev_objects = objects
        return PerceptionResult(
            objects=objects, ui_regions=ui_regions, text_blocks=text_blocks,
            compact_summary=summary, frame_size=(frame.width, frame.height),
        )

    def _detect_ui_regions(self, frame: CapturedFrame) -> list[UIRegion]:
        """Heuristic UI region detection based on spatial layout.

        Top band: likely HUD/health/score. Bottom band: dialogue/subtitles.
        Corners: minimap. Center: gameplay.
        """
        w, h = frame.width, frame.height
        regions: list[UIRegion] = []
        # Top HUD band
        regions.append(UIRegion(label="top_hud", x=0, y=0, w=w, h=max(1, h // 8), confidence=0.6))
        # Bottom band (dialogue/subtitles)
        regions.append(UIRegion(label="bottom_bar", x=0, y=h - max(1, h // 6), w=w, h=max(1, h // 6), confidence=0.6))
        # Top-right minimap guess
        regions.append(UIRegion(label="minimap", x=w - max(1, w // 5), y=0, w=max(1, w // 5), h=max(1, h // 5), confidence=0.4))
        return regions

    def _detect_text_regions(self, frame: CapturedFrame) -> list[str]:
        """Use Windows OCR to extract text from the frame.

        OCR requires sufficient resolution; skip tiny frames.
        """
        if frame.width < 300 or frame.height < 200:
            return []
        try:
            from gfa.vision.ocr import WindowsOCR
            result = WindowsOCR.extract_from_frame(frame)
            lines = result.get("lines", [])
            text = result.get("text", "")
            if lines:
                return lines
            if text:
                return [text]
        except Exception:  # noqa: BLE001
            pass
        return []

    def _compute_changes(self, objects: list[DetectedObject]) -> list[str]:
        changes = []
        prev_map = {o.label: o for o in self._prev_objects}
        for o in objects:
            if o.label in prev_map:
                p = prev_map[o.label]
                dx = o.x - p.x
                dy = o.y - p.y
                if abs(dx) > 3 or abs(dy) > 3:
                    changes.append(f"{o.label} moved ({dx:+d},{dy:+d})")
            else:
                changes.append(f"{o.label} appeared at ({o.x},{o.y})")
        for label in prev_map:
            if label not in {o.label for o in objects}:
                changes.append(f"{label} disappeared")
        return changes

    def _build_compact_summary(self, frame, objects, ui_regions, text_blocks, changes) -> str:
        parts = [f"Frame {frame.width}x{frame.height}."]
        if objects:
            obj_str = ", ".join(f"{o.label}@({o.x},{o.y})" for o in objects)
            parts.append(f"Objects: {obj_str}.")
        if changes:
            parts.append("Changes: " + "; ".join(changes) + ".")
        if ui_regions:
            parts.append(f"UI regions: {', '.join(r.label for r in ui_regions)}.")
        # OCR text
        if text_blocks:
            ocr_text = " | ".join(text_blocks[:10])
            parts.append(f"Screen text: {ocr_text}.")
        return " ".join(parts)
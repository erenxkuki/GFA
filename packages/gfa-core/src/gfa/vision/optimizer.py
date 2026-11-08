"""Token optimization: reduce observation payload sent to the model."""

from __future__ import annotations

import base64
from dataclasses import dataclass
from typing import Any

from gfa.universal.capture import CapturedFrame


@dataclass
class ObservationMode:
    mode: str = "compact"  # "full", "compact", "hybrid"
    max_image_tokens: int = 0  # 0 = no image
    include_diff: bool = True
    downscale: float = 0.25


class TokenOptimizer:
    """Converts a frame + perception result into an optimized model payload.

    Modes:
    - compact: text-only summary (lowest tokens)
    - full: full screenshot (highest tokens)
    - hybrid: compact text + small thumbnail (balanced)
    """

    def __init__(self, mode: str = "compact", downscale: float = 0.25):
        self.mode = mode
        self.downscale = downscale

    def build_payload(self, frame: CapturedFrame, compact_summary: str, perception_result: Any = None) -> dict[str, Any]:
        payload: dict[str, Any] = {"text": compact_summary}
        if self.mode == "full":
            payload["image_base64"] = frame.to_base64() if hasattr(frame, "to_base64") else None
            payload["image_size"] = (frame.width, frame.height)
        elif self.mode == "hybrid":
            # downscale frame
            from gfa.universal.capture import capture_screen
            small = capture_screen(0, 0, frame.width, frame.height, scale=self.downscale) if False else None
            # Use frame's png but note downscale in metadata; actual downscale done at capture time
            payload["image_base64"] = frame.to_base64()
            payload["image_size"] = (frame.width, frame.height)
            payload["note"] = f"downscaled capture recommended at {self.downscale}x"
        # compact: text only
        return payload

    @staticmethod
    def estimate_tokens(text: str, has_image: bool = False) -> int:
        # Rough estimate: 1 token ~ 4 chars; image ~ 85 tokens for small thumbnail
        toks = len(text) // 4
        if has_image:
            toks += 85
        return toks

    @staticmethod
    def frame_diff_summary(prev_summary: str, curr_summary: str) -> str:
        if prev_summary == curr_summary:
            return "No change since last frame."
        return curr_summary
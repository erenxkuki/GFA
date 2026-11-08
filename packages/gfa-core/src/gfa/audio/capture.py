"""Audio capture primitives: frames and the source interface."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass
class AudioFrame:
    """A chunk of mono audio samples (normalized to roughly -1.0..1.0)."""

    samples: list[float]
    sample_rate: int = 44100
    source: str = "loopback"  # "loopback" (game output) | "mic"


class AudioSource(Protocol):
    """Audio input source: reads chunks of PCM frames."""

    def read(self) -> list[AudioFrame]: ...

    def close(self) -> None: ...

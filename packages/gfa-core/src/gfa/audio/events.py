"""Audio event model and cooldown buffer."""

from __future__ import annotations

from collections import deque
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any


@dataclass
class AudioEvent:
    """A classified sound event detected in the audio stream."""

    category: str
    confidence: float
    timestamp: float
    duration_ms: float
    peak: float
    source: str = "loopback"

    def to_dict(self) -> dict[str, Any]:
        return {
            "category": self.category,
            "confidence": round(self.confidence, 3),
            "timestamp": round(self.timestamp, 3),
            "duration_ms": round(self.duration_ms, 1),
            "peak": round(self.peak, 3),
            "source": self.source,
        }

    def __str__(self) -> str:
        return f"[{self.category} c={self.confidence:.2f}]"


class AudioEventBuffer:
    """Rolling buffer of audio events with per-category cooldown."""

    def __init__(self, cooldown_ms: float = 250.0, max_events: int = 50):
        self.cooldown_ms = cooldown_ms
        self.max_events = max_events
        self._events: deque[AudioEvent] = deque(maxlen=max_events)
        self._last_seen: dict[str, float] = {}

    def add(self, events: Iterable[AudioEvent]) -> list[AudioEvent]:
        """Add new events, dropping repeats that fall within the cooldown window."""
        accepted: list[AudioEvent] = []
        if not events:
            return accepted
        now = max((e.timestamp for e in events), default=0.0)
        for e in events:
            last = self._last_seen.get(e.category, 0.0)
            if (now - last) * 1000.0 < self.cooldown_ms:
                continue
            self._last_seen[e.category] = now
            self._events.append(e)
            accepted.append(e)
        return accepted

    def recent(self, limit: int = 10) -> list[AudioEvent]:
        if not self._events:
            return []
        return list(self._events)[-limit:] if limit else list(self._events)

    def clear(self) -> None:
        self._events.clear()
        self._last_seen.clear()

    @staticmethod
    def summarize(events: list[AudioEvent], limit: int = 8) -> str:
        """Human/LLM-readable summary of a batch of events, e.g. 'gunshot x1, footsteps x1'."""
        if not events:
            return "audio: quiet"
        counts: dict[str, int] = {}
        for e in events:
            counts[e.category] = counts.get(e.category, 0) + 1
        ordered = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
        return "audio: " + ", ".join(f"{cat} x{n}" for cat, n in ordered)

    def summary(self, limit: int = 8) -> str:
        return self.summarize(self.recent(limit), limit)

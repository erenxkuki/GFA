"""Audio perception facade: frames -> events -> summaries."""

from __future__ import annotations

from typing import Any

from gfa.audio.analyzer import AudioClassifier
from gfa.audio.capture import AudioFrame
from gfa.audio.events import AudioEvent, AudioEventBuffer


class AudioPerceptionResult:
    """Result of analyzing a batch of audio frames."""

    def __init__(self, events: list[AudioEvent], summary: str):
        self.events = events
        self.summary = summary

    def to_dict(self) -> dict[str, Any]:
        return {"events": [e.to_dict() for e in self.events], "summary": self.summary}


class AudioPerception:
    """Turns raw audio frames into classified events and summaries."""

    def __init__(self, classifier: AudioClassifier | None = None):
        self.classifier = classifier or AudioClassifier()

    def analyze(self, frames: list[AudioFrame] | None, source: str = "loopback") -> AudioPerceptionResult:
        events = self.classifier.analyze(list(frames or []), source=source)
        return AudioPerceptionResult(events=events, summary=AudioEventBuffer.summarize(events))

    @staticmethod
    def summarize(events: list[AudioEvent], limit: int = 8) -> str:
        return AudioEventBuffer.summarize(events, limit=limit)


class AudioMonitor:
    """Feeds audio frames through the classifier and keeps an event buffer.

    Intended lifecycle: source.read() -> frames -> monitor.feed(frames) ->
    monitor.poll() returns newly accepted events (for world state / reasoning).
    """

    def __init__(self, source: Any = None, classifier: AudioClassifier | None = None, cooldown_ms: float = 250.0, max_events: int = 50):
        self.source = source
        self.classifier = classifier or AudioClassifier()
        self.cooldown_ms = cooldown_ms
        self.buffer = AudioEventBuffer(cooldown_ms=cooldown_ms, max_events=max_events)
        self._pending: list[AudioEvent] = []

    def feed(self, frames: list[AudioFrame] | None, source: str = "loopback") -> AudioPerceptionResult:
        result = AudioPerception(self.classifier).analyze(frames, source=source)
        accepted = self.buffer.add(result.events)
        self._pending = accepted
        return AudioPerceptionResult(events=accepted, summary=self.buffer.summary())

    def poll(self) -> list[AudioEvent]:
        """Read frames from the source (if set), analyze them, return new accepted events."""
        if self.source is None:
            return []
        frames = self.source.read()
        return self.feed(frames).events

    def summary(self) -> str:
        return self.buffer.summary()

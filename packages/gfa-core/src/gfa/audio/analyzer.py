"""Audio classification: detect sound events from mono PCM frames.

Heuristic event detection from raw PCM samples:
- Energy-based segmentation (silence vs active sound)
- Per-event features: duration, peak, RMS, zero-crossing rate
- Template classification into gameplay-relevant categories

This is the "hearing" layer of GFA: turn raw audio into concise events
the model can act on (gunshot, explosion, footsteps, music, voice, ...).
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass

from gfa.audio.capture import AudioFrame
from gfa.audio.events import AudioEvent

DEFAULT_SAMPLE_RATE = 44100
SILENCE_RMS_THRESHOLD = 0.005


@dataclass
class AudioFeatures:
    duration_ms: float
    peak: float
    rms: float
    zcr: float


class AudioClassifier:
    """Classifies audio frames into gameplay sound events.

    Detection rules (duration/peak/rms/zcr heuristics):
    - gunshots: very loud (<=60ms impulsive bursts)
    - explosions: loud bursts (60-900ms)
    - voice: broadband signals (high zero-crossing rate)
    - alerts: short tonal dings (<=250ms)
    - music: sustained energy (>=450ms)
    - footsteps: short low-amplitude impacts (<120ms)
    - sfx: fallback
    """

    def __init__(self, sample_rate: int = DEFAULT_SAMPLE_RATE, silence_rms: float = SILENCE_RMS_THRESHOLD):
        self.sample_rate = sample_rate
        self.silence_rms = silence_rms

    def analyze(self, frames: list[AudioFrame] | None, source: str = "loopback") -> list[AudioEvent]:
        events: list[AudioEvent] = []
        for frame in frames or []:
            feats = self.features(frame)
            if feats is None:
                continue
            outcome = self.classify(feats)
            if outcome is None:
                continue
            category, confidence = outcome
            events.append(AudioEvent(
                category=category,
                confidence=confidence,
                timestamp=time.monotonic(),
                duration_ms=feats.duration_ms,
                peak=feats.peak,
                source=frame.source or source,
            ))
        return events

    def features(self, frame: AudioFrame) -> AudioFeatures | None:
        samples = frame.samples
        if not samples:
            return None
        n = len(samples)
        peak = max(abs(s) for s in samples)
        if peak < self.silence_rms:
            return None  # digital silence
        rms = math.sqrt(sum(s * s for s in samples) / n)
        if rms < self.silence_rms:
            return None  # silence
        duration_ms = n / max(1, frame.sample_rate) * 1000.0
        return AudioFeatures(duration_ms=duration_ms, peak=peak, rms=rms, zcr=self._zero_crossing_rate(samples))

    def classify(self, feats: AudioFeatures) -> tuple[str, float] | None:
        if feats.rms < self.silence_rms or feats.peak < self.silence_rms:
            return None
        if feats.duration_ms <= 60.0 and feats.peak >= 0.35:
            return "gunshot", min(0.99, 0.25 + feats.peak * 0.8)
        if 60.0 < feats.duration_ms <= 900.0 and feats.peak >= 0.65:
            return "explosion", min(0.95, 0.25 + feats.peak * 0.8)
        if feats.zcr >= 0.08 and feats.duration_ms <= 800.0:
            return "voice", min(0.85, 0.2 + feats.zcr * 10.0)
        if feats.duration_ms <= 250.0 and feats.peak >= 0.5 and feats.zcr < 0.08:
            return "alert", min(0.9, 0.3 + feats.peak)
        if feats.duration_ms >= 450.0 and feats.rms >= 0.01:
            return "music", min(0.85, 0.3 + feats.rms * 3.0)
        if feats.duration_ms < 120.0 and feats.peak < 0.45 and feats.rms < 0.25:
            return "footstep", min(0.8, 0.2 + feats.peak * 2.0)
        return "sfx", min(0.75, 0.2 + feats.peak)

    @staticmethod
    def _zero_crossing_rate(samples: list[float]) -> float:
        if len(samples) < 2:
            return 0.0
        crossings = 0
        for i in range(1, len(samples)):
            if (samples[i - 1] >= 0) != (samples[i] >= 0):
                crossings += 1
        return crossings / (len(samples) - 1)

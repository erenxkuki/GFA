import asyncio
import math
from unittest.mock import MagicMock

from gfa.agent.agent import GameplayAgent
from gfa.agent.reasoning import ReasoningCoordinator
from gfa.audio.analyzer import AudioClassifier
from gfa.audio.capture import AudioFrame
from gfa.audio.events import AudioEvent, AudioEventBuffer
from gfa.audio.perception import AudioMonitor, AudioPerception
from gfa.universal.capture import CapturedFrame


def _burst(peak: float = 0.9, seconds: float = 0.03, sample_rate: int = 44100, decay: float = 0.98) -> list[float]:
    n = max(1, int(seconds * sample_rate))
    return [peak * (decay ** i) for i in range(n)]


def _tone(peak: float = 0.3, freq: float = 440.0, seconds: float = 0.5, sample_rate: int = 44100) -> list[float]:
    n = max(1, int(seconds * sample_rate))
    return [peak * math.sin(2 * math.pi * freq * i / sample_rate) for i in range(n)]


def _noise(peak: float = 0.5, seconds: float = 0.15, sample_rate: int = 44100) -> list[float]:
    n = max(1, int(seconds * sample_rate))
    return [peak if (i // 4) % 2 == 0 else -peak for i in range(n)]


def _silence(seconds: float = 0.2, sample_rate: int = 44100) -> list[float]:
    n = max(1, int(seconds * sample_rate))
    return [0.0] * n


def test_classifier_detects_gunshot():
    events = AudioClassifier().analyze([AudioFrame(samples=_burst(0.9, 0.03))], source="loopback")
    assert len(events) == 1
    assert events[0].category == "gunshot"
    assert events[0].confidence > 0.5
    assert events[0].source == "loopback"


def test_classifier_detects_explosion():
    events = AudioClassifier().analyze([AudioFrame(samples=_burst(0.95, 0.2))], source="loopback")
    assert len(events) == 1
    assert events[0].category == "explosion"


def test_classifier_detects_music():
    events = AudioClassifier().analyze([AudioFrame(samples=_tone(0.3, 440.0, 0.5))], source="loopback")
    assert len(events) == 1
    assert events[0].category == "music"


def test_classifier_detects_voice():
    events = AudioClassifier().analyze([AudioFrame(samples=_noise(0.5, 0.15), source="mic")], source="mic")
    assert len(events) == 1
    assert events[0].category == "voice"
    assert events[0].source == "mic"


def test_classifier_detects_footstep():
    events = AudioClassifier().analyze([AudioFrame(samples=_tone(0.25, 80.0, 0.06))], source="loopback")
    assert len(events) == 1
    assert events[0].category == "footstep"


def test_classifier_detects_alert():
    events = AudioClassifier().analyze([AudioFrame(samples=_tone(0.6, 880.0, 0.1))], source="loopback")
    assert len(events) == 1
    assert events[0].category == "alert"


def test_classifier_ignores_silence():
    events = AudioClassifier().analyze([AudioFrame(samples=_silence())], source="loopback")
    assert events == []


def test_classifier_no_frames():
    assert AudioClassifier().analyze([], source="loopback") == []


def test_event_buffer_cooldown():
    buf = AudioEventBuffer(cooldown_ms=250.0)
    e1 = AudioEvent("gunshot", 0.9, 100.0, 30.0, 0.9)
    e2 = AudioEvent("gunshot", 0.8, 150.0, 30.0, 0.8)  # within cooldown -> dropped
    accepted = buf.add([e1, e2])
    assert len(accepted) == 1
    e3 = AudioEvent("footstep", 0.6, 400.0, 60.0, 0.2)
    accepted = buf.add([e3])
    assert len(accepted) == 1
    assert buf.recent(5)[0].category == "gunshot"


def test_event_buffer_summary():
    events = [
        AudioEvent("gunshot", 0.9, 100.0, 30.0, 0.9),
        AudioEvent("gunshot", 0.8, 120.0, 30.0, 0.8),
        AudioEvent("footstep", 0.6, 130.0, 60.0, 0.2),
    ]
    assert AudioEventBuffer.summarize(events) == "audio: gunshot x2, footstep x1"
    assert AudioEventBuffer.summarize([]) == "audio: quiet"


def test_monitor_feed_poll_summary():
    class FakeSource:
        def __init__(self, frames):
            self.frames = frames
            self.closed = False

        def read(self):
            return self.frames

        def close(self):
            self.closed = True

    frames = [AudioFrame(samples=_burst(0.9, 0.03))]
    mon = AudioMonitor(source=FakeSource(frames), cooldown_ms=250.0)

    # poll reads from source, analyzes, applies cooldown, returns accepted events
    polled = mon.poll()
    assert len(polled) == 1
    assert polled[0].category == "gunshot"
    assert "gunshot" in mon.summary()
    # second poll -> cooldown suppresses the repeat gunshot
    assert mon.poll() == []


def test_audio_perception_analyze():
    p = AudioPerception()
    result = p.analyze([AudioFrame(samples=_tone(0.3, 440.0, 0.5))], source="loopback")
    assert len(result.events) == 1
    assert result.events[0].category == "music"
    assert result.summary.startswith("audio:")


def test_agent_includes_audio_in_world_state():
    async def run():
        baseline = MagicMock()
        baseline.observe.return_value = CapturedFrame(width=1920, height=1080, png_bytes=b"x")
        baseline.capabilities.return_value = MagicMock()
        baseline.register_gcl_handlers = MagicMock()

        class FakeSource:
            def read(self):
                return [AudioFrame(samples=_burst(0.9, 0.03))]

            def close(self):
                pass

        reasoning = ReasoningCoordinator(fallback_policy=lambda ws: [{"type": "wait", "duration_ms": 1}])
        monitor = AudioMonitor(source=FakeSource(), cooldown_ms=250.0)
        agent = GameplayAgent(baseline=baseline, reasoning=reasoning, audio_monitor=monitor, max_steps=1, step_delay=0.0)

        captured_ws = {}

        def fb(ws):
            captured_ws["ws"] = ws
            return [{"type": "wait", "duration_ms": 1}]

        reasoning.fallback_policy = fb
        await agent.run("test objective", game="test_game")
        ws = captured_ws["ws"]
        assert "Audio: gunshot" in ws.observation_summary
    asyncio.run(run())


def test_agent_without_audio_monitor():
    async def run():
        baseline = MagicMock()
        baseline.observe.return_value = CapturedFrame(width=1920, height=1080, png_bytes=b"x")
        baseline.capabilities.return_value = MagicMock()
        baseline.register_gcl_handlers = MagicMock()
        reasoning = ReasoningCoordinator(fallback_policy=lambda ws: [{"type": "wait", "duration_ms": 1}])
        agent = GameplayAgent(baseline=baseline, reasoning=reasoning, max_steps=1, step_delay=0.0)
        captured_ws = {}

        def fb(ws):
            captured_ws["ws"] = ws
            return [{"type": "wait", "duration_ms": 1}]

        reasoning.fallback_policy = fb
        await agent.run("test objective", game="test_game")
        assert "Audio:" not in captured_ws["ws"].observation_summary
    asyncio.run(run())

"""Tests for genre-specific HUD detectors using synthetic BGRA frames."""

import asyncio

from gfa.agent.agent import GameplayAgent
from gfa.agent.reasoning import ReasoningCoordinator
from gfa.genre import GenreDetector, get_genre, list_genres, select_genre_for_keywords
from gfa.universal.capture import CapturedFrame


def _frame(w: int, h: int, painter) -> CapturedFrame:
    """Build a frame (mid-gray background) then paint pixels via painter(set_px)."""
    raw = bytearray(bytes([90, 90, 90, 255]))  # BGRA gray, opaque
    raw = raw * (w * h)

    def set_px(x, y, r, g, b):
        i = (y * w + x) * 4
        raw[i], raw[i + 1], raw[i + 2], raw[i + 3] = b, g, r, 255

    painter(set_px)
    return CapturedFrame(width=w, height=h, png_bytes=b"x", raw_bgra=bytes(raw))


def _blank(paint):
    pass


def test_genre_profiles():
    assert set(list_genres()) == {"fps", "rpg", "platformer", "racing", "strategy"}
    fps = get_genre("fps")
    names = [e.name for e in fps.elements]
    assert "crosshair" in names and "health_bar" in names
    assert select_genre_for_keywords(["shooter"]) == "fps"
    assert select_genre_for_keywords(["quest", "rpg"]) == "rpg"
    assert select_genre_for_keywords(["nothing"]) is None


def test_detect_on_blank_frame():
    frame = _frame(320, 240, _blank)
    det = GenreDetector("fps")
    els = det.detect(frame)
    assert len(els) == len(get_genre("fps").elements)
    # blank frame: nothing should be confidently present
    assert all(e.confidence < 0.6 for e in els)


def test_crosshair_detection():
    def paint(set_px):
        # bright white cross at center (160, 120)
        for x in range(150, 171):
            set_px(x, 120, 255, 255, 255)
        for y in range(111, 130):
            set_px(160, y, 255, 255, 255)

    frame = _frame(320, 240, paint)
    det = GenreDetector("fps", sample_step=1)
    els = {e.key: e for e in det.detect(frame)}
    ch = els["crosshair"]
    assert ch.present is True
    assert ch.confidence >= 0.3


def test_health_bar_green_detected():
    def paint(set_px):
        # green bar: top-left wide strip
        for y in range(5, 15):
            for x in range(20, 120):
                set_px(x, y, 60, 200, 60)

    frame = _frame(320, 240, paint)
    det = GenreDetector("fps", sample_step=2)
    els = {e.key: e for e in det.detect(frame)}
    hb = els["health_bar"]
    assert hb.present is True
    assert hb.value.endswith("%")  # fill estimate


def test_health_bar_red_is_low():
    def paint(set_px):
        # mostly red bar -> low health
        for y in range(5, 15):
            for x in range(20, 120):
                set_px(x, y, 220, 40, 40)

    frame = _frame(320, 240, paint)
    det = GenreDetector("fps", sample_step=2)
    hb = {e.key: e for e in det.detect(frame)}["health_bar"]
    assert hb.present is True
    assert "low" in hb.value


def test_dialogue_box_detection():
    def paint(set_px):
        # uniformly dark bottom band
        for y in range(210, 240):
            for x in range(0, 320):
                set_px(x, y, 30, 30, 30)

    frame = _frame(320, 240, paint)
    det = GenreDetector("rpg", sample_step=2)
    els = {e.key: e for e in det.detect(frame)}
    assert els["dialogue_box"].present is True


def test_summary_text():
    def paint(set_px):
        for x in range(150, 171):
            set_px(x, 120, 255, 255, 255)
        for y in range(111, 130):
            set_px(160, y, 255, 255, 255)

    frame = _frame(320, 240, paint)
    det = GenreDetector("fps", sample_step=1)
    els = det.detect(frame)
    s = det.summary(els)
    assert "Genre HUD (fps)" in s


class DummyBaseline:
    def __init__(self, frame):
        self.frame = frame

    def observe(self):
        return self.frame

    def capabilities(self):
        from gfa.gcl.capabilities import CapabilitySet

        return CapabilitySet.core_capabilities()

    def register_gcl_handlers(self, executor):
        async def wait_handler(cmd):
            return {"duration_ms": 1}

        executor.register_handler("wait", wait_handler)

    def emergency_stop(self):
        pass


def test_agent_includes_genre_hud():
    async def run():
        def paint(set_px):
            for x in range(150, 171):
                set_px(x, 120, 255, 255, 255)
            for y in range(111, 130):
                set_px(160, y, 255, 255, 255)
            for y in range(5, 15):
                for x in range(20, 120):
                    set_px(x, y, 60, 200, 60)

        baseline = DummyBaseline(_frame(320, 240, paint))
        reasoning = ReasoningCoordinator(fallback_policy=lambda ws: [{"type": "wait", "duration_ms": 1}])
        captured = {}

        def fb(ws):
            captured["ws"] = ws
            return [{"type": "wait", "duration_ms": 1}]

        reasoning.fallback_policy = fb
        agent = GameplayAgent(baseline=baseline, reasoning=reasoning, genre="fps",
                              max_steps=1, step_delay=0.0)
        result = await agent.run("win", game="TestGame")
        assert result.steps == 1
        ws = captured["ws"]
        assert "Genre HUD (fps)" in ws.observation_summary
        # detected elements also appear as visible objects
        labels = [o["label"] for o in ws.visible_objects]
        assert "crosshair" in labels
        assert "health_bar" in labels

    asyncio.run(run())


def test_agent_without_genre_still_works():
    async def run():
        baseline = DummyBaseline(_frame(100, 100, _blank))
        reasoning = ReasoningCoordinator(fallback_policy=lambda ws: [{"type": "wait", "duration_ms": 1}])
        captured = {}

        def fb(ws):
            captured["ws"] = ws
            return [{"type": "wait", "duration_ms": 1}]

        reasoning.fallback_policy = fb
        agent = GameplayAgent(baseline=baseline, reasoning=reasoning, max_steps=1, step_delay=0.0)
        result = await agent.run("win", game="TestGame")
        assert result.steps == 1
        assert "Genre HUD" not in captured["ws"].observation_summary

    asyncio.run(run())

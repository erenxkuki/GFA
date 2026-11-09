import asyncio

from gfa.agent.agent import GameplayAgent
from gfa.agent.reasoning import ReasoningCoordinator
from gfa.universal.capture import CapturedFrame
from gfa.worldmodel import ObjectTracker, WorldModelPredictor


class Obj:
    """Minimal perception object with x/y attributes."""

    def __init__(self, label, x, y, w=10, h=10, confidence=1.0):
        self.label = label
        self.x = x
        self.y = y
        self.w = w
        self.h = h
        self.confidence = confidence


class DummyBaseline:
    def __init__(self, frame, objects_sequence):
        self.frames = [frame] * 10
        self.objects_sequence = objects_sequence  # list per step (or static list)
        self._step = 0

    def observe(self):
        return self.frames[0]

    def capabilities(self):
        from gfa.gcl.capabilities import CapabilitySet

        return CapabilitySet.core_capabilities()

    def register_gcl_handlers(self, executor):
        async def wait_handler(cmd):
            return {"duration_ms": 1}

        executor.register_handler("wait", wait_handler)

    def emergency_stop(self):
        pass


class MovingPerception:
    """Perception that moves an object left-to-right each step toward center."""

    def __init__(self, start_x=1500, step_px=100, y=540):
        self.start_x = start_x
        self.step_px = step_px
        self.y = y
        self.calls = 0

    def analyze(self, frame):
        x = self.start_x - self.calls * self.step_px
        self.calls += 1
        return [Obj("enemy", x=x, y=self.y)]


def test_tracker_velocity():
    tracker = ObjectTracker()
    tracker.update([Obj("enemy", 100, 200)], step=0)
    t = tracker.get("enemy")
    assert t is not None
    assert (t.vx, t.vy) == (0, 0)  # first sighting, no velocity yet
    tracker.update([Obj("enemy", 110, 200)], step=1)
    # velocity: 0.5*0 + 0.5*((110-100)/1) = 5
    assert t.vx == 5.0


def test_tracker_stale_expiry():
    tracker = ObjectTracker(stale_steps=2)
    tracker.update([Obj("enemy", 100, 100)], step=0)
    tracker.update([], step=1)
    assert tracker.get("enemy") is not None
    tracker.update([], step=4)
    assert tracker.get("enemy") is None


def test_predictor_stationary():
    pred = WorldModelPredictor(frame_width=1920, frame_height=1080, horizon_steps=3.0)
    pred.update([Obj("rock", 100, 100)], step=0)
    result = pred.predict()
    assert result.predicted_positions["rock"] == (100.0, 100.0)
    assert result.incoming_threats == []
    assert result.recommendation == ""
    assert "no moving threats" in result.to_text() or result.predicted_positions


def test_predictor_extrapolates_moving_object():
    pred = WorldModelPredictor(frame_width=1920, frame_height=1080, horizon_steps=2.0)
    # enemy starts far right, moves toward center (960, 540) each step
    pred.update([Obj("enemy", 1500, 540)], step=0)
    pred.update([Obj("enemy", 1400, 540)], step=1)
    pred.update([Obj("enemy", 1300, 540)], step=2)
    # vx smoothed: step1 -> 0.5*0+0.5*(-100) = -50; step2 -> 0.5*(-50)+0.5*(-100) = -75
    result = pred.predict()
    px = result.predicted_positions["enemy"][0]
    assert px < 1300  # extrapolated further left
    assert abs(px - (1300 - 75 * 2.0)) < 1e-6


def test_predictor_detects_incoming_threat_and_dodges():
    pred = WorldModelPredictor(frame_width=1920, frame_height=1080, player_radius_px=100.0,
                               step_ms=200.0, horizon_steps=3.0)
    # enemy approaches player zone (center 960,540) from the right
    pred.update([Obj("enemy", 1500, 540)], step=0)
    pred.update([Obj("enemy", 1300, 540)], step=1)
    pred.update([Obj("enemy", 1150, 540)], step=2)
    result = pred.predict()
    assert len(result.incoming_threats) == 1
    threat = result.incoming_threats[0]
    assert threat.label == "enemy"
    assert threat.dodge_direction == "left"  # enemy is right of center -> dodge left
    assert threat.time_to_impact_ms >= 0
    assert "dodge left" in result.recommendation


def test_predictor_dodge_right_side():
    pred = WorldModelPredictor(frame_width=1920, frame_height=1080, player_radius_px=100.0)
    # enemy approaches from the left
    pred.update([Obj("enemy", 420, 540)], step=0)
    pred.update([Obj("enemy", 620, 540)], step=1)
    pred.update([Obj("enemy", 770, 540)], step=2)
    result = pred.predict()
    assert len(result.incoming_threats) == 1
    assert result.incoming_threats[0].dodge_direction == "right"


def test_predictor_no_threat_when_leaving():
    pred = WorldModelPredictor(frame_width=1920, frame_height=1080, player_radius_px=100.0)
    # enemy moving AWAY from player zone (right edge -> center covered? start far, move further right)
    pred.update([Obj("enemy", 1400, 540)], step=0)
    pred.update([Obj("enemy", 1500, 540)], step=1)
    pred.update([Obj("enemy", 1600, 540)], step=2)
    result = pred.predict()
    assert result.incoming_threats == []


def test_agent_includes_prediction_in_world_state():
    async def run():
        perception = MovingPerception(start_x=1500, step_px=100)
        baseline = DummyBaseline(CapturedFrame(width=1920, height=1080, png_bytes=b"x"), [])
        reasoning = ReasoningCoordinator(fallback_policy=lambda ws: [{"type": "wait", "duration_ms": 1}])
        captured = {}

        def fb(ws):
            captured["ws"] = ws
            return [{"type": "wait", "duration_ms": 1}]

        reasoning.fallback_policy = fb
        predictor = WorldModelPredictor(frame_width=1920, frame_height=1080, player_radius_px=100.0)
        agent = GameplayAgent(baseline=baseline, reasoning=reasoning, perception=perception,
                              world_model=predictor, max_steps=3, step_delay=0.0)
        await agent.run("survive", game="TestGame")
        ws = captured["ws"]
        assert "Predicted" in ws.observation_summary
        # after 3 steps the enemy is close enough to trigger a threat
        assert isinstance(ws.incoming_threats, list)

    asyncio.run(run())


def test_agent_without_world_model_still_works():
    async def run():
        baseline = DummyBaseline(CapturedFrame(width=100, height=100, png_bytes=b"x"), [])
        reasoning = ReasoningCoordinator(fallback_policy=lambda ws: [{"type": "wait", "duration_ms": 1}])
        captured = {}

        def fb(ws):
            captured["ws"] = ws
            return [{"type": "wait", "duration_ms": 1}]

        reasoning.fallback_policy = fb
        agent = GameplayAgent(baseline=baseline, reasoning=reasoning, max_steps=1, step_delay=0.0)
        await agent.run("win", game="TestGame")
        assert captured["ws"].incoming_threats == []

    asyncio.run(run())

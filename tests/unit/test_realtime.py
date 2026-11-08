import asyncio

from gfa.agent.agent import GameplayAgent
from gfa.agent.reasoning import ReasoningCoordinator
from gfa.agent.world_state import WorldState
from gfa.realtime.agent import RealtimeAgent, RealtimeConfig
from gfa.realtime.profiles import GENRE_PROFILES
from gfa.realtime.tracking import MotionTracker
from gfa.realtime.aiming import AimAssist, AimTarget
from gfa.realtime.steering import SteeringController
from gfa.universal.baseline import BaselineConfig, UniversalBaseline


def test_genre_profiles():
    assert "shooter" in GENRE_PROFILES
    assert "racing" in GENRE_PROFILES
    assert GENRE_PROFILES["shooter"].target_fps == 30
    assert GENRE_PROFILES["racing"].input_smoothing is True


def test_motion_tracker_prediction():
    mt = MotionTracker(lookahead=0.1)
    mt.update("enemy", 100, 100)
    mt.update("enemy", 120, 100)
    mt.update("enemy", 140, 100)
    pos = mt.predict("enemy")
    assert pos is not None
    assert pos[0] > 140  # predicted forward


def test_aim_assist_select_target():
    aim = AimAssist(fov=200)
    targets = [AimTarget(100, 100, "enemy", 1), AimTarget(500, 500, "enemy", 1)]
    t = aim.select_target(targets, (90, 90))
    assert t is not None
    assert t.x == 100


def test_steering():
    sc = SteeringController(deadzone=0.1, smoothing=0.0)
    val = sc.compute(0.5, current_speed=0.5)
    assert -1.0 <= val <= 1.0
    keys = sc.to_key_presses(val)
    assert isinstance(keys, list)


def test_realtime_agent_construction():
    bl = UniversalBaseline(BaselineConfig(capture_scale=0.4))
    reasoning = ReasoningCoordinator(fallback_policy=lambda ws: [])
    agent = GameplayAgent(baseline=bl, reasoning=reasoning, max_steps=5, step_delay=0.033)
    cfg = RealtimeConfig(genre="shooter", duration_seconds=1.0)
    rta = RealtimeAgent(agent, cfg)
    assert rta.config.profile.name == "shooter"
    assert rta.tracker is not None
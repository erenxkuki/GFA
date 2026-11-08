import asyncio

from gfa.agent.agent import GameplayAgent
from gfa.agent.reasoning import ReasoningCoordinator
from gfa.agent.world_state import WorldState
from gfa.fast.engine import FastActionEngine, ReflexLayer, ReflexRule, FAST_PROFILE
from gfa.universal.baseline import BaselineConfig, UniversalBaseline


def test_reflex_layer():
    rl = ReflexLayer()
    rl.add_rule(ReflexRule(
        name="always_wait",
        condition=lambda ws: True,
        commands=lambda ws: [{"type": "wait", "duration_ms": 1}],
        priority=10,
    ))
    ws = WorldState()
    cmds = rl.evaluate(ws)
    assert cmds is not None and cmds[0]["type"] == "wait"


def test_fast_engine_profile_applied():
    bl = UniversalBaseline(BaselineConfig(capture_scale=0.5))
    reasoning = ReasoningCoordinator(fallback_policy=lambda ws: [{"type": "wait", "duration_ms": 1}])
    agent = GameplayAgent(baseline=bl, reasoning=reasoning, max_steps=2, step_delay=0.5)
    engine = FastActionEngine(agent, profile=FAST_PROFILE)
    assert agent.step_delay == 0.05
    assert bl.config.capture_scale == 0.35


def test_fast_engine_runs():
    async def run():
        bl = UniversalBaseline(BaselineConfig(capture_scale=0.35))
        reasoning = ReasoningCoordinator(fallback_policy=lambda ws: [{"type": "wait", "duration_ms": 1}])
        agent = GameplayAgent(baseline=bl, reasoning=reasoning, max_steps=2, step_delay=0.05)
        engine = FastActionEngine(agent, profile=FAST_PROFILE)
        # Can't actually run without a window; just ensure construction
        assert engine.profile.name == "fast"
    asyncio.run(run())
import asyncio

from gfa.agent.agent import GameplayAgent
from gfa.agent.reasoning import ReasoningCoordinator
from gfa.rl import RewardExtractor, RewardLedger, RewardTracker, StrategyScorer, command_signature
from gfa.universal.capture import CapturedFrame
from gfa.vision.perception import PerceptionResult


def test_command_signature():
    assert command_signature([{"type": "wait"}]) == "wait"
    assert command_signature([{"type": "combo", "name": "dodge_left"}, {"type": "move", "direction": "right"}]) == "combo:dodge_left,move:right"
    assert command_signature([]) == "noop"
    assert command_signature({"type": "click"}) == "click"


def test_extractor_parses_metrics():
    m = RewardExtractor.parse_metrics("Score: 1,200 | Health 85 | progress 42.5%")
    assert m == {"score": 1200.0, "health": 85.0, "progress": 42.5}
    assert RewardExtractor.parse_metrics("nothing here") == {}
    assert RewardExtractor.parse_metrics("") == {}


def test_extractor_computes_delta_reward():
    ext = RewardExtractor()
    first = ext.observe("Score: 100 Health: 80 progress: 10%", step=0)
    assert first.reward == 0.0  # baseline
    assert first.score == 100
    second = ext.observe("Score: 150 Health: 75 progress: 12%", step=1)
    # dScore=+50*1.0, dProgress=+2*2.0, dHealth=-5*1.0 -> 50+4-5 = 49
    assert second.reward == 49.0
    # losing score/health gives negative reward
    third = ext.observe("Score: 120 Health: 70 progress: 12%", step=2)
    # dScore=-30, dHealth=-5 -> -35
    assert third.reward == -35.0


def test_ledger_persists_and_stats(tmp_path):
    ledger = RewardLedger(tmp_path, game="ZZZ")
    assert ledger.load() == 0
    from gfa.rl.rewards import RewardSignal

    ledger.record(RewardSignal(game="ZZZ", step=0, score=100, reward=0.0), commands=[{"type": "wait"}])
    ledger.record(RewardSignal(game="ZZZ", step=1, score=150, reward=50.0), commands=[{"type": "move"}])
    st = ledger.stats()
    assert st["count"] == 2
    assert st["total"] == 50.0
    assert st["mean"] == 25.0
    assert st["best"] == 50.0
    assert "mean" in ledger.trend()

    # reload from disk in a new instance
    ledger2 = RewardLedger(tmp_path, game="ZZZ")
    assert ledger2.load() == 2
    assert ledger2.stats()["count"] == 2
    recents = ledger2.recent(1)
    assert len(recents) == 1 and recents[0].reward == 50.0


def test_scorer_ranks_actions():
    scorer = StrategyScorer()
    scorer.update("wait", 0.0)
    scorer.update("combo:dodge_left", 10.0)
    scorer.update("combo:dodge_left", 20.0)
    scorer.update("move:right", 5.0)
    assert scorer.count("combo:dodge_left") == 2
    assert scorer.average("combo:dodge_left") == 15.0
    ranked = scorer.ranked()
    assert ranked[0][0] == "combo:dodge_left"
    assert scorer.best(1) == ["combo:dodge_left"]
    assert "combo:dodge_left" in scorer.best_hint()


def test_tracker_facade(tmp_path):
    tracker = RewardTracker(data_dir=tmp_path, game="G")
    tracker.observe("Score: 100", step=0)
    tracker.score_action([{"type": "wait"}])
    tracker.observe("Score: 130", step=1)
    tracker.score_action([{"type": "move"}])
    assert tracker.scorer_best == ["move", "wait"]
    ctx = tracker.reward_context()
    assert "Reward:" in ctx
    assert "Best recent action" in ctx
    st = tracker.ledger.stats()
    assert st["count"] == 2


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


class ScorePerception:
    """Perception that reports an increasing score each step."""

    def __init__(self):
        self.calls = 0

    def analyze(self, frame):
        self.calls += 1
        result = PerceptionResult(objects=[], ui_regions=[], text_blocks=[],
                                  compact_summary=f"score {100 + (self.calls - 1) * 50}",
                                  frame_size=(frame.width, frame.height))
        return result


def test_agent_includes_reward_context(tmp_path):
    async def run():
        baseline = DummyBaseline(CapturedFrame(width=100, height=100, png_bytes=b"x"))
        reasoning = ReasoningCoordinator(fallback_policy=lambda ws: [{"type": "wait", "duration_ms": 1}])
        captured = {}

        def fb(ws):
            captured.setdefault("summaries", []).append(ws.observation_summary)
            captured["ws"] = ws
            return [{"type": "wait", "duration_ms": 1}]

        reasoning.fallback_policy = fb
        tracker = RewardTracker(data_dir=tmp_path, game="TestGame")
        agent = GameplayAgent(baseline=baseline, reasoning=reasoning, perception=ScorePerception(),
                              reward_tracker=tracker, max_steps=3, step_delay=0.0)
        await agent.run("win", game="TestGame")

        summaries = captured["summaries"]
        # step 0: reward baseline only; step 1+: reward deltas appear
        assert "Reward:" in captured["ws"].reward_summary
        assert "Reward:" in summaries[1]
        assert "score" in summaries[1]
        # scorer learned about "wait" from all steps
        assert tracker.scorer.count("wait") == 3
        assert tracker.ledger.stats()["count"] == 3

    asyncio.run(run())


def test_agent_without_reward_tracker_still_works(tmp_path):
    async def run():
        baseline = DummyBaseline(CapturedFrame(width=100, height=100, png_bytes=b"x"))
        reasoning = ReasoningCoordinator(fallback_policy=lambda ws: [{"type": "wait", "duration_ms": 1}])
        captured = {}

        def fb(ws):
            captured["ws"] = ws
            return [{"type": "wait", "duration_ms": 1}]

        reasoning.fallback_policy = fb
        agent = GameplayAgent(baseline=baseline, reasoning=reasoning, max_steps=1, step_delay=0.0)
        await agent.run("win", game="TestGame")
        assert captured["ws"].reward_summary == ""

    asyncio.run(run())

import asyncio
from unittest.mock import MagicMock

from gfa.agent.agent import GameplayAgent
from gfa.agent.reasoning import ReasoningCoordinator
from gfa.feedback import FeedbackInjector, FeedbackStore, LearningLoop
from gfa.universal.capture import CapturedFrame

PNG = b"\\x89PNG" + b"\\x00" * 16


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


def test_store_add_list_delete_clear(tmp_path):
    store = FeedbackStore(tmp_path)
    c = store.add("preference", "dodge when close", game="ZZZ")
    assert c.id.startswith("fb_")
    assert c.type == "preference"
    assert c.applied is False

    listed = store.list(game="ZZZ")
    assert len(listed) == 1 and listed[0].text == "dodge when close"
    assert len(store.pending()) == 1

    # add for another game; game-filtered list should only include ZZZ + generic
    store.add("avoid", "no left turns", game="Other")
    assert len(store.list(game="ZZZ")) == 1
    assert len(store.list()) == 2

    store.mark_applied([c.id])
    reloaded = store.list()
    c2 = [x for x in reloaded if x.id == c.id][0]
    assert c2.applied is True
    assert c2.applied_count == 1
    assert c2.applied_at is not None
    assert len(store.pending()) == 1  # only the "Other" one remains pending

    assert store.delete(c.id) is True
    assert store.delete("fb_missing") is False
    assert store.clear() == 1
    assert store.list() == []


def test_store_rejects_bad_type(tmp_path):
    store = FeedbackStore(tmp_path)
    import pytest

    with pytest.raises(ValueError):
        store.add("bogus", "text")


def test_injector_inject_and_consume(tmp_path):
    injector = FeedbackInjector(tmp_path)
    assert injector.inject() == ""  # nothing pending -> empty

    injector.add_correction("preference", "dodge when close", game="ZZZ")
    injector.add_correction("avoid", "no left", game="ZZZ")
    injector.add_correction("override", "global hint")  # generic (no game)

    text = injector.inject(game="ZZZ")
    assert "Human feedback:" in text
    assert "dodge when close" in text
    assert "no left" in text
    assert "global hint" in text
    assert injector.shown_count == 3

    applied = injector.consume_after_action()
    assert len(applied) == 3
    assert injector.shown_count == 0
    # now pending is empty
    assert injector.inject() == ""
    assert len(injector.store.pending()) == 0


def test_learning_loop_stores_verified_memory():
    mm = MagicMock()
    loop = LearningLoop(mm)
    from gfa.feedback.corrections import Correction

    loop.learn_from_correction(Correction(type="preference", text="dodge when close", game="ZZZ"))
    assert mm.add.called
    rec = mm.add.call_args[0][0]
    assert rec.category == "procedural"
    assert rec.memory_type == "verified"
    assert rec.verification_status == "verified"
    assert rec.confidence == 0.9
    assert "dodge when close" in rec.content
    assert rec.game_id == "ZZZ"
    assert "human-feedback" in rec.tags


def test_agent_includes_human_feedback(tmp_path):
    async def run():
        baseline = DummyBaseline(CapturedFrame(width=100, height=100, png_bytes=PNG))
        recording = []
        reasoning = ReasoningCoordinator(fallback_policy=lambda ws: [{"type": "wait", "duration_ms": 1}])

        def fb(ws):
            recording.append(ws.observation_summary)
            return [{"type": "wait", "duration_ms": 1}]

        reasoning.fallback_policy = fb
        injector = FeedbackInjector(tmp_path)
        injector.add_correction("preference", "stay near door", game="TestGame")
        agent = GameplayAgent(baseline=baseline, reasoning=reasoning, feedback_injector=injector,
                              max_steps=1, step_delay=0.0)
        await agent.run("win", game="TestGame")
        assert len(recording) == 1
        assert "Human feedback:" in recording[0]
        assert "stay near door" in recording[0]
        # correction was consumed after the action
        assert injector.store.pending(game="TestGame") == []
        all_items = injector.store.list(game="TestGame")
        assert all_items[0].applied is True
        assert all_items[0].applied_count == 1

    asyncio.run(run())


def test_agent_without_feedback_still_works(tmp_path):
    async def run():
        baseline = DummyBaseline(CapturedFrame(width=100, height=100, png_bytes=PNG))
        reasoning = ReasoningCoordinator(fallback_policy=lambda ws: [{"type": "wait", "duration_ms": 1}])
        agent = GameplayAgent(baseline=baseline, reasoning=reasoning, max_steps=1, step_delay=0.0)
        result = await agent.run("win", game="TestGame")
        assert result.steps == 1

    asyncio.run(run())

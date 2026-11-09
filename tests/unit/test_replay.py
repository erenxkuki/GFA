import asyncio
import json

from gfa.agent.agent import GameplayAgent
from gfa.agent.reasoning import ReasoningCoordinator
from gfa.replay import ReplayViewer, SessionRecorder, list_replays
from gfa.universal.capture import CapturedFrame

PNG = b"\\x89PNG\\r\\n\\x1a\\n" + b"\\x00" * 32


def _frame(w: int = 100, h: int = 100) -> CapturedFrame:
    return CapturedFrame(width=w, height=h, png_bytes=PNG + str(w).encode())


class DummyBaseline:
    def __init__(self, frame: CapturedFrame):
        self.frame = frame
        self.handlers = None

    def observe(self):
        return self.frame

    def capabilities(self):
        from gfa.gcl.capabilities import CapabilitySet

        return CapabilitySet.core_capabilities()

    def register_gcl_handlers(self, executor):
        self.handlers = executor

        async def wait_handler(cmd):
            return {"duration_ms": 1}

        executor.register_handler("wait", wait_handler)

    def emergency_stop(self):
        pass


def test_recorder_writes_replay(tmp_path):
    rec = SessionRecorder(data_dir=tmp_path, session_id="ses_test01", game="TestGame",
                          model="ollama/llama3", objective="reach target")
    pdir = rec.start()
    assert pdir.exists()
    rec.record_step(0, frame=_frame(), observation_summary="frame 100x100",
                    reasoning="move right", commands=[{"type": "move", "direction": "right", "duration_ms": 100}],
                    results=["succeeded"])
    rec.record_step(1, frame=_frame(), reasoning="wait", commands=[{"type": "wait"}],
                    results=["succeeded"], audio_events="Audio: gunshot(conf=0.90)")
    rec.record_error(2, "observe failed: boom")
    out = rec.finish(success=True, reason="objective met")
    assert out.exists()
    assert (out / "manifest.json").exists()
    assert (out / "frames" / "frame_00000.png").exists()
    assert (out / "frames" / "frame_00001.png").exists()

    manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["session_id"] == "ses_test01"
    assert manifest["steps"] == 2
    assert manifest["frames"] == 2
    assert manifest["success"] is True
    assert manifest["ended_at"] is not None

    events = [json.loads(line) for line in (out / "events.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(events) == 3
    assert events[0]["type"] == "step"
    assert events[0]["commands"][0]["direction"] == "right"
    assert events[2]["type"] == "error"


def test_recorder_never_raises(tmp_path):
    # Recording must never break gameplay, even with broken inputs
    rec = SessionRecorder(data_dir=tmp_path)
    rec.start()
    rec.record_step(0, frame=None, observation_summary="", reasoning="")
    rec.record_step(1, frame="not-a-frame")  # wrong type -> swallowed
    rec.finish(success=False, reason="test")
    assert rec.finished


def test_viewer_timeline_and_frames(tmp_path):
    rec = SessionRecorder(data_dir=tmp_path, session_id="ses_view", game="G", objective="O")
    rec.start()
    rec.record_step(0, frame=_frame(), reasoning="first", commands=[{"type": "move"}])
    rec.record_step(1, frame=_frame(), reasoning="second", commands=[{"type": "wait"}])
    rec.finish(success=False, reason="max steps")

    viewer = ReplayViewer(tmp_path, session_id="ses_view")
    assert viewer.session_id == "ses_view"
    assert len(viewer.steps) == 2
    assert len(viewer.timeline()) == 2
    fp = viewer.frame_path(0)
    assert fp is not None and fp.exists()
    assert viewer.frame_path(99) is None

    # step_at: nearest step at or before offset
    tl = viewer.timeline()
    first_t = tl[0][0]
    assert viewer.step_at(first_t + 1)["step"] in (0, 1)
    assert viewer.step_at(0) is not None or viewer.steps[0]["step"] == 0
    assert viewer.step_at(1e9)["step"] == 1  # far future -> last step

    # summary mentions session + objective
    s = viewer.summary()
    assert "ses_view" in s
    assert "Objective: O" in s

    # export copies the directory
    dest = tmp_path / "exported"
    out = viewer.export(dest)
    assert out.exists() and (out / "manifest.json").exists()


def test_list_replays(tmp_path):
    assert list_replays(tmp_path) == []
    rec = SessionRecorder(data_dir=tmp_path, session_id="ses_list01", game="G")
    rec.start()
    rec.record_step(0, frame=_frame())
    rec.finish(success=True, reason="done")
    rows = list_replays(tmp_path)
    assert len(rows) == 1
    assert rows[0]["session_id"] == "ses_list01"
    assert rows[0]["steps"] == 1


def test_agent_records_replay(tmp_path):
    async def run():
        baseline = DummyBaseline(_frame())
        reasoning = ReasoningCoordinator(fallback_policy=lambda ws: [{"type": "wait", "duration_ms": 1}])
        recorder = SessionRecorder(data_dir=tmp_path, session_id="ses_agent", game="G", objective="O")
        agent = GameplayAgent(baseline=baseline, reasoning=reasoning, recorder=recorder,
                              max_steps=2, step_delay=0.0)
        result = await agent.run("test objective", game="TestGame")
        assert result.steps == 2

    asyncio.run(run())
    viewer = ReplayViewer(tmp_path, session_id="ses_agent")
    assert len(viewer.steps) == 2
    assert all(ev["frame"] is not None for ev in viewer.steps)
    assert viewer.manifest["success"] is False
    assert viewer.manifest["reason"] == "max steps reached"
    assert viewer.manifest["game"] == "G"
    assert viewer.manifest["objective"] == "O"


def test_agent_without_recorder_still_works():
    async def run():
        baseline = DummyBaseline(_frame())
        reasoning = ReasoningCoordinator(fallback_policy=lambda ws: [{"type": "wait", "duration_ms": 1}])
        agent = GameplayAgent(baseline=baseline, reasoning=reasoning, max_steps=1, step_delay=0.0)
        result = await agent.run("test objective", game="TestGame")
        assert result.steps == 1

    asyncio.run(run())

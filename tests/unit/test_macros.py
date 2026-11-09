import asyncio

import pytest
from gfa.agent.agent import GameplayAgent
from gfa.agent.reasoning import ReasoningCoordinator
from gfa.macros import Macro, MacroLibrary, MacroPlayer, MacroRecorder
from gfa.macros.library import MacroLibraryError
from gfa.universal.baseline import BaselineConfig, UniversalBaseline
from gfa.universal.capture import CapturedFrame


def _frame():
    return CapturedFrame(width=100, height=100, png_bytes=b"\\x89PNG" + b"\\x00" * 16)


class DummyBaseline:
    """Minimal baseline-like object for agent tests (with macro library)."""

    def __init__(self, frame, macro_library):
        self.frame = frame
        self.macros = macro_library

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


def test_recorder_builds_macro(tmp_path):
    rec = MacroRecorder(name="combo1", game="G")
    rec.start_recording()
    rec.record([{"type": "wait", "duration_ms": 10}], delay_ms=0.0)
    rec.record([{"type": "move", "direction": "right", "duration_ms": 100}, {"type": "wait", "duration_ms": 5}],
               delay_ms=250.0)
    assert rec.step_count == 2
    macro = rec.stop_recording()
    assert macro.name == "combo1"
    assert len(macro.steps) == 2
    assert macro.command_count == 3
    assert macro.total_delay_ms == 250.0
    assert macro.steps[1].commands[0]["direction"] == "right"


def test_library_save_load_list_delete(tmp_path):
    lib = MacroLibrary(tmp_path)
    assert lib.list() == []

    macro = Macro(name="dodge", steps=[], game="ZZZ")
    from gfa.macros.models import MacroStep

    macro.steps = [MacroStep(commands=[{"type": "move", "direction": "left"}], delay_ms=10.0),
                   MacroStep(commands=[{"type": "wait", "duration_ms": 50}], delay_ms=5.0)]
    lib.save(macro)
    assert lib.exists("dodge")

    loaded = lib.load("dodge")
    assert loaded.name == "dodge"
    assert loaded.game == "ZZZ"
    assert loaded.command_count == 2
    assert len(lib.list()) == 1

    data = lib.export_json("dodge")
    assert '"dodge"' in data

    lib.delete("dodge")
    assert not lib.exists("dodge")
    assert lib.delete("dodge") is False

    # import/export round trip
    m = lib.import_json(data)
    assert m.name == "dodge"
    assert lib.exists("dodge")


def test_library_rejects_bad_json(tmp_path):
    lib = MacroLibrary(tmp_path)
    with pytest.raises(MacroLibraryError):
        lib.import_json("not json")


def test_player_plays_macro_with_mock_dispatch():
    from gfa.macros.models import MacroStep

    macro = Macro(name="m", steps=[
        MacroStep(commands=[{"type": "wait"}], delay_ms=0.0),
        MacroStep(commands=[{"type": "move", "direction": "right"}, {"type": "wait"}], delay_ms=5.0),
    ])

    calls = []

    def dispatch(cmd):
        calls.append(cmd["type"])
        return {"ok": True, "type": cmd["type"]}

    player = MacroPlayer(dispatch)
    result = player.play(macro, speed=10.0)  # speed up delays
    assert result.success is True
    assert result.commands_played == 3
    assert result.steps_played == 2
    assert calls == ["wait", "move", "wait"]
    assert result.duration_ms >= 0
    assert result.error is None


def test_player_stops_on_error():
    from gfa.macros.models import MacroStep

    macro = Macro(name="m", steps=[
        MacroStep(commands=[{"type": "wait"}], delay_ms=0.0),
        MacroStep(commands=[{"type": "boom"}], delay_ms=0.0),
        MacroStep(commands=[{"type": "wait"}], delay_ms=0.0),
    ])

    def dispatch(cmd):
        if cmd["type"] == "boom":
            raise ValueError("boom")
        return {"ok": True}

    result = MacroPlayer(dispatch).play(macro, stop_on_error=True)
    assert result.success is False
    assert result.steps_played == 1
    assert "boom" in result.error

    result2 = MacroPlayer(dispatch).play(macro, stop_on_error=False)
    assert result2.success is False
    assert result2.steps_played == 2  # third step still played


def test_player_honors_start_step():
    from gfa.macros.models import MacroStep

    macro = Macro(name="m", steps=[
        MacroStep(commands=[{"type": "wait"}], delay_ms=0.0),
        MacroStep(commands=[{"type": "move"}], delay_ms=0.0),
    ])
    calls = []
    player = MacroPlayer(lambda c: calls.append(c["type"]) or {"ok": True})
    result = player.play(macro, start_step=1)
    assert result.steps_played == 1
    assert calls == ["move"]


def test_baseline_dispatch_macro_commands(tmp_path):
    bl = UniversalBaseline(BaselineConfig(capture_scale=1.0, data_dir=tmp_path))
    recorded = []
    bl.wait = lambda ms=0: recorded.append(("wait", ms)) or {"duration_ms": ms}
    bl.move = lambda d, ms=0: recorded.append(("move", d)) or {"direction": d}
    bl.key = lambda k, a="tap": recorded.append(("key", k)) or {"key": k}

    out = bl._dispatch_macro_command({"type": "wait", "duration_ms": 42})
    assert out == {"duration_ms": 42}
    out = bl._dispatch_macro_command({"type": "move", "direction": "forward", "duration_ms": 100})
    assert out["direction"] == "forward"
    out = bl._dispatch_macro_command({"type": "key", "key": "space"})
    assert out["key"] == "space"
    assert recorded == [("wait", 42), ("move", "forward"), ("key", "space")]

    # nested params shape
    bl.move = lambda d, ms=0: {"direction": d, "duration_ms": ms}
    out = bl._dispatch_macro_command({"type": "move", "params": {"direction": "left", "duration_ms": 200}})
    assert out == {"direction": "left", "duration_ms": 200}

    import pytest

    with pytest.raises(ValueError):
        bl._dispatch_macro_command({"type": "nope"})


def test_baseline_execute_macro_roundtrip(tmp_path):
    bl = UniversalBaseline(BaselineConfig(capture_scale=1.0, data_dir=tmp_path))
    bl.wait = lambda ms=0: {"duration_ms": ms}
    bl.move = lambda d, ms=0: {"direction": d}

    lib = bl.macros
    from gfa.macros.models import MacroStep

    lib.save(Macro(name="rt", steps=[
        MacroStep(commands=[{"type": "move", "direction": "right", "duration_ms": 100}], delay_ms=0.0),
        MacroStep(commands=[{"type": "wait", "duration_ms": 10}], delay_ms=0.0),
    ]))
    res = bl.execute_macro("rt")
    assert res["success"] is True
    assert res["macro"] == "rt"
    assert res["steps_played"] == 2

    with pytest.raises(MacroLibraryError):
        bl.execute_macro("missing")


def test_agent_records_and_playback(tmp_path):
    async def run():
        lib = MacroLibrary(tmp_path)
        baseline = DummyBaseline(_frame(), lib)
        reasoning = ReasoningCoordinator(fallback_policy=lambda ws: [{"type": "wait", "duration_ms": 1}])
        agent = GameplayAgent(baseline=baseline, reasoning=reasoning, max_steps=2, step_delay=0.0)
        agent.start_macro_recording("my-macro", game="TestGame")
        await agent.run("win", game="TestGame")
        saved = agent.stop_macro_recording()
        assert saved is not None
        assert saved["name"] == "my-macro"
        assert len(saved["steps"]) == 2
        assert lib.exists("my-macro")
        loaded = lib.load("my-macro")
        assert loaded.game == "TestGame"
        assert loaded.steps[0].commands[0]["type"] == "wait"

    asyncio.run(run())


def test_macro_gcl_command_registered():
    from gfa.gcl.commands import default_registry

    spec = default_registry().get("macro")
    assert spec is not None
    assert spec.required == ["name"]

    from gfa.gcl.capabilities import CapabilitySet

    assert CapabilitySet.core_capabilities().allows_command("macro")

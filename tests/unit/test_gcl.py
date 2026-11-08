import asyncio

from gfa.gcl.capabilities import CapabilitySet
from gfa.gcl.executor import CommandExecutor
from gfa.gcl.parser import parse_batch
from gfa.gcl.schema import CommandStatus
from gfa.gcl.validator import GCLValidator, ValidationContext


def test_parse_batch_basic():
    raw = {"protocol": "gcl-v1", "commands": [{"type": "move", "direction": "forward", "duration_ms": 500}]}
    batch = parse_batch(raw)
    assert len(batch.commands) == 1
    assert batch.commands[0].type == "move"
    assert batch.commands[0].params["direction"] == "forward"


def test_parse_single_command_list_shorthand():
    batch = parse_batch([{"type": "wait", "duration_ms": 100}])
    assert batch.protocol == "gcl-v1"
    assert batch.commands[0].type == "wait"


def test_parse_invalid_protocol():
    try:
        parse_batch({"protocol": "gcl-v2", "commands": [{"type": "wait"}]})
        raise AssertionError()
    except Exception as e:
        assert "protocol" in str(e).lower() or "unsupported" in str(e).lower()


def test_validator_accepts_valid():
    caps = CapabilitySet.core_capabilities()
    ctx = ValidationContext(capabilities=caps)
    batch = parse_batch({"protocol": "gcl-v1", "commands": [{"type": "move", "direction": "forward", "duration_ms": 100}]})
    vr = GCLValidator().validate_batch(batch, ctx)
    assert vr.ok is True, vr.errors


def test_validator_rejects_unknown_type():
    caps = CapabilitySet.core_capabilities()
    ctx = ValidationContext(capabilities=caps)
    batch = parse_batch({"protocol": "gcl-v1", "commands": [{"type": "teleport", "x": 1}]})
    vr = GCLValidator().validate_batch(batch, ctx)
    assert vr.ok is False


def test_validator_rejects_missing_capability():
    caps = CapabilitySet()  # empty
    ctx = ValidationContext(capabilities=caps)
    batch = parse_batch({"protocol": "gcl-v1", "commands": [{"type": "move", "direction": "forward"}]})
    vr = GCLValidator().validate_batch(batch, ctx)
    assert vr.ok is False


def test_validator_duration_budget():
    caps = CapabilitySet.core_capabilities()
    ctx = ValidationContext(capabilities=caps, max_total_duration_ms=100)
    batch = parse_batch({"protocol": "gcl-v1", "commands": [
        {"type": "wait", "duration_ms": 200},
        {"type": "wait", "duration_ms": 200},
    ]})
    vr = GCLValidator().validate_batch(batch, ctx)
    assert vr.ok is False


def test_executor_runs_handlers():
    async def run():
        caps = CapabilitySet.core_capabilities()
        ctx = ValidationContext(capabilities=caps)
        ex = CommandExecutor()
        async def move_handler(cmd):
            return {"moved": cmd.params["direction"]}
        ex.register_handler("move", move_handler)
        ex.register_handler("wait", lambda cmd: asyncio.coroutine(lambda: {"waited": cmd.params.get("duration_ms", 0)})())
        # register wait properly
        async def wait_handler(cmd):
            return {"waited": cmd.params.get("duration_ms", 0)}
        ex.register_handler("wait", wait_handler)
        batch = parse_batch({"protocol": "gcl-v1", "commands": [
            {"type": "move", "direction": "forward", "duration_ms": 100},
            {"type": "wait", "duration_ms": 50},
        ]})
        res = await ex.execute_batch(batch, ctx)
        assert all(r.status == CommandStatus.SUCCEEDED for r in res)
        assert res[0].data["moved"] == "forward"
    asyncio.run(run())


def test_executor_rejects_without_handler():
    async def run():
        caps = CapabilitySet.core_capabilities()
        ctx = ValidationContext(capabilities=caps)
        ex = CommandExecutor()
        batch = parse_batch({"protocol": "gcl-v1", "commands": [{"type": "move", "direction": "forward"}]})
        res = await ex.execute_batch(batch, ctx)
        assert res[0].status == CommandStatus.FAILED
    asyncio.run(run())


def test_executor_cancellation():
    async def run():
        caps = CapabilitySet.core_capabilities()
        ctx = ValidationContext(capabilities=caps)
        ex = CommandExecutor()
        async def slow(cmd):
            await asyncio.sleep(10)
            return {}
        ex.register_handler("wait", slow)
        batch = parse_batch({"protocol": "gcl-v1", "commands": [{"type": "wait", "duration_ms": 100, "timeout_ms": 50}]})
        res = await ex.execute_batch(batch, ctx)
        assert res[0].status == CommandStatus.TIMED_OUT
    asyncio.run(run())


def test_invoke_capability():
    caps = CapabilitySet.core_capabilities()
    caps.add("adapter.minecraft.inventory.inspect")
    ctx = ValidationContext(capabilities=caps)
    batch = parse_batch({"protocol": "gcl-v1", "commands": [{"type": "invoke", "capability": "adapter.minecraft.inventory.inspect"}]})
    vr = GCLValidator().validate_batch(batch, ctx)
    assert vr.ok is True


def test_emergency_stop_flag():
    ex = CommandExecutor()
    ex.emergency_stop()
    assert ex._emergency is True
    assert ex._cancelled is True
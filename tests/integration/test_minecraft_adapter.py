"""Smoke tests for the Minecraft adapter."""

import subprocess
import sys
from pathlib import Path

import pytest

ADAPTER_DIR = Path(__file__).resolve().parents[2] / "official-adapters" / "gfa-minecraft"


@pytest.fixture
def runner():
    import json
    p = subprocess.Popen(
        [sys.executable, "adapter.py"],
        cwd=ADAPTER_DIR,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        text=True,
    )
    yield p
    p.stdin.close()
    p.wait(timeout=5)


def _call(p, method, params=None):
    import json
    req = {"method": method, "params": params or {}, "id": 1}
    p.stdin.write(json.dumps(req) + "\n")
    p.stdin.flush()
    return json.loads(p.stdout.readline())


def test_initialize_and_observe(runner):
    r = _call(runner, "initialize")
    assert r["result"]["ok"] is True
    assert "game.observe_state" in r["result"]["capabilities"]
    obs = _call(runner, "observe")["result"]["observations"][0]
    assert obs["health"] == 20
    assert obs["hotbar"] == ["empty"] * 9
    assert obs["position"] == {"x": 0, "y": 0, "z": 0}


def test_move_and_eat(runner):
    _call(runner, "initialize")
    r = _call(runner, "execute", {"command": {"type": "game.move", "direction": "right"}})
    assert r["result"]["status"] == "succeeded"
    assert r["result"]["state"]["moves"] == 1
    assert r["result"]["state"]["position"]["z"] == 1
    # eat with empty hunger (full) -> failed
    er = _call(runner, "execute", {"command": {"type": "game.eat"}})
    assert er["result"]["status"] == "failed"


def test_place_requires_item(runner):
    _call(runner, "initialize")
    r = _call(runner, "execute", {"command": {"type": "game.place"}})
    assert r["result"]["status"] == "failed"
    # craft without recipe fails
    r2 = _call(runner, "execute", {"command": {"type": "game.craft"}})
    assert r2["result"]["status"] == "failed"
    # craft with recipe succeeds
    r3 = _call(runner, "execute", {"command": {"type": "game.craft", "recipe": "stick"}})
    assert r3["result"]["status"] == "succeeded"


def test_mine_attack_inventory_reset(runner):
    _call(runner, "initialize")
    for cmd in ["game.mine", "game.attack"]:
        r = _call(runner, "execute", {"command": {"type": cmd}})
        assert r["result"]["status"] == "succeeded"
    inv = _call(runner, "execute", {"command": {"type": "game.inventory", "open": True}})
    assert inv["result"]["state"]["inventory_open"] is True
    reset = _call(runner, "execute", {"command": {"type": "game.reset"}})
    assert reset["result"]["state"]["inventory_open"] is False
    assert reset["result"]["state"]["moves"] == 0
    h = _call(runner, "health")
    assert h["result"]["ok"] is True
    s = _call(runner, "shutdown")
    assert s["result"]["ok"] is True

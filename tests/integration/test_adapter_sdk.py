from pathlib import Path

from gfa.adapter_sdk.host import AdapterHost
from gfa.adapter_sdk.manifest import validate_manifest_file

REPO = Path(__file__).resolve().parents[2]


def test_python_echo_adapter():
    adir = REPO / "examples" / "adapters" / "echo-adapter"
    ok, errors, manifest = validate_manifest_file(adir / "manifest.json")
    assert ok, errors
    host = AdapterHost(manifest, cwd=adir)
    init = host.start()
    assert init.get("ok") is True
    assert "echo.observe" in init.get("capabilities", [])
    h = host.health()
    assert h.get("ok") is True
    obs = host.observe()
    assert obs["observations"][0]["count"] == 1
    res = host.execute({"type": "move", "direction": "forward"})
    assert res["status"] == "succeeded"
    host.shutdown()
    assert not host.running


def test_node_echo_adapter():
    adir = REPO / "examples" / "adapters" / "echo-adapter-node"
    ok, errors, manifest = validate_manifest_file(adir / "manifest.json")
    assert ok, errors
    host = AdapterHost(manifest, cwd=adir)
    init = host.start()
    assert init.get("ok") is True
    obs = host.observe()
    assert obs["observations"][0]["lang"] == "node"
    host.shutdown()
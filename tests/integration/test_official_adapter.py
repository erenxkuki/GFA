from pathlib import Path

from gfa.adapter_sdk.host import AdapterHost
from gfa.adapter_sdk.manifest import validate_manifest_file

REPO = Path(__file__).resolve().parents[2]


def test_official_reference_adapter():
    adir = REPO / "official-adapters" / "gfa-reference-game"
    ok, errors, manifest = validate_manifest_file(adir / "manifest.json")
    assert ok, errors
    assert manifest.id.startswith("official.")
    host = AdapterHost(manifest, cwd=adir)
    init = host.start()
    assert init.get("ok") is True
    assert "game.observe_state" in init.get("capabilities", [])
    obs = host.observe()
    assert obs["observations"][0]["distance"] == 10
    res = host.execute({"type": "game.move", "direction": "right"})
    assert res["status"] == "succeeded"
    obs2 = host.observe()
    assert obs2["observations"][0]["player"]["x"] == 1
    host.execute({"type": "game.reset"})
    obs3 = host.observe()
    assert obs3["observations"][0]["player"]["x"] == 0
    host.shutdown()
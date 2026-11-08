import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "packages" / "gfa-core" / "src"))

from gfa.adapter_sdk.base import Adapter, AdapterRunner
from gfa.adapter_sdk.manifest import AdapterManifest

manifest = AdapterManifest.from_file(Path(__file__).with_name("manifest.json"))


class ReferenceGameAdapter(Adapter):
    def __init__(self, manifest):
        super().__init__(manifest)
        self.state = {"player": {"x": 0, "y": 0}, "target": {"x": 5, "y": 5}, "moves": 0}

    def initialize(self, context=None):
        super().initialize(context)
        self.state = {"player": {"x": 0, "y": 0}, "target": {"x": 5, "y": 5}, "moves": 0}
        return {"ok": True, "capabilities": list(self.manifest.capabilities)}

    def observe(self):
        p = self.state["player"]
        t = self.state["target"]
        dist = abs(p["x"] - t["x"]) + abs(p["y"] - t["y"])
        return {"observations": [{"type": "game_state", "player": p, "target": t, "distance": dist, "moves": self.state["moves"]}]}

    def execute(self, command):
        cmd = command or {}
        ctype = cmd.get("type")
        if ctype == "game.move":
            direction = cmd.get("direction", "right")
            delta = {"up": (0, -1), "down": (0, 1), "left": (-1, 0), "right": (1, 0)}.get(direction, (0, 0))
            self.state["player"]["x"] += delta[0]
            self.state["player"]["y"] += delta[1]
            self.state["moves"] += 1
            return {"status": "succeeded", "state": self.state}
        if ctype == "game.reset":
            self.initialize()
            return {"status": "succeeded", "state": self.state}
        return {"status": "failed", "message": f"unknown command {ctype}"}

    def health(self):
        return {"ok": True, "moves": self.state["moves"]}


if __name__ == "__main__":
    AdapterRunner(ReferenceGameAdapter(manifest)).run_stdio()
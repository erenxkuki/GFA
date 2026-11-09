"""GFA adapter for Minecraft.

State model: health/hunger/hotbar slot, player position, biome, inventory.
Commands: move, look, mine, place, craft, attack, eat, inventory open/close.

This adapter is a *reference* for how to wire a game into GFA: it exposes the
structured observations the agent needs (health, hunger, hotbar, biome) so
they can be merged into the world state, and the GCL commands the agent can
issue. The actual screen capture + input happens through the Universal Baseline
(Windows SendInput), so the adapter does not need to touch the game process.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "packages" / "gfa-core" / "src"))

from gfa.adapter_sdk.base import Adapter, AdapterRunner
from gfa.adapter_sdk.manifest import AdapterManifest

manifest = AdapterManifest.from_file(Path(__file__).with_name("manifest.json"))

# Hotbar slot indices 0..8
HOTBAR_SIZE = 9


class MinecraftAdapter(Adapter):
    def __init__(self, manifest: AdapterManifest):
        super().__init__(manifest)
        self.state = self._default_state()

    @staticmethod
    def _default_state() -> dict[str, Any]:
        return {
            "health": 20,
            "max_health": 20,
            "hunger": 20,
            "max_hunger": 20,
            "hotbar_slot": 0,
            "hotbar": [None] * HOTBAR_SIZE,
            "inventory_open": False,
            "position": {"x": 0, "y": 0, "z": 0},
            "biome": "plains",
            "dimension": "overworld",
            "time_of_day": "day",
            "mining": False,
            "attacking": False,
            "moves": 0,
        }

    def initialize(self, context=None):
        super().initialize(context)
        self.state = self._default_state()
        return {"ok": True, "capabilities": list(self.manifest.capabilities)}

    def health(self):
        return {
            "ok": True,
            "health": self.state["health"],
            "hunger": self.state["hunger"],
            "hotbar_slot": self.state["hotbar_slot"],
            "position": self.state["position"],
            "biome": self.state["biome"],
            "time_of_day": self.state["time_of_day"],
        }

    def observe(self):
        obs = {
            "type": "game_state",
            "health": self.state["health"],
            "max_health": self.state["max_health"],
            "hunger": self.state["hunger"],
            "max_hunger": self.state["max_hunger"],
            "hotbar_slot": self.state["hotbar_slot"],
            "hotbar": [self._slot_name(s) for s in self.state["hotbar"]],
            "inventory_open": self.state["inventory_open"],
            "position": self.state["position"],
            "biome": self.state["biome"],
            "dimension": self.state["dimension"],
            "time_of_day": self.state["time_of_day"],
            "mining": self.state["mining"],
            "attacking": self.state["attacking"],
            "moves": self.state["moves"],
        }
        return {"observations": [obs]}

    @staticmethod
    def _slot_name(slot: Any) -> str:
        if slot is None:
            return "empty"
        if isinstance(slot, dict):
            return f"{slot.get('item', '?')}x{slot.get('count', 1)}"
        return str(slot)

    def execute(self, command: dict[str, Any] | None = None):
        cmd = command or {}
        ctype = cmd.get("type")

        if ctype == "game.move":
            direction = cmd.get("direction", "forward")
            delta = {
                "forward": (1, 0, 0), "backward": (-1, 0, 0),
                "left": (0, 0, -1), "right": (0, 0, 1),
                "up": (0, 1, 0), "down": (0, -1, 0),
            }.get(direction, (0, 0, 0))
            p = self.state["position"]
            p["x"] += delta[0]
            p["y"] += delta[1]
            p["z"] += delta[2]
            self.state["moves"] += 1
            return {"status": "succeeded", "state": self.state}

        if ctype == "game.look":
            return {"status": "succeeded", "state": self.state}

        if ctype == "game.mine":
            # mining is a sustained action; toggle flag + small position jitter
            self.state["mining"] = True
            return {"status": "succeeded", "state": self.state}

        if ctype == "game.place":
            slot = self.state["hotbar_slot"]
            item = self.state["hotbar"][slot]
            if not item:
                return {"status": "failed", "message": "hotbar slot empty"}
            self.state["hotbar"][slot] = None
            return {"status": "succeeded", "state": self.state}

        if ctype == "game.craft":
            # placeholder: crafting requires recipe + materials; accept as intent
            recipe = cmd.get("recipe")
            if not recipe:
                return {"status": "failed", "message": "missing recipe"}
            return {"status": "succeeded", "recipe": recipe, "state": self.state}

        if ctype == "game.attack":
            self.state["attacking"] = True
            return {"status": "succeeded", "state": self.state}

        if ctype == "game.eat":
            if self.state["hunger"] >= self.state["max_hunger"]:
                return {"status": "failed", "message": "not hungry"}
            self.state["hunger"] = min(self.state["max_hunger"], self.state["hunger"] + 4)
            return {"status": "succeeded", "state": self.state}

        if ctype == "game.inventory":
            self.state["inventory_open"] = bool(cmd.get("open", True))
            return {"status": "succeeded", "state": self.state}

        if ctype == "game.reset":
            self.initialize()
            return {"status": "succeeded", "state": self.state}

        return {"status": "failed", "message": f"unknown command {ctype}"}

    def shutdown(self):
        self.state["mining"] = False
        self.state["attacking"] = False
        return super().shutdown()


if __name__ == "__main__":
    AdapterRunner(MinecraftAdapter(manifest)).run_stdio()

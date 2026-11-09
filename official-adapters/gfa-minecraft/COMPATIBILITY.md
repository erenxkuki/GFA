# GFA Minecraft Adapter

Reference adapter for **Minecraft Java/Bedrock**. Demonstrates how to wire
Minecraft into GFA: structured HUD observations (health, hunger, hotbar,
biome, position) and the GCL commands the agent can issue.

## Capabilities

- `game.observe_state` — returns health/hunger/hotbar/inventory/position/biome/time
- `game.move` — move forward/backward/left/right/up/down
- `game.look` — camera look (delegated to the Universal Baseline)
- `game.click` — left/right click (attack/place/break)
- `game.mine` — toggle mining
- `game.place` — place the held block
- `game.craft` — craft a recipe
- `game.attack` — attack
- `game.eat` — eat food from the hotbar (restores hunger)
- `game.inventory` — open/close inventory
- `game.reset` — reset to spawn state

## Usage

```bash
gfa adapter validate official-adapters/gfa-minecraft/manifest.json
gfa adapter test official-adapters/gfa-minecraft
```

## Notes

- This adapter tracks a *reference state* (no live game memory reading) — the
  Universal Baseline (`capture_screen` + `SendInput`) is what actually drives
  the real Minecraft window. The adapter's value is **structured observations**
  and **structured commands**, not memory hacks (anti-cheat safe).
- Recommended genre for the agent: `fps` (crosshair + health bars).
- Recommended keybind preset: `fps-wasd`.

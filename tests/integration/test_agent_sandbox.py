import asyncio
import threading
import time

import tkinter as tk

from gfa.agent.agent import GameplayAgent
from gfa.agent.perception import ColorBlobPerception
from gfa.agent.reasoning import ReasoningCoordinator
from gfa.universal.baseline import BaselineConfig, UniversalBaseline


def _heuristic_policy(ws):
    objs = {o["label"]: o for o in ws.visible_objects}
    if "blue" not in objs or "red" not in objs:
        return [{"type": "observe"}]
    dx = objs["red"]["x"] - objs["blue"]["x"]
    dy = objs["red"]["y"] - objs["blue"]["y"]
    if abs(dx) > abs(dy):
        return [{"type": "move", "direction": "right" if dx > 0 else "left", "duration_ms": 120}]
    return [{"type": "move", "direction": "down" if dy > 0 else "up", "duration_ms": 120}]


def test_agent_completes_sandbox_objective():
    root = tk.Tk()
    root.title("GFA Agent Sandbox")
    root.geometry("400x300+50+50")
    canvas = tk.Canvas(root, width=400, height=300, bg="white")
    canvas.pack()

    player = {"x": 60, "y": 60}
    target = {"x": 320, "y": 230}
    player_rect = canvas.create_rectangle(player["x"], player["y"], player["x"] + 20, player["y"] + 20, fill="blue")
    target_rect = canvas.create_rectangle(target["x"], target["y"], target["x"] + 20, target["y"] + 20, fill="red")

    def move_player(dx, dy):
        player["x"] = max(0, min(380, player["x"] + dx))
        player["y"] = max(0, min(280, player["y"] + dy))
        canvas.coords(player_rect, player["x"], player["y"], player["x"] + 20, player["y"] + 20)

    def on_key(event):
        k = event.keysym.lower()
        if k in ("w", "up"):
            move_player(0, -15)
        elif k in ("s", "down"):
            move_player(0, 15)
        elif k in ("a", "left"):
            move_player(-15, 0)
        elif k in ("d", "right"):
            move_player(15, 0)

    root.bind("<KeyPress>", on_key)
    root.update()
    time.sleep(0.5)

    result_box = {}

    def run_agent():
        async def main():
            bl = UniversalBaseline(BaselineConfig(target_window_title="GFA Agent Sandbox", capture_scale=0.5))
            bl.select_window("GFA Agent Sandbox")
            reasoning = ReasoningCoordinator(model_provider=None, fallback_policy=_heuristic_policy)
            perception = ColorBlobPerception(color_map={"blue": (0, 0, 200), "red": (200, 0, 0)}, tolerance=80)

            def objective_check(ws):
                objs = {o["label"]: o for o in ws.visible_objects}
                if "blue" in objs and "red" in objs:
                    dx = objs["blue"]["x"] - objs["red"]["x"]
                    dy = objs["blue"]["y"] - objs["red"]["y"]
                    return (dx * dx + dy * dy) ** 0.5 < 40
                return False

            agent = GameplayAgent(
                baseline=bl, reasoning=reasoning, perception=perception,
                objective_check=objective_check, max_steps=40, step_delay=0.2,
            )
            result_box["result"] = await agent.run("Move the blue player to the red target", game="Sandbox")

        asyncio.run(main())

    agent_thread = threading.Thread(target=run_agent, daemon=True)
    agent_thread.start()

    # keep UI alive until agent finishes or timeout
    deadline = time.time() + 60
    while agent_thread.is_alive() and time.time() < deadline:
        try:
            root.update()
        except tk.TclError:
            break
        time.sleep(0.05)

    try:
        root.destroy()
    except Exception:
        pass

    assert "result" in result_box, "agent did not finish"
    res = result_box["result"]
    assert res.success is True, f"agent failed: {res.reason} errors={res.errors}"
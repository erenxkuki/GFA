import time

import tkinter as tk

from gfa.gcl.executor import CommandExecutor
from gfa.gcl.parser import parse_batch
from gfa.gcl.validator import ValidationContext
from gfa.universal.baseline import BaselineConfig, UniversalBaseline
from gfa.universal.windows import get_client_rect


def test_baseline_observe_and_click():
    root = tk.Tk()
    root.title("GFA Sandbox")
    root.geometry("320x240+100+100")
    state = {"clicked": False}

    def on_click():
        state["clicked"] = True
        btn.config(text="CLICKED")

    btn = tk.Button(root, text="Click me", command=on_click)
    btn.pack(pady=40, expand=True)
    root.update()
    time.sleep(0.5)

    try:
        bl = UniversalBaseline(BaselineConfig(target_window_title="GFA Sandbox", capture_scale=0.5))
        win = bl.select_window("GFA Sandbox")
        assert win is not None
        frame = bl.observe()
        assert frame.width > 0

        cl = get_client_rect(win.hwnd)
        cx = (cl[0] + cl[2]) // 2
        cy = (cl[1] + cl[3]) // 2

        caps = bl.capabilities()
        ctx = ValidationContext(capabilities=caps)
        ex = CommandExecutor()
        bl.register_gcl_handlers(ex)
        batch = parse_batch({"protocol": "gcl-v1", "commands": [
            {"type": "click", "button": "left", "x": cx, "y": cy},
        ]})
        import asyncio
        res = asyncio.run(ex.execute_batch(batch, ctx))
        assert res[0].status.value == "succeeded", res[0].message
        # process pending events
        for _ in range(10):
            root.update()
            time.sleep(0.1)
        assert state["clicked"] is True, "button was not clicked"
    finally:
        try:
            root.destroy()
        except Exception:
            pass
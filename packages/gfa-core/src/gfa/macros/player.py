"""Macro player: replay recorded macros through a command dispatch."""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from gfa.macros.models import Macro

DispatchFn = Callable[[dict[str, Any]], Any]


@dataclass
class PlaybackResult:
    """Outcome of playing a macro."""

    macro_name: str
    success: bool
    steps_played: int = 0
    commands_played: int = 0
    duration_ms: float = 0.0
    error: str | None = None
    step_results: list[Any] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "macro": self.macro_name,
            "success": self.success,
            "steps_played": self.steps_played,
            "commands_played": self.commands_played,
            "duration_ms": round(self.duration_ms, 1),
            "error": self.error,
        }


class MacroPlayer:
    """Plays macros by dispatching each recorded command in order.

    The ``dispatch`` callable receives one raw GCL command dict and returns a
    result — in GFA this is wired to :meth:`UniversalBaseline._dispatch_macro_command`.
    Timing: each step sleeps its recorded ``delay_ms`` (scaled by ``speed``,
    capped at ``max_delay_ms``) before executing, reproducing the original pacing.
    """

    def __init__(self, dispatch: DispatchFn, max_delay_s: float = 5.0):
        self.dispatch = dispatch
        self.max_delay_s = max_delay_s

    def play(self, macro: Macro, speed: float = 1.0, stop_on_error: bool = True,
             start_step: int = 0) -> PlaybackResult:
        """Play the macro's steps starting at ``start_step``.

        Stops at the first failing command when ``stop_on_error`` (default) —
        the result reports which step/command failed. With ``False``, the
        error is recorded and playback continues with the next step.
        """
        result = PlaybackResult(macro_name=macro.name, success=True)
        errors: list[str] = []
        t0 = time.monotonic()
        for i, step in enumerate(macro.steps):
            if i < start_step:
                continue
            if step.delay_ms > 0:
                time.sleep(min(step.delay_ms / 1000.0 / max(0.01, speed), self.max_delay_s))
            try:
                for cmd in step.commands:
                    out = self.dispatch(dict(cmd))
                    result.step_results.append(out)
                    result.commands_played += 1
            except Exception as exc:  # noqa: BLE001
                errors.append(f"step {i}: {type(exc).__name__}: {exc}")
                if stop_on_error:
                    break
                continue
            result.steps_played += 1
        result.duration_ms = (time.monotonic() - t0) * 1000.0
        if errors:
            result.success = False
            result.error = errors[-1]
        return result

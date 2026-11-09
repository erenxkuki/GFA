"""Macro recorder: capture live GCL execution into a replayable macro."""

from __future__ import annotations

import time
from typing import Any

from gfa.macros.models import Macro, MacroStep


class MacroRecorder:
    """Records executed GCL command batches with their timing.

    Lifecycle: :meth:`start_recording`, then :meth:`record` for each executed
    step, then :meth:`stop_recording` to get the finished :class:`Macro`.

    The ``agent`` integration records wall-clock delays between steps so
    playback reproduces the same pacing.
    """

    def __init__(self, name: str = "unnamed", game: str | None = None,
                 description: str = "", source: str = "agent"):
        self.name = name
        self.game = game
        self.description = description
        self.source = source
        self._steps: list[MacroStep] = []
        self._recording = False
        self._last_t: float | None = None

    @property
    def recording(self) -> bool:
        return self._recording

    @property
    def step_count(self) -> int:
        return len(self._steps)

    def start_recording(self) -> None:
        self._steps = []
        self._recording = True
        self._last_t = time.monotonic()

    def record(self, commands: Any, delay_ms: float | None = None) -> MacroStep:
        """Append one executed step; ``delay_ms`` is measured automatically if omitted."""
        now = time.monotonic()
        if delay_ms is None and self._last_t is not None:
            delay_ms = max(0.0, (now - self._last_t) * 1000.0)
        step = MacroStep(commands=self._normalize(commands), delay_ms=float(delay_ms or 0.0))
        self._steps.append(step)
        self._last_t = now
        return step

    def stop_recording(self) -> Macro:
        self._recording = False
        return Macro(name=self.name, steps=list(self._steps), game=self.game,
                     description=self.description, source=self.source)

    def discard(self) -> None:
        self._steps = []
        self._recording = False
        self._last_t = None

    @staticmethod
    def _normalize(commands: Any) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        if isinstance(commands, dict):
            commands = [commands]
        for c in commands or []:
            if isinstance(c, dict) and "type" in c:
                out.append(dict(c))
        return out

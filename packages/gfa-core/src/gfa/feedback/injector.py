"""Feedback injector: pending corrections → world state → learning."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from gfa.feedback.corrections import Correction, FeedbackStore, LearningLoop


class FeedbackInjector:
    """Feeds human corrections into the agent loop and learns from them.

    Typical use inside ``GameplayAgent``:

    - ``inject(game)`` — returns human-readable correction lines for the
      world state (e.g. ``"Human: prefer dodge when enemy is close"``) and
      remembers which corrections were shown.
    - ``consume()`` — after the model acts on a step, marks shown
      corrections as applied and (with a memory manager) stores them as
      verified procedural memories.

    When no corrections are pending, :meth:`inject` returns ``""`` — zero
    cost for normal runs.
    """

    def __init__(self, data_dir: Path, memory_manager: Any = None):
        self.store = FeedbackStore(data_dir)
        self.memory_manager = memory_manager
        self.learning = LearningLoop(memory_manager) if memory_manager is not None else None
        self._shown: list[Correction] = []

    def add_correction(self, ctype: str, text: str, game: str | None = None, source: str = "cli") -> Correction:
        return self.store.add(ctype, text, game=game, source=source)

    def inject(self, game: str | None = None) -> str:
        """Return pending corrections as model-readable text (or '')."""
        pending = self.store.pop_pending(game=game)
        self._shown = pending
        if not pending:
            return ""
        return "Human feedback: " + "; ".join(f"{c.type}: {c.text}" for c in pending)

    def consume_after_action(self) -> list[Correction]:
        """Mark injected corrections as applied and learn from them."""
        applied = self._shown
        self._shown = []
        if not applied:
            return []
        self.store.mark_applied([c.id for c in applied])
        if self.learning is not None:
            for c in applied:
                try:
                    self.learning.learn_from_correction(c)
                except Exception:  # noqa: BLE001 - learning must never break play
                    continue
        return applied

    @property
    def shown_count(self) -> int:
        return len(self._shown)

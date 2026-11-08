"""Speculative execution: act on predictions, verify later.

Like CPU branch prediction — guess the next action based on patterns,
execute it immediately, and verify/correct when the real perception arrives.
"""

from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class SpeculativeAction:
    commands: list[dict[str, Any]]
    predicted_state: dict[str, Any] | None = None
    confidence: float = 0.5
    executed_at: float = field(default_factory=time.time)
    verified: bool = False
    correct: bool = True


class SpeculativeExecutor:
    """Executes predicted actions before confirmation, corrects if wrong."""

    def __init__(self, confidence_threshold: float = 0.7):
        self.confidence_threshold = confidence_threshold
        self._history: deque[SpeculativeAction] = deque(maxlen=50)
        self._pattern_cache: dict[str, list[dict[str, Any]]] = {}
        self._correct_count = 0
        self._total_count = 0

    def predict(self, state_key: str, context: dict[str, Any] | None = None) -> list[dict[str, Any]] | None:
        """Predict next action based on cached patterns."""
        if state_key in self._pattern_cache:
            return self._pattern_cache[state_key]
        return None

    def learn(self, state_key: str, commands: list[dict[str, Any]]) -> None:
        """Cache a successful action pattern for future prediction."""
        self._pattern_cache[state_key] = commands

    def should_speculate(self, confidence: float) -> bool:
        return confidence >= self.confidence_threshold

    def record(self, action: SpeculativeAction) -> None:
        self._history.append(action)
        self._total_count += 1
        if action.correct:
            self._correct_count += 1

    def verify(self, action: SpeculativeAction, actual_state: dict[str, Any]) -> bool:
        """Verify if speculative action was correct."""
        action.verified = True
        if action.predicted_state and actual_state:
            # Compare predicted vs actual
            correct = True
            for k, v in action.predicted_state.items():
                if k in actual_state and actual_state[k] != v:
                    correct = False
                    break
            action.correct = correct
        self.record(action)
        return action.correct

    @property
    def accuracy(self) -> float:
        if self._total_count == 0:
            return 0.0
        return self._correct_count / self._total_count

    def stats(self) -> dict[str, Any]:
        return {
            "total_speculations": self._total_count,
            "correct": self._correct_count,
            "accuracy": round(self.accuracy, 3),
            "cached_patterns": len(self._pattern_cache),
        }


class InputCoalescer:
    """Batches rapid inputs into fewer SendInput calls.

    Instead of sending 5 separate key presses in 5ms, coalesce them
    into one SendInput call with 5 inputs.
    """

    def __init__(self, max_batch: int = 8, flush_interval_ms: float = 5.0):
        self.max_batch = max_batch
        self.flush_interval_ms = flush_interval_ms
        self._pending: list[Any] = []
        self._last_flush = 0.0

    def add(self, inp: Any) -> None:
        self._pending.append(inp)
        if len(self._pending) >= self.max_batch:
            self.flush()

    def should_flush(self) -> bool:
        if not self._pending:
            return False
        elapsed = (time.time() - self._last_flush) * 1000
        return elapsed >= self.flush_interval_ms

    def flush(self) -> list[Any]:
        batch = self._pending[:]
        self._pending.clear()
        self._last_flush = time.time()
        return batch

    @property
    def pending_count(self) -> int:
        return len(self._pending)
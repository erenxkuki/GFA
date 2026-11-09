"""Reward ledger and bandit-style strategy scorer.

The ledger persists reward history to ``<data_dir>/rewards/<game>.jsonl``
(one signal per line). The scorer keeps a running average reward per
*action signature* — a compact string describing a GCL command batch like
``"wait"`` or ``"combo:dodge_left,move:right"`` — so the agent learns which
actions earn rewards and can prefer them.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from gfa.rl.rewards import RewardExtractor, RewardSignal


def command_signature(commands: Any) -> str:
    """Compact signature for a GCL command batch, e.g. 'combo:dodge_left,move:right'."""
    parts: list[str] = []
    if isinstance(commands, dict):
        commands = [commands]
    for c in commands or []:
        if not isinstance(c, dict) or "type" not in c:
            continue
        extra = c.get("name") or c.get("direction") or c.get("key") or ""
        parts.append(f"{c['type']}:{extra}" if extra else c["type"])
    return ",".join(parts) or "noop"


class StrategyScorer:
    """Bandit scoring: average reward that followed each action signature."""

    def __init__(self):
        self._totals: dict[str, float] = {}
        self._counts: dict[str, int] = {}

    def update(self, signature: str, reward: float) -> None:
        self._totals[signature] = self._totals.get(signature, 0.0) + reward
        self._counts[signature] = self._counts.get(signature, 0) + 1

    def average(self, signature: str) -> float:
        n = self._counts.get(signature, 0)
        return self._totals.get(signature, 0.0) / n if n else 0.0

    def count(self, signature: str) -> int:
        return self._counts.get(signature, 0)

    def ranked(self) -> list[tuple[str, float, int]]:
        """All signatures sorted by average reward (best first)."""
        return sorted(
            ((s, self.average(s), self._counts[s]) for s in self._totals),
            key=lambda t: -t[1],
        )

    def best(self, n: int = 3) -> list[str]:
        """Top-n signatures by average reward."""
        return [s for s, _, _ in self.ranked()[:n]]

    def best_hint(self) -> str:
        ranked = self.ranked()
        if not ranked:
            return ""
        best_sig, best_avg, _ = ranked[0]
        return f"Best recent action: {best_sig} (avg +{best_avg:.1f}/step)"


class RewardLedger:
    """Persistent JSONL log of reward signals per game + aggregate stats."""

    def __init__(self, data_dir: Path | None = None, game: str | None = None):
        if data_dir is None:
            from gfa.core.config import ConfigManager

            data_dir = ConfigManager().data_dir
        self.data_dir = Path(data_dir)
        self.game = game
        self._signals: list[RewardSignal] = []
        self._super = 0  # in-memory reward trend buffer index

    @property
    def _path(self) -> Path:
        name = (self.game or "default").replace("/", "_") + ".jsonl"
        return self.data_dir / "rewards" / name

    def load(self) -> int:
        """Load existing history; returns number of signals loaded."""
        p = self._path
        if not p.exists():
            self._signals = []
            return 0
        loaded: list[RewardSignal] = []
        for line in p.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
                loaded.append(RewardSignal(**{k: v for k, v in data.items()
                                              if k in RewardSignal.__dataclass_fields__}))
            except (json.JSONDecodeError, TypeError):
                continue
        self._signals = loaded
        return len(loaded)

    def record(self, signal: RewardSignal, commands: Any = None) -> None:
        """Append one signal (+ optional command context) to the ledger."""
        self._signals.append(signal)
        p = self._path
        p.parent.mkdir(parents=True, exist_ok=True)
        row = signal.to_dict()
        row["commands"] = command_signature(commands) if commands else ""
        row["recorded_at"] = time.time()
        with p.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, default=str) + "\n")

    def stats(self) -> dict[str, float]:
        rewards = [s.reward for s in self._signals]
        if not rewards:
            return {"count": 0, "total": 0.0, "mean": 0.0, "best": 0.0, "worst": 0.0}
        return {
            "count": len(rewards),
            "total": round(sum(rewards), 2),
            "mean": round(sum(rewards) / len(rewards), 2),
            "best": round(max(rewards), 2),
            "worst": round(min(rewards), 2),
        }

    def trend(self, n: int = 10) -> str:
        """Human-readable reward trend over the last n signals."""
        st = self.stats()
        if st["count"] == 0:
            return "no rewards recorded yet"
        return f"reward trend: mean {st['mean']:+.1f}/step over {int(st['count'])} steps (best {st['best']:+.1f})"

    def recent(self, n: int = 5) -> list[RewardSignal]:
        return self._signals[-n:]


class RewardTracker:
    """Facade: extractor + ledger + scorer for use inside the agent loop."""

    def __init__(self, data_dir: Path | None = None, game: str | None = None):
        self.game = game
        self.extractor = RewardExtractor()
        self.ledger = RewardLedger(data_dir, game=game)
        self.ledger.load()
        self.scorer = StrategyScorer()
        self._pending_signal: RewardSignal | None = None

    def observe(self, observation_text: str, step: int = 0) -> RewardSignal:
        """Call each step with the current observation summary."""
        self._pending_signal = self.extractor.observe(observation_text, step=step, game=self.game)
        return self._pending_signal

    def score_action(self, commands: Any) -> RewardSignal:
        """Call after executing `commands`: ledger + scorer update using the
        most recent observation's reward."""
        sig = command_signature(commands)
        reward = self._pending_signal.reward if self._pending_signal else 0.0
        self.scorer.update(sig, reward)
        if self._pending_signal is not None:
            self.ledger.record(self._pending_signal, commands=commands)
        return self._pending_signal  # type: ignore[return-value]

    def reward_context(self) -> str:
        """World-state line: reward trend + best action hint."""
        parts = [self.ledger.trend(10)]
        hint = self.scorer.best_hint()
        if hint:
            parts.append(hint)
        return "Reward: " + "; ".join(parts)

    @property
    def scorer_best(self) -> list[str]:
        return self.scorer.best()

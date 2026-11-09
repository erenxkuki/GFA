"""Reward signals: extract score/health/progress deltas from observations."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime

SCORE_RE = re.compile(r"(?i)score[:\s]*([\d,]+)")
HEALTH_RE = re.compile(r"(?i)health[:\s]*(\d+)")
PROGRESS_RE = re.compile(r"(?i)progress[:\s]*([\d.]+)")

# reward weights: catching up (gain) is good; losing health/score is bad
W_SCORE = 1.0
W_PROGRESS = 2.0
W_HEALTH = 1.0


@dataclass
class RewardSignal:
    """One step's reward: deltas of game metrics plus the scalar reward."""

    game: str | None = None
    step: int = 0
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    score: float | None = None
    health: float | None = None
    progress: float | None = None
    reward: float = 0.0
    source: str = "inferred"  # inferred | adapter | human

    def to_dict(self) -> dict:
        return asdict(self)

    def __str__(self) -> str:
        bits = []
        if self.score is not None:
            bits.append(f"score={self.score:g}")
        if self.health is not None:
            bits.append(f"health={self.health:g}")
        if self.progress is not None:
            bits.append(f"progress={self.progress:g}%")
        return f"Reward {self.reward:+.1f} ({', '.join(bits) or 'no metrics'})"


class RewardExtractor:
    """Parses score/health/progress from observation text and computes deltas.

    The first observation establishes a baseline (reward 0). Subsequent
    observations produce a reward from metric deltas:
    ``reward = Δscore*W_SCORE + Δprogress*W_PROGRESS + Δhealth*W_HEALTH``.
    Positive rewards = making progress; negative = losing ground.
    """

    def __init__(self, w_score: float = W_SCORE, w_progress: float = W_PROGRESS, w_health: float = W_HEALTH):
        self.w_score = w_score
        self.w_progress = w_progress
        self.w_health = w_health
        self._prev: RewardSignal | None = None

    @staticmethod
    def parse_metrics(text: str) -> dict[str, float]:
        metrics: dict[str, float] = {}
        if not text:
            return metrics
        m = SCORE_RE.search(text)
        if m:
            metrics["score"] = float(m.group(1).replace(",", ""))
        m = HEALTH_RE.search(text)
        if m:
            metrics["health"] = float(m.group(1))
        m = PROGRESS_RE.search(text)
        if m:
            metrics["progress"] = float(m.group(1))
        return metrics

    def observe(self, text: str, step: int = 0, game: str | None = None,
                source: str = "inferred") -> RewardSignal:
        """Build a reward signal for one observation (baseline on first call)."""
        metrics = self.parse_metrics(text)
        cur = RewardSignal(
            game=game,
            step=step,
            score=metrics.get("score"),
            health=metrics.get("health"),
            progress=metrics.get("progress"),
            reward=0.0,
            source=source,
        )
        if self._prev is not None:
            reward = 0.0
            if cur.score is not None and self._prev.score is not None:
                reward += (cur.score - self._prev.score) * self.w_score
            if cur.progress is not None and self._prev.progress is not None:
                reward += (cur.progress - self._prev.progress) * self.w_progress
            if cur.health is not None and self._prev.health is not None:
                reward += (cur.health - self._prev.health) * self.w_health
            cur.reward = round(reward, 2)
        self._prev = cur
        return cur

    def reset(self) -> None:
        self._prev = None

    @property
    def has_baseline(self) -> bool:
        return self._prev is not None

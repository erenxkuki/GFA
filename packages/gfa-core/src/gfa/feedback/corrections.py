"""Human-in-the-loop corrections: store, pending queue, application, and learning.

Feedback flow:
1. A human submits a correction (CLI ``gfa feedback add`` or UI): "prefer dodge
   when enemy is close" / "avoid going left here" / "that was good, repeat it".
2. The correction is stored in ``<data_dir>/feedback/corrections.jsonl`` as
   *pending* (``applied=False``).
3. During an agent run, :class:`FeedbackInjector` pops pending corrections for
   the current game and injects them into the world-state observation, so the
   model sees exactly what the human said.
4. After the model acts, the injector marks those corrections *applied* and the
   learning loop stores them as **high-confidence verified procedural memories**
   — corrections shape future behaviour even without a human in the loop.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

CORRECTION_TYPES = {"preference", "override", "avoid", "positive"}


@dataclass
class Correction:
    """One human correction, stored pending until the agent applies it."""

    id: str = field(default_factory=lambda: f"fb_{uuid.uuid4().hex[:12]}")
    type: str = "preference"  # preference | override | avoid | positive
    game: str | None = None
    text: str = ""
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    applied: bool = False
    applied_count: int = 0
    applied_at: str | None = None
    source: str = "cli"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Correction:
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})

    def __str__(self) -> str:
        return f"[{self.type}] {self.text}"


class FeedbackStore:
    """Persistent JSONL store of corrections under ``<data_dir>/feedback/``."""

    def __init__(self, data_dir: Path):
        self.data_dir = Path(data_dir)
        self._path = self.data_dir / "feedback" / "corrections.jsonl"

    def add(self, ctype: str, text: str, game: str | None = None, source: str = "cli") -> Correction:
        if ctype not in CORRECTION_TYPES:
            raise ValueError(f"unknown correction type '{ctype}'; expected one of {sorted(CORRECTION_TYPES)}")
        corr = Correction(type=ctype, text=text, game=game, source=source)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(corr.to_dict(), default=str) + "\n")
        return corr

    def _load(self) -> list[Correction]:
        if not self._path.exists():
            return []
        out: list[Correction] = []
        for line in self._path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                out.append(Correction.from_dict(json.loads(line)))
            except (json.JSONDecodeError, TypeError):
                continue
        return out

    def _save_all(self, items: list[Correction]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(
            "".join(json.dumps(c.to_dict(), default=str) + "\n" for c in items),
            encoding="utf-8",
        )

    def list(self, game: str | None = None, pending_only: bool = False) -> list[Correction]:
        items = self._load()
        if game:
            items = [c for c in items if c.game == game or c.game is None]
        if pending_only:
            items = [c for c in items if not c.applied]
        return items

    def pending(self, game: str | None = None) -> list[Correction]:
        return self.list(game=game, pending_only=True)

    def pop_pending(self, game: str | None = None) -> list[Correction]:
        """Return pending corrections and mark them consumed (applied is set
        separately by :meth:`mark_applied` after the model acts)."""
        items = self._load()
        consumed = []
        for c in items:
            if not c.applied and (game is None or c.game == game or c.game is None):
                consumed.append(c)
        return consumed

    def mark_applied(self, correction_ids: list[str]) -> None:
        """Mark corrections as applied (increments applied_count, sets applied_at)."""
        if not correction_ids:
            return
        items = self._load()
        changed = False
        for c in items:
            if c.id in set(correction_ids):
                c.applied = True
                c.applied_count += 1
                c.applied_at = datetime.now(UTC).isoformat()
                changed = True
        if changed:
            self._save_all(items)

    def delete(self, correction_id: str) -> bool:
        items = self._load()
        kept = [c for c in items if c.id != correction_id]
        if len(kept) == len(items):
            return False
        self._save_all(kept)
        return True

    def clear(self) -> int:
        n = len(self._load())
        if self._path.exists():
            self._path.unlink()
        return n


class LearningLoop:
    """Turns applied corrections into high-confidence procedural memories."""

    def __init__(self, memory_manager: Any):
        self.memory_manager = memory_manager

    def learn_from_correction(self, correction: Correction) -> None:
        """Store an applied correction as a verified procedural memory."""
        if self.memory_manager is None:
            return
        from gfa.memory.models import MemoryRecord

        content = f"Human feedback ({correction.type}): {correction.text}"
        rec = MemoryRecord(
            game_id=correction.game,
            category="procedural",
            memory_type="verified",
            content=content,
            confidence=0.9,
            verification_status="verified",
            tags=["human-feedback", correction.type],
        )
        self.memory_manager.add(rec)

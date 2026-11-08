"""High-level memory manager."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from gfa.core.config import ConfigManager
from gfa.memory.models import (
    MEMORY_CATEGORIES, MEMORY_TYPES, MemoryRecord, jaccard, tokenize,
)
from gfa.memory.storage import MemoryStorage


class WorkingMemory:
    """Temporary in-memory store for a session."""

    def __init__(self, capacity: int = 50):
        self.capacity = capacity
        self._items: list[dict[str, Any]] = []

    def add(self, item: dict[str, Any]) -> None:
        self._items.append(item)
        if len(self._items) > self.capacity:
            self._items = self._items[-self.capacity:]

    def all(self) -> list[dict[str, Any]]:
        return list(self._items)

    def clear(self) -> None:
        self._items.clear()


class MemoryManager:
    def __init__(self, config: ConfigManager):
        self.config = config
        db_path = config.data_dir / "memory" / "gfa_memory.db"
        self.storage = MemoryStorage(db_path)
        self.working = WorkingMemory()

    def close(self) -> None:
        self.storage.close()

    # ---- CRUD ----
    def add(self, memory: MemoryRecord) -> MemoryRecord:
        if memory.category not in MEMORY_CATEGORIES:
            memory.category = "episodic"
        if memory.memory_type not in MEMORY_TYPES:
            memory.memory_type = "hypothesis"
        self.storage.insert(memory)
        return memory

    def get(self, memory_id: str) -> MemoryRecord | None:
        rec = self.storage.get(memory_id)
        if rec is not None:
            rec.last_accessed = datetime.now(timezone.utc).isoformat()
            rec.access_count += 1
            self.storage.update(rec, create_version=False)
        return rec

    def update(self, memory_id: str, **fields: Any) -> MemoryRecord | None:
        rec = self.storage.get(memory_id)
        if rec is None:
            return None
        for k, v in fields.items():
            if hasattr(rec, k):
                setattr(rec, k, v)
        rec.updated_at = datetime.now(timezone.utc).isoformat()
        self.storage.update(rec, create_version=True)
        return rec

    def delete(self, memory_id: str) -> bool:
        return self.storage.delete(memory_id)

    def list(self, game_id: str | None = None, category: str | None = None, limit: int = 100) -> list[MemoryRecord]:
        return self.storage.list(game_id=game_id, category=category, limit=limit)

    # ---- Retrieval ----
    def retrieve(self, query: str, game_id: str | None = None, categories: list[str] | None = None,
                limit: int = 10) -> list[MemoryRecord]:
        candidates = self.storage.all_for_game(game_id) if game_id else self.storage.all_for_game(None)
        if categories:
            candidates = [c for c in candidates if c.category in categories]
        qtoks = tokenize(query)
        now = datetime.now(timezone.utc)
        scored = []
        for m in candidates:
            score = 0.0
            if game_id and m.game_id == game_id:
                score += 2.0
            if categories and m.category in categories:
                score += 0.5
            mtoks = tokenize(m.content)
            score += jaccard(qtoks, mtoks) * 3.0
            # confidence
            score += m.confidence
            # verification
            if m.verification_status == "verified":
                score += 0.5
            elif m.verification_status == "outdated":
                score -= 0.5
            # recency decay
            try:
                created = datetime.fromisoformat(m.created_at.replace("Z", "+00:00"))
                age_days = (now - created).total_seconds() / 86400.0
                score += max(0.0, 1.0 - age_days / 30.0) * 0.5
            except ValueError:
                pass
            # memory type reliability
            if m.memory_type == "verified":
                score += 0.3
            elif m.memory_type == "hypothesis":
                score -= 0.1
            scored.append((score, m))
        scored.sort(key=lambda x: x[0], reverse=True)
        out = []
        for score, m in scored[:limit]:
            m.last_accessed = datetime.now(timezone.utc).isoformat()
            m.access_count += 1
            out.append(m)
        # persist access bumps (best effort)
        for m in out:
            try:
                self.storage.update(m, create_version=False)
            except Exception:  # noqa: BLE001
                pass
        return out

    def retrieve_for_context(self, game_id: str | None, objective: str, limit: int = 8) -> list[MemoryRecord]:
        cats = ["semantic", "procedural", "spatial", "episodic"]
        return self.retrieve(objective or "", game_id=game_id, categories=cats, limit=limit)

    # ---- Dedup & compression ----
    def find_duplicates(self, game_id: str | None = None, threshold: float = 0.85) -> list[tuple[str, str]]:
        cands = self.storage.all_for_game(game_id)
        dups = []
        for i in range(len(cands)):
            for j in range(i + 1, len(cands)):
                if jaccard(tokenize(cands[i].content), tokenize(cands[j].content)) >= threshold:
                    dups.append((cands[i].id, cands[j].id))
        return dups

    def deduplicate(self, game_id: str | None = None, threshold: float = 0.85) -> int:
        dups = self.find_duplicates(game_id, threshold)
        removed = 0
        for a, b in dups:
            # keep a (higher confidence), remove b
            ra = self.storage.get(a)
            rb = self.storage.get(b)
            if ra is None or rb is None:
                continue
            if rb.confidence > ra.confidence:
                a, b = b, a
                ra, rb = rb, ra
            # merge tags/related
            ra.tags = sorted(set(ra.tags) | set(rb.tags))
            ra.related_ids = sorted(set(ra.related_ids) | set(rb.related_ids) | {rb.id})
            ra.updated_at = datetime.now(timezone.utc).isoformat()
            self.storage.update(ra, create_version=True)
            self.storage.delete(rb.id)
            removed += 1
        return removed

    def compress(self, game_id: str | None = None) -> dict[str, Any]:
        # 1. dedup
        removed = self.deduplicate(game_id)
        # 2. mark very old low-confidence memories as outdated (not delete)
        cands = self.storage.all_for_game(game_id)
        marked = 0
        now = datetime.now(timezone.utc)
        for m in cands:
            if m.verification_status == "outdated":
                continue
            try:
                created = datetime.fromisoformat(m.created_at.replace("Z", "+00:00"))
                age_days = (now - created).total_seconds() / 86400.0
            except ValueError:
                age_days = 0
            if age_days > 60 and m.confidence < 0.4 and m.access_count == 0:
                m.verification_status = "outdated"
                m.memory_type = "outdated"
                m.updated_at = datetime.now(timezone.utc).isoformat()
                self.storage.update(m, create_version=True)
                marked += 1
        return {"duplicates_removed": removed, "marked_outdated": marked}

    # ---- Export / import ----
    def export_json(self, path: Path, game_id: str | None = None) -> int:
        recs = self.storage.all_for_game(game_id)
        path.write_text(json.dumps([r.to_dict() for r in recs], indent=2, ensure_ascii=False), encoding="utf-8")
        return len(recs)

    def import_json(self, path: Path, overwrite: bool = False) -> int:
        data = json.loads(path.read_text(encoding="utf-8"))
        count = 0
        for item in data:
            rec = MemoryRecord.from_dict(item)
            existing = self.storage.get(rec.id)
            if existing is not None:
                if overwrite:
                    self.storage.delete(rec.id)
                    self.storage.insert(rec)
                    count += 1
            else:
                self.storage.insert(rec)
                count += 1
        return count

    def stats(self) -> dict[str, Any]:
        return self.storage.stats()

    def versions(self, memory_id: str) -> list[dict[str, Any]]:
        return self.storage.versions(memory_id)
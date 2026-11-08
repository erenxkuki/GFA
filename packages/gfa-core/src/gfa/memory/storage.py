"""SQLite-backed memory storage."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from gfa.memory.models import MemoryRecord


SCHEMA = """
CREATE TABLE IF NOT EXISTS memories (
    id TEXT PRIMARY KEY,
    game_id TEXT,
    category TEXT,
    memory_type TEXT,
    content TEXT,
    confidence REAL,
    verification_status TEXT,
    source_session TEXT,
    source_observation TEXT,
    game_version TEXT,
    adapter_version TEXT,
    model_provenance TEXT,
    created_at TEXT,
    updated_at TEXT,
    last_accessed TEXT,
    access_count INTEGER DEFAULT 0,
    tags TEXT,
    related_ids TEXT,
    metadata TEXT
);
CREATE TABLE IF NOT EXISTS memory_versions (
    memory_id TEXT,
    version INTEGER,
    content TEXT,
    metadata TEXT,
    created_at TEXT,
    PRIMARY KEY (memory_id, version)
);
CREATE INDEX IF NOT EXISTS idx_mem_game ON memories(game_id);
CREATE INDEX IF NOT EXISTS idx_mem_cat ON memories(category);
"""


class MemoryStorage:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(db_path))
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(SCHEMA)
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    def _row_to_record(self, row) -> MemoryRecord:
        return MemoryRecord(
            id=row["id"], game_id=row["game_id"], category=row["category"],
            memory_type=row["memory_type"], content=row["content"],
            confidence=row["confidence"], verification_status=row["verification_status"],
            source_session=row["source_session"], source_observation=row["source_observation"],
            game_version=row["game_version"], adapter_version=row["adapter_version"],
            model_provenance=row["model_provenance"], created_at=row["created_at"],
            updated_at=row["updated_at"], last_accessed=row["last_accessed"],
            access_count=row["access_count"] or 0,
            tags=json.loads(row["tags"] or "[]"),
            related_ids=json.loads(row["related_ids"] or "[]"),
            metadata=json.loads(row["metadata"] or "{}"),
        )

    def insert(self, m: MemoryRecord) -> None:
        self._conn.execute(
            """INSERT INTO memories (id,game_id,category,memory_type,content,confidence,verification_status,
               source_session,source_observation,game_version,adapter_version,model_provenance,created_at,
               updated_at,last_accessed,access_count,tags,related_ids,metadata)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (m.id, m.game_id, m.category, m.memory_type, m.content, m.confidence, m.verification_status,
             m.source_session, m.source_observation, m.game_version, m.adapter_version, m.model_provenance,
             m.created_at, m.updated_at, m.last_accessed, m.access_count, json.dumps(m.tags),
             json.dumps(m.related_ids), json.dumps(m.metadata)),
        )
        self._conn.commit()

    def update(self, m: MemoryRecord, create_version: bool = True) -> None:
        if create_version:
            # store previous version
            cur = self._conn.execute("SELECT content, metadata FROM memories WHERE id=?", (m.id,)).fetchone()
            if cur is not None:
                v = self._conn.execute("SELECT COALESCE(MAX(version),0)+1 FROM memory_versions WHERE memory_id=?", (m.id,)).fetchone()[0]
                self._conn.execute(
                    "INSERT INTO memory_versions (memory_id,version,content,metadata,created_at) VALUES (?,?,?,?,?)",
                    (m.id, v, cur["content"], cur["metadata"], m.updated_at),
                )
        self._conn.execute(
            """UPDATE memories SET game_id=?,category=?,memory_type=?,content=?,confidence=?,verification_status=?,
               source_session=?,source_observation=?,game_version=?,adapter_version=?,model_provenance=?,
               updated_at=?,last_accessed=?,access_count=?,tags=?,related_ids=?,metadata=? WHERE id=?""",
            (m.game_id, m.category, m.memory_type, m.content, m.confidence, m.verification_status,
             m.source_session, m.source_observation, m.game_version, m.adapter_version, m.model_provenance,
             m.updated_at, m.last_accessed, m.access_count, json.dumps(m.tags), json.dumps(m.related_ids),
             json.dumps(m.metadata), m.id),
        )
        self._conn.commit()

    def delete(self, memory_id: str) -> bool:
        cur = self._conn.execute("DELETE FROM memories WHERE id=?", (memory_id,))
        self._conn.execute("DELETE FROM memory_versions WHERE memory_id=?", (memory_id,))
        self._conn.commit()
        return cur.rowcount > 0

    def get(self, memory_id: str) -> MemoryRecord | None:
        row = self._conn.execute("SELECT * FROM memories WHERE id=?", (memory_id,)).fetchone()
        if row is None:
            return None
        rec = self._row_to_record(row)
        # bump access
        self._conn.execute("UPDATE memories SET last_accessed=?, access_count=access_count+1 WHERE id=?",
                           (rec.last_accessed or rec.created_at, memory_id))  # placeholder
        self._conn.commit()
        return rec

    def list(self, game_id: str | None = None, category: str | None = None, limit: int = 100) -> list[MemoryRecord]:
        q = "SELECT * FROM memories WHERE 1=1"
        params: list[Any] = []
        if game_id:
            q += " AND game_id=?"
            params.append(game_id)
        if category:
            q += " AND category=?"
            params.append(category)
        q += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        rows = self._conn.execute(q, params).fetchall()
        return [self._row_to_record(r) for r in rows]

    def search_text(self, query: str, game_id: str | None = None, limit: int = 50) -> list[MemoryRecord]:
        q = "SELECT * FROM memories WHERE content LIKE ?"
        params: list[Any] = [f"%{query}%"]
        if game_id:
            q += " AND game_id=?"
            params.append(game_id)
        q += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        rows = self._conn.execute(q, params).fetchall()
        return [self._row_to_record(r) for r in rows]

    def all_for_game(self, game_id: str | None = None) -> list[MemoryRecord]:
        if game_id:
            rows = self._conn.execute("SELECT * FROM memories WHERE game_id=?", (game_id,)).fetchall()
        else:
            rows = self._conn.execute("SELECT * FROM memories").fetchall()
        return [self._row_to_record(r) for r in rows]

    def versions(self, memory_id: str) -> list[dict[str, Any]]:
        rows = self._conn.execute(
            "SELECT * FROM memory_versions WHERE memory_id=? ORDER BY version", (memory_id,)).fetchall()
        return [dict(r) for r in rows]

    def stats(self) -> dict[str, Any]:
        total = self._conn.execute("SELECT COUNT(*) FROM memories").fetchone()[0]
        by_cat = {}
        for r in self._conn.execute("SELECT category, COUNT(*) c FROM memories GROUP BY category"):
            by_cat[r["category"]] = r["c"]
        return {"total": total, "by_category": by_cat}
"""Session management for GFA."""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any

from gfa.core.config import ConfigManager
from gfa.shared.errors import SessionError


class SessionStatus(StrEnum):
    CREATED = "created"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    INTERRUPTED = "interrupted"


@dataclass
class SessionRecord:
    session_id: str
    game: str | None = None
    model_provider: str | None = None
    model_id: str | None = None
    adapter_id: str | None = None
    adapter_version: str | None = None
    gcl_version: str = "gcl-v1"
    status: str = SessionStatus.CREATED.value
    started_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    ended_at: str | None = None
    action_count: int = 0
    error_count: int = 0
    errors: list[str] = field(default_factory=list)
    action_history: list[dict[str, Any]] = field(default_factory=list)
    summary: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SessionRecord:
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


class SessionManager:
    def __init__(self, config: ConfigManager):
        self.config = config
        self._dir = config.data_dir / "sessions"
        self._dir.mkdir(parents=True, exist_ok=True)
        self._sessions: dict[str, SessionRecord] = {}
        self._load_all()

    def _path(self, session_id: str) -> Path:
        return self._dir / f"{session_id}.json"

    def _load_all(self) -> None:
        for p in self._dir.glob("*.json"):
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
                rec = SessionRecord.from_dict(data)
                self._sessions[rec.session_id] = rec
            except (OSError, json.JSONDecodeError, TypeError):
                continue

    def create(self, game: str | None = None, model_provider: str | None = None,
               model_id: str | None = None, adapter_id: str | None = None,
               **metadata: Any) -> SessionRecord:
        sid = f"ses_{uuid.uuid4().hex[:12]}"
        rec = SessionRecord(session_id=sid, game=game, model_provider=model_provider,
                            model_id=model_id, adapter_id=adapter_id, metadata=metadata)
        self._sessions[sid] = rec
        self._persist(rec)
        return rec

    def get(self, session_id: str) -> SessionRecord:
        rec = self._sessions.get(session_id)
        if rec is None:
            raise SessionError(f"Session not found: {session_id}", code="session_not_found")
        return rec

    def list(self, status: str | None = None, limit: int = 100) -> list[SessionRecord]:
        items = list(self._sessions.values())
        if status:
            items = [s for s in items if s.status == status]
        items.sort(key=lambda s: s.started_at, reverse=True)
        return items[:limit]

    def update_status(self, session_id: str, status: SessionStatus | str) -> SessionRecord:
        rec = self.get(session_id)
        rec.status = status.value if isinstance(status, SessionStatus) else str(status)
        if rec.status in (SessionStatus.COMPLETED.value, SessionStatus.FAILED.value,
                          SessionStatus.INTERRUPTED.value):
            rec.ended_at = datetime.now(UTC).isoformat()
        self._persist(rec)
        return rec

    def record_action(self, session_id: str, action: dict[str, Any], result: dict[str, Any] | None = None) -> None:
        rec = self.get(session_id)
        entry = {"timestamp": datetime.now(UTC).isoformat(), "action": action, "result": result}
        rec.action_history.append(entry)
        rec.action_count += 1
        self._persist(rec)

    def record_error(self, session_id: str, message: str) -> None:
        rec = self.get(session_id)
        rec.errors.append(message)
        rec.error_count += 1
        self._persist(rec)

    def finalize(self, session_id: str, summary: str | None = None) -> SessionRecord:
        rec = self.get(session_id)
        rec.summary = summary
        rec.ended_at = datetime.now(UTC).isoformat()
        if rec.status == SessionStatus.RUNNING.value:
            rec.status = SessionStatus.COMPLETED.value
        self._persist(rec)
        return rec

    def delete(self, session_id: str) -> bool:
        rec = self._sessions.pop(session_id, None)
        if rec is None:
            return False
        p = self._path(session_id)
        if p.exists():
            p.unlink()
        return True

    def _persist(self, rec: SessionRecord) -> None:
        self._path(rec.session_id).write_text(
            json.dumps(rec.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8"
        )
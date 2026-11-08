"""Memory data models."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
import uuid

MEMORY_CATEGORIES = {"working", "episodic", "semantic", "procedural", "spatial"}
MEMORY_TYPES = {"observed_fact", "inference", "hypothesis", "verified", "outdated"}
VERIFICATION_STATUSES = {"unverified", "verified", "contradicted", "outdated"}


@dataclass
class MemoryRecord:
    id: str = field(default_factory=lambda: f"mem_{uuid.uuid4().hex[:12]}")
    game_id: str | None = None
    category: str = "episodic"
    memory_type: str = "hypothesis"
    content: str = ""
    confidence: float = 0.5
    verification_status: str = "unverified"
    source_session: str | None = None
    source_observation: str | None = None
    game_version: str | None = None
    adapter_version: str | None = None
    model_provenance: str | None = None
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    last_accessed: str | None = None
    access_count: int = 0
    tags: list[str] = field(default_factory=list)
    related_ids: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id, "game_id": self.game_id, "category": self.category,
            "memory_type": self.memory_type, "content": self.content,
            "confidence": self.confidence, "verification_status": self.verification_status,
            "source_session": self.source_session, "source_observation": self.source_observation,
            "game_version": self.game_version, "adapter_version": self.adapter_version,
            "model_provenance": self.model_provenance, "created_at": self.created_at,
            "updated_at": self.updated_at, "last_accessed": self.last_accessed,
            "access_count": self.access_count, "tags": self.tags,
            "related_ids": self.related_ids, "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MemoryRecord":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


def tokenize(text: str) -> set[str]:
    import re
    return set(re.findall(r"[a-zA-Z0-9_]+", text.lower()))


def jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)
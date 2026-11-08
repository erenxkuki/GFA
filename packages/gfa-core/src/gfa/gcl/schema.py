"""GCL schemas."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any


class CommandStatus(StrEnum):
    PENDING = "pending"
    VALIDATED = "validated"
    EXECUTING = "executing"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    REJECTED = "rejected"
    CANCELLED = "cancelled"
    TIMED_OUT = "timed_out"


@dataclass
class Command:
    type: str
    id: str | None = None
    params: dict[str, Any] = field(default_factory=dict)
    # convenience: top-level fields merged into params during parsing
    raw: dict[str, Any] = field(default_factory=dict, repr=False)

    def get(self, key: str, default: Any = None) -> Any:
        if key in self.params:
            return self.params[key]
        return self.raw.get(key, default)


@dataclass
class CommandResult:
    command_id: str | None
    type: str
    status: CommandStatus
    message: str = ""
    data: dict[str, Any] = field(default_factory=dict)
    started_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    ended_at: str | None = None
    duration_ms: float | None = None


@dataclass
class CommandBatch:
    protocol: str
    commands: list[Command]
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ValidationResult:
    ok: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
"""Macro data models: recorded input sequences with timing."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


@dataclass
class MacroStep:
    """One step: a batch of GCL commands and the delay BEFORE executing it."""

    commands: list[dict[str, Any]] = field(default_factory=list)
    delay_ms: float = 0.0  # delay before this step (relative to previous step end)

    def to_dict(self) -> dict[str, Any]:
        return {"commands": self.commands, "delay_ms": self.delay_ms}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MacroStep:
        return cls(
            commands=[dict(c) for c in data.get("commands", []) if isinstance(c, dict)],
            delay_ms=float(data.get("delay_ms", 0.0) or 0.0),
        )


@dataclass
class Macro:
    """A named, replayable input sequence."""

    name: str
    steps: list[MacroStep] = field(default_factory=list)
    game: str | None = None
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    description: str = ""
    source: str = "agent"  # agent | cli | manual

    @property
    def total_delay_ms(self) -> float:
        return sum(s.delay_ms for s in self.steps)

    @property
    def command_count(self) -> int:
        return sum(len(s.commands) for s in self.steps)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "game": self.game,
            "created_at": self.created_at,
            "description": self.description,
            "source": self.source,
            "steps": [s.to_dict() for s in self.steps],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Macro:
        return cls(
            name=data.get("name", ""),
            steps=[MacroStep.from_dict(s) for s in data.get("steps", []) if isinstance(s, dict)],
            game=data.get("game"),
            created_at=data.get("created_at", datetime.now(UTC).isoformat()),
            description=data.get("description", ""),
            source=data.get("source", "manual"),
        )

    def to_text(self) -> str:
        lines = [
            f"Macro '{self.name}' ({self.command_count} commands, {len(self.steps)} steps, "
            f"{self.total_delay_ms:.0f}ms total delay)",
        ]
        if self.game:
            lines.append(f"  Game: {self.game}")
        if self.description:
            lines.append(f"  Description: {self.description}")
        for i, s in enumerate(self.steps):
            cmds = ", ".join(c.get("type", "?") for c in s.commands)
            lines.append(f"  step {i:2d} (+{s.delay_ms:6.0f}ms): {cmds}")
        return "\n".join(lines)

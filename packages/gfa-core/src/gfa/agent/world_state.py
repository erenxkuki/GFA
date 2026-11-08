"""World state representation."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class WorldState:
    session_id: str | None = None
    game: str | None = None
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    current_context: str = "unknown"
    visible_objects: list[dict[str, Any]] = field(default_factory=list)
    retrieved_memories: list[dict[str, Any]] = field(default_factory=list)
    objectives: list[str] = field(default_factory=list)
    recent_actions: list[dict[str, Any]] = field(default_factory=list)
    known_constraints: list[str] = field(default_factory=list)
    uncertainty: list[str] = field(default_factory=list)
    observation_summary: str = ""
    available_capabilities: list[str] = field(default_factory=list)

    def to_prompt_text(self) -> str:
        lines = []
        lines.append(f"Context: {self.current_context}")
        if self.objectives:
            lines.append("Objectives: " + "; ".join(self.objectives))
        if self.visible_objects:
            lines.append("Visible objects: " + str(self.visible_objects))
        if self.retrieved_memories:
            lines.append("Relevant memories: " + str(self.retrieved_memories))
        if self.recent_actions:
            lines.append("Recent actions: " + str(self.recent_actions[-5:]))
        if self.known_constraints:
            lines.append("Constraints: " + "; ".join(self.known_constraints))
        if self.uncertainty:
            lines.append("Uncertainty: " + "; ".join(self.uncertainty))
        if self.observation_summary:
            lines.append("Observation: " + self.observation_summary)
        return "\n".join(lines)
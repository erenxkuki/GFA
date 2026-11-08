"""Experience extraction: decides what to store as memory."""

from __future__ import annotations

from typing import Any

from gfa.memory.models import MemoryRecord


class ExperienceExtractor:
    def __init__(self, game_id: str | None = None, session_id: str | None = None, model_provenance: str | None = None):
        self.game_id = game_id
        self.session_id = session_id
        self.model_provenance = model_provenance

    def extract(self, experience: dict[str, Any]) -> list[MemoryRecord]:
        """Experience dict may contain: action, result, observation, objective, objects, location, success."""
        out: list[MemoryRecord] = []
        action = experience.get("action")
        result = experience.get("result") or {}
        success = experience.get("success", result.get("ok", False) if isinstance(result, dict) else False)
        objective = experience.get("objective")

        # Successful strategy -> procedural
        if success and action:
            content = f"Strategy: action {action} succeeded"
            if objective:
                content += f" while pursuing '{objective}'"
            if experience.get("context"):
                content += f". Context: {experience['context']}"
            out.append(MemoryRecord(
                game_id=self.game_id, category="procedural", memory_type="verified" if success else "hypothesis",
                content=content, confidence=0.7 if success else 0.4,
                source_session=self.session_id, model_provenance=self.model_provenance,
                metadata={"action": action, "result": result},
            ))

        # Failure -> episodic
        if not success and action:
            content = f"Failure: action {action} did not succeed"
            if result:
                content += f". Result: {result}"
            out.append(MemoryRecord(
                game_id=self.game_id, category="episodic", memory_type="observed_fact",
                content=content, confidence=0.6,
                source_session=self.session_id, model_provenance=self.model_provenance,
                metadata={"action": action, "result": result},
            ))

        # Newly discovered object -> semantic
        for obj in experience.get("new_objects", []) or []:
            out.append(MemoryRecord(
                game_id=self.game_id, category="semantic", memory_type="hypothesis",
                content=f"Discovered object: {obj}", confidence=0.5,
                source_session=self.session_id, model_provenance=self.model_provenance,
            ))

        # Location -> spatial
        if experience.get("location"):
            out.append(MemoryRecord(
                game_id=self.game_id, category="spatial", memory_type="observed_fact",
                content=f"Visited location: {experience['location']}", confidence=0.6,
                source_session=self.session_id, model_provenance=self.model_provenance,
            ))

        # Important fact from observation text
        if experience.get("fact"):
            out.append(MemoryRecord(
                game_id=self.game_id, category="semantic", memory_type="hypothesis",
                content=experience["fact"], confidence=0.5,
                source_session=self.session_id, model_provenance=self.model_provenance,
            ))

        return out
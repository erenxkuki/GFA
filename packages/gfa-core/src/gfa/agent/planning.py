"""Planning engine for short-horizon action plans."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from gfa.gcl.parser import parse_batch
from gfa.gcl.schema import Command, CommandBatch


@dataclass
class Plan:
    goal: str
    batches: list[CommandBatch] = field(default_factory=list)
    current: int = 0
    invalidated: bool = False

    def has_next(self) -> bool:
        return self.current < len(self.batches) and not self.invalidated

    def next_batch(self) -> CommandBatch | None:
        if not self.has_next():
            return None
        b = self.batches[self.current]
        self.current += 1
        return b

    def invalidate(self) -> None:
        self.invalidated = True


class PlanningEngine:
    def __init__(self):
        self.current_plan: Plan | None = None

    def create_plan(self, goal: str, commands: list[dict[str, Any]] | CommandBatch) -> Plan:
        if isinstance(commands, CommandBatch):
            batches = [commands]
        else:
            # commands may be list of command dicts (one batch) or list of batches
            if commands and isinstance(commands[0], list):
                batches = [parse_batch({"protocol": "gcl-v1", "commands": b}) for b in commands]
            elif commands and isinstance(commands[0], dict) and "type" in commands[0]:
                batches = [parse_batch({"protocol": "gcl-v1", "commands": commands})]
            else:
                batches = []
        plan = Plan(goal=goal, batches=batches)
        self.current_plan = plan
        return plan

    def replan(self, goal: str, commands) -> Plan:
        if self.current_plan is not None:
            self.current_plan.invalidate()
        return self.create_plan(goal, commands)

    def clear(self) -> None:
        self.current_plan = None
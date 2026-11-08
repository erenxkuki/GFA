"""AI Arena: run and compare multiple agents."""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any

from gfa.agent.agent import GameplayAgent


@dataclass
class MatchResult:
    agent_name: str
    success: bool
    steps: int
    reason: str
    duration_seconds: float
    action_history: list[dict[str, Any]] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


@dataclass
class Match:
    match_id: str
    game: str | None
    objective: str
    results: list[MatchResult] = field(default_factory=list)
    started_at: float = field(default_factory=time.time)
    ended_at: float | None = None


class Arena:
    def __init__(self):
        self.matches: dict[str, Match] = {}

    def create_match(self, game: str | None, objective: str) -> Match:
        mid = f"match_{len(self.matches)+1}"
        m = Match(match_id=mid, game=game, objective=objective)
        self.matches[mid] = m
        return m

    async def run_agent(self, match: Match, name: str, agent: GameplayAgent, objective: str, game: str | None) -> MatchResult:
        start = time.time()
        res = await agent.run(objective, game=game)
        dur = time.time() - start
        mr = MatchResult(agent_name=name, success=res.success, steps=res.steps, reason=res.reason,
                         duration_seconds=dur, action_history=res.action_history, errors=res.errors)
        match.results.append(mr)
        return mr

    async def run_match(self, match: Match, agents: dict[str, GameplayAgent], objective: str | None = None) -> Match:
        obj = objective or match.objective
        # run sequentially to share environment safely
        for name, agent in agents.items():
            await self.run_agent(match, name, agent, obj, match.game)
        match.ended_at = time.time()
        return match

    def leaderboard(self) -> list[dict[str, Any]]:
        rows = []
        for m in self.matches.values():
            for r in m.results:
                rows.append({"match": m.match_id, "agent": r.agent_name, "success": r.success,
                            "steps": r.steps, "duration": round(r.duration_seconds, 2)})
        rows.sort(key=lambda x: (not x["success"], x["steps"], x["duration"]))
        return rows
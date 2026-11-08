import asyncio

from gfa.agent.agent import AgentResult
from gfa.arena.arena import Arena


class FakeAgent:
    def __init__(self, success=True, steps=3):
        self.success = success
        self.steps = steps

    async def run(self, objective, game=None):
        return AgentResult(success=self.success, steps=self.steps, reason="done", action_history=[], errors=[])


def test_arena_match_and_leaderboard():
    async def run():
        arena = Arena()
        match = arena.create_match(game="Sandbox", objective="reach target")
        agents = {"A": FakeAgent(success=True, steps=2), "B": FakeAgent(success=False, steps=5)}
        await arena.run_match(match, agents)
        assert len(match.results) == 2
        lb = arena.leaderboard()
        assert lb[0]["agent"] == "A"
    asyncio.run(run())
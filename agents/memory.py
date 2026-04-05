"""
agents/memory.py — Per-agent cross-cycle memory store.
Agents use this to remember cleared zones, blocked routes,
resource consumption rates, and previous messages.
"""
from __future__ import annotations

from typing import Any, Optional

from agents.models import AgentMemoryEntry


class AgentMemory:
    """
    Lightweight key-value store per agent, indexed by cycle number.
    Supports recall of full history or just the latest value.
    """

    def __init__(self):
        self._store: dict[str, list[AgentMemoryEntry]] = {}

    def store(self, agent: str, key: str, value: Any, cycle: int) -> None:
        full_key = f"{agent}::{key}"
        if full_key not in self._store:
            self._store[full_key] = []
        self._store[full_key].append(
            AgentMemoryEntry(cycle_num=cycle, agent_name=agent, key=key, value=value)
        )

    def recall(self, agent: str, key: str) -> list[AgentMemoryEntry]:
        return list(self._store.get(f"{agent}::{key}", []))

    def recall_latest(self, agent: str, key: str) -> Optional[Any]:
        entries = self.recall(agent, key)
        return entries[-1].value if entries else None

    def recall_all_for_agent(self, agent: str) -> dict[str, list[Any]]:
        result: dict[str, list[Any]] = {}
        prefix = f"{agent}::"
        for full_key, entries in self._store.items():
            if full_key.startswith(prefix):
                short_key = full_key[len(prefix):]
                result[short_key] = [e.value for e in entries]
        return result

    def to_dict(self) -> dict:
        return {
            k: [
                {
                    "cycle_num": e.cycle_num,
                    "agent_name": e.agent_name,
                    "key": e.key,
                    "value": e.value,
                }
                for e in v
            ]
            for k, v in self._store.items()
        }

    @classmethod
    def from_dict(cls, data: dict) -> "AgentMemory":
        m = cls()
        for full_key, entries in data.items():
            m._store[full_key] = [
                AgentMemoryEntry(
                    cycle_num=e["cycle_num"],
                    agent_name=e["agent_name"],
                    key=e["key"],
                    value=e["value"],
                )
                for e in entries
            ]
        return m

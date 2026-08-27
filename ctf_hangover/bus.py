"""Insight bus — shared findings across all running solvers."""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field


@dataclass
class Insight:
    challenge: str
    model: str
    kind: str  # "finding" | "approach" | "dead-end" | "operator" | "guidance"
    text: str
    ts: float = field(default_factory=time.time)


class InsightBus:
    """Async pub/sub for cross-solver intelligence."""

    def __init__(self) -> None:
        self._insights: list[Insight] = []
        self._subs: dict[str, list[asyncio.Queue[Insight]]] = {}
        self._lock = asyncio.Lock()

    async def publish(self, insight: Insight) -> None:
        async with self._lock:
            self._insights.append(insight)
            for q in self._subs.get(insight.challenge, []):
                q.put_nowait(insight)
            for q in self._subs.get("*", []):
                q.put_nowait(insight)

    async def recent(self, challenge: str, limit: int = 20) -> list[Insight]:
        async with self._lock:
            matched = [
                i for i in self._insights
                if i.challenge in (challenge, "*")
            ]
            return matched[-limit:]

    async def all_for(self, challenge: str) -> list[Insight]:
        async with self._lock:
            return [i for i in self._insights if i.challenge == challenge]

    def subscribe(self, challenge: str) -> asyncio.Queue[Insight]:
        q: asyncio.Queue[Insight] = asyncio.Queue()
        self._subs.setdefault(challenge, []).append(q)
        return q

    def unsubscribe(self, challenge: str, q: asyncio.Queue[Insight]) -> None:
        if challenge in self._subs:
            try:
                self._subs[challenge].remove(q)
            except ValueError:
                pass

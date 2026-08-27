"""Solver swarm — race multiple models on one challenge."""

from __future__ import annotations

import asyncio
import logging

from ..bus import InsightBus
from ..config import settings
from ..router import RouterClient
from ..routing import route_models
from .core import Solver, SolverResult

log = logging.getLogger(__name__)


class Swarm:
    """Run N models in parallel against one challenge. First flag wins."""

    def __init__(
        self,
        challenge_name: str,
        challenge_prompt: str,
        category: str,
        bus: InsightBus,
        available_models: list[str] | None = None,
        router: RouterClient | None = None,
    ) -> None:
        self.challenge_name = challenge_name
        self.prompt = challenge_prompt
        self.category = category
        self.bus = bus
        self.router = router or RouterClient()
        self.available = available_models or settings.model_list

        if settings.enable_smart_routing:
            self.models = route_models(
                category, self.available, settings.max_models_per_swarm,
            )
        else:
            self.models = self.available[: settings.max_models_per_swarm]

        self.solvers: list[Solver] = []
        self.result: SolverResult | None = None

    async def run(self) -> SolverResult:
        """Race all models. Return the first solver that finds a flag."""
        log.info(
            "swarm %s: racing %d models: %s",
            self.challenge_name, len(self.models), self.models,
        )

        # Build solvers with fallback chains
        for i, model in enumerate(self.models):
            fallbacks = [m for m in self.models if m != model]
            self.solvers.append(Solver(
                model=model,
                challenge_name=self.challenge_name,
                challenge_prompt=self.prompt,
                bus=self.bus,
                fallbacks=fallbacks,
                router=self.router,
            ))

        tasks = [asyncio.create_task(s.run()) for s in self.solvers]

        # Wait for first solver to find a flag
        done, pending = await asyncio.wait(
            tasks, return_when=asyncio.FIRST_COMPLETED,
        )

        # Check if any completed task found a flag
        winner: SolverResult | None = None
        for t in done:
            r = t.result()
            if r.flag:
                winner = r
                break

        if winner:
            # Cancel remaining solvers
            for s in self.solvers:
                s.stop()
            for t in pending:
                t.cancel()
            await asyncio.gather(*pending, return_exceptions=True)
            self.result = winner
        else:
            # No flag yet — keep waiting
            if pending:
                done2, pending2 = await asyncio.wait(
                    pending, return_when=asyncio.FIRST_COMPLETED,
                )
                for t in done2:
                    r = t.result()
                    if r.flag:
                        winner = r
                        break
                if winner:
                    for s in self.solvers:
                        s.stop()
                    for t in pending2:
                        t.cancel()
                    await asyncio.gather(*pending2, return_exceptions=True)
                    self.result = winner

        if not self.result:
            # All solvers finished without finding a flag
            self.result = max(
                (t.result() for t in tasks),
                key=lambda r: r.tokens_used,
                default=SolverResult(challenge=self.challenge_name, model="none", status="failed"),
            )

        return self.result

    def stop(self) -> None:
        for s in self.solvers:
            s.stop()

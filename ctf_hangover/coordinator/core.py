"""Coordinator — orchestrator LLM that monitors swarms and provides guidance."""

from __future__ import annotations

import asyncio
import logging
import time

from ..bus import Insight, InsightBus
from ..config import settings
from ..router import RouterClient

log = logging.getLogger(__name__)

COORDINATOR_SYSTEM = """\
You are the CTF competition coordinator. You monitor all active solver swarms \
and provide targeted technical guidance when they get stuck.

Your responsibilities:
1. READ solver traces and identify when a swarm is going in circles.
2. PROVIDE specific, actionable guidance (not generic advice).
3. RECOGNIZE when a challenge is likely solved and tell swarms to stop.
4. SHARE cross-challenge insights when relevant.

When providing guidance, be SPECIFIC:
- Name the exact tool or technique to try next
- Reference specific findings from the traces
- Point out when solvers are repeating the same failed approach
"""


class Coordinator:
    """Monitors swarms, detects stuck states, injects guidance."""

    def __init__(
        self,
        bus: InsightBus,
        router: RouterClient | None = None,
        model: str | None = None,
    ) -> None:
        self.bus = bus
        self.router = router or RouterClient()
        self.model = model or settings.coordinator_model
        self._stop = asyncio.Event()
        self._active_challenges: dict[str, float] = {}  # name → last_activity_ts

    async def run(self) -> None:
        """Main coordinator loop. Runs until stopped."""
        log.info("coordinator started (model=%s)", self.model)
        q = self.bus.subscribe("*")

        try:
            while not self._stop.is_set():
                try:
                    insight = await asyncio.wait_for(q.get(), timeout=5.0)
                    self._active_challenges[insight.challenge] = time.time()

                    # Check for stuck swarms
                    await self._check_stuck()

                except asyncio.TimeoutError:
                    await self._check_stuck()
        finally:
            self.bus.unsubscribe("*", q)

    async def _check_stuck(self) -> None:
        """Detect challenges with no recent progress and send guidance."""
        now = time.time()
        stuck_threshold = settings.swarm_stuck_minutes * 60

        for challenge, last_activity in list(self._active_challenges.items()):
            if now - last_activity > stuck_threshold:
                await self._send_guidance(challenge)
                # Reset timer so we don't spam
                self._active_challenges[challenge] = now

    async def _send_guidance(self, challenge: str) -> None:
        """Ask coordinator LLM for guidance based on recent solver activity."""
        insights = await self.bus.recent(challenge, limit=20)
        if not insights:
            return

        trace = "\n".join(
            f"[{i.model}] [{i.kind}] {i.text}" for i in insights
        )

        try:
            _, resp = await self.router.chat(
                model=self.model,
                messages=[
                    {"role": "system", "content": COORDINATOR_SYSTEM},
                    {
                        "role": "user",
                        "content": (
                            f"Challenge '{challenge}' has been stuck for "
                            f"{settings.swarm_stuck_minutes}+ minutes. "
                            f"Recent solver activity:\n\n{trace}\n\n"
                            "Provide specific guidance to unblock the solvers."
                        ),
                    },
                ],
                temperature=0.5,
                max_tokens=1024,
            )

            guidance = resp["choices"][0]["message"].get("content", "")
            if guidance:
                await self.bus.publish(Insight(
                    challenge=challenge,
                    model="coordinator",
                    kind="guidance",
                    text=guidance,
                ))
                log.info("coordinator guidance for %s: %s", challenge, guidance[:100])

        except Exception as e:
            log.error("coordinator guidance failed: %s", e)

    async def suggest_approach(self, challenge: str, prompt: str, category: str) -> str:
        """Ask coordinator for an initial approach strategy."""
        try:
            _, resp = await self.router.chat(
                model=self.model,
                messages=[
                    {"role": "system", "content": COORDINATOR_SYSTEM},
                    {
                        "role": "user",
                        "content": (
                            f"New {category} challenge: {challenge}\n\n"
                            f"Description:\n{prompt}\n\n"
                            "Suggest the best initial approach and tools."
                        ),
                    },
                ],
                temperature=0.5,
                max_tokens=1024,
            )
            return resp["choices"][0]["message"].get("content", "")
        except Exception as e:
            log.error("coordinator suggest failed: %s", e)
            return ""

    def stop(self) -> None:
        self._stop.set()

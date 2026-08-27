"""Overkill features — self-play, auto-decompose, cross-pollination."""

from __future__ import annotations

import asyncio
import logging

from .bus import Insight, InsightBus
from .config import settings
from .router import RouterClient

log = logging.getLogger(__name__)


async def selfplay_variants(
    prompt: str,
    model: str,
    n: int = 3,
    router: RouterClient | None = None,
) -> list[str]:
    """Generate N alternative interpretations of a challenge via self-play.

    Each variant is a paraphrased/reframed version of the challenge prompt
    with a different solving angle, generated at high temperature.
    """
    router = router or RouterClient()
    variants: list[str] = []

    async def _gen(i: int) -> None:
        try:
            _, resp = await router.chat(
                model=model,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a CTF challenge analyzer. Given a challenge "
                            "description, generate an alternative interpretation "
                            "with a different solving angle. Focus on a different "
                            "attack vector than the obvious one."
                        ),
                    },
                    {
                        "role": "user",
                        "content": f"Challenge:\n{prompt}\n\nGive an alternative interpretation #{i+1}.",
                    },
                ],
                temperature=1.0,
                max_tokens=512,
            )
            text = resp["choices"][0]["message"].get("content", "")
            if text:
                variants.append(text)
        except Exception as e:
            log.error("selfplay variant %d failed: %s", i, e)

    await asyncio.gather(*[_gen(i) for i in range(n)])
    return variants


async def auto_decompose(
    challenge_name: str,
    prompt: str,
    category: str,
    model: str,
    router: RouterClient | None = None,
) -> list[dict[str, str]]:
    """Break a complex challenge into sub-tasks that can run in parallel.

    Returns a list of {"name": ..., "prompt": ..., "category": ...} dicts.
    """
    router = router or RouterClient()

    try:
        _, resp = await router.chat(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a CTF challenge decomposer. Given a complex "
                        "challenge, break it into 2-4 independent sub-tasks "
                        "that can be solved in parallel. For each sub-task, "
                        "provide: name, description, and category. "
                        "Return one sub-task per line in format: "
                        "NAME | CATEGORY | DESCRIPTION"
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"Challenge: {challenge_name}\n"
                        f"Category: {category}\n"
                        f"Description:\n{prompt}\n\n"
                        "Decompose into sub-tasks."
                    ),
                },
            ],
            temperature=0.3,
            max_tokens=1024,
        )

        text = resp["choices"][0]["message"].get("content", "")
        subtasks = []
        for line in text.strip().split("\n"):
            parts = [p.strip() for p in line.split("|")]
            if len(parts) >= 3:
                subtasks.append({
                    "name": parts[0],
                    "category": parts[1].lower(),
                    "prompt": parts[2],
                })

        if subtasks:
            log.info(
                "auto-decomposed %s into %d sub-tasks",
                challenge_name, len(subtasks),
            )
        return subtasks

    except Exception as e:
        log.error("auto-decompose failed: %s", e)
        return []


async def cross_pollinate(
    bus: InsightBus,
    challenge_a: str,
    challenge_b: str,
) -> None:
    """Share relevant insights between two challenges.

    Called when the coordinator notices that findings from one challenge
    might help another (e.g., same service, shared credentials).
    """
    insights_a = await bus.recent(challenge_a, limit=10)
    for insight in insights_a:
        if insight.kind == "finding":
            await bus.publish(Insight(
                challenge=challenge_b,
                model="cross-pollination",
                kind="guidance",
                text=f"[from {challenge_a}] {insight.text}",
            ))
    log.info("cross-pollinated %s → %s", challenge_a, challenge_b)

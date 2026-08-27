"""9Router client — OpenAI-compatible chat completions with retry/fallback."""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from openai import AsyncOpenAI

from .config import settings

log = logging.getLogger(__name__)


class RouterClient:
    """Thin async wrapper around 9Router with retry + model fallback."""

    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        max_retries: int = 3,
        timeout: float = 300.0,
    ) -> None:
        self.client = AsyncOpenAI(
            base_url=base_url or settings.ninerouter_base_url,
            api_key=api_key or settings.ninerouter_api_key,
            timeout=timeout,
        )
        self.max_retries = max_retries

    async def list_models(self) -> list[str]:
        resp = await self.client.models.list()
        return [m.id for m in resp.data]

    async def chat(
        self,
        model: str,
        messages: list[dict[str, Any]],
        temperature: float = 0.7,
        max_tokens: int = 8192,
        tools: list[dict[str, Any]] | None = None,
        fallbacks: list[str] | None = None,
        **extra: Any,
    ) -> tuple[str, dict[str, Any]]:
        """Chat with retry + model fallback.

        Returns (model_used, response_dict). Falls back to each model in
        `fallbacks` if the primary keeps failing after retries.
        """
        chain = [model, *(fallbacks or [])]
        last_err: Exception | None = None
        for m in chain:
            for attempt in range(1, self.max_retries + 1):
                try:
                    kwargs: dict[str, Any] = dict(
                        model=m,
                        messages=messages,
                        temperature=temperature,
                        max_tokens=max_tokens,
                        **extra,
                    )
                    if tools:
                        kwargs["tools"] = tools
                    resp = await self.client.chat.completions.create(**kwargs)
                    return m, resp.model_dump()
                except Exception as e:
                    last_err = e
                    wait = min(2**attempt, 30)
                    log.warning(
                        "chat failed model=%s attempt=%d err=%s; retry in %ds",
                        m, attempt, type(e).__name__, wait,
                    )
                    await asyncio.sleep(wait)
            log.warning("model %s exhausted retries, trying fallback", m)
        raise RuntimeError(f"all models failed: {chain}; last={last_err}")


class TokenBudget:
    """Per-swarm token + wall-clock budget."""

    def __init__(self, max_tokens: int, max_seconds: float) -> None:
        self.max_tokens = max_tokens
        self.max_seconds = max_seconds
        self.used_tokens = 0
        self.started = time.monotonic()

    def record(self, usage: dict[str, Any] | None) -> None:
        if usage:
            self.used_tokens += int(usage.get("total_tokens") or 0)

    @property
    def exceeded(self) -> bool:
        return (
            self.used_tokens >= self.max_tokens
            or (time.monotonic() - self.started) >= self.max_seconds
        )

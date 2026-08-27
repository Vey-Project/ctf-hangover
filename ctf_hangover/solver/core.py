"""Solver — a single model attacking a challenge in a sandbox."""

from __future__ import annotations

import asyncio
import logging
import re
import time
from dataclasses import dataclass, field

from ..bus import Insight, InsightBus
from ..config import settings
from ..router import RouterClient, TokenBudget
from ..sandbox.core import Sandbox

log = logging.getLogger(__name__)

FLAG_RE = re.compile(r"(?:flag|FLAG|CTF)\{[^}]{1,200}\}")

SYSTEM_PROMPT = """\
You are an autonomous CTF solver running inside a Docker container with full \
CTF tooling (pwntools, radare2, gdb, nmap, sqlmap, binwalk, sage, volatility3, \
steghide, foremost, and more).

RULES:
1. NEVER give up. If one approach fails, try another.
2. Use the `run_command` tool to execute shell commands in your sandbox.
3. When you find a flag, call `submit_flag` with the flag string.
4. Share useful intermediate findings via `share_insight` — other solvers on the \
same challenge can read them.
5. If you receive a `guidance` message from the coordinator, FOLLOW it.
6. Work efficiently — you have a token and time budget.
"""

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "run_command",
            "description": "Execute a shell command in the sandbox",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "Shell command to run"},
                    "timeout": {"type": "number", "description": "Timeout in seconds", "default": 120},
                },
                "required": ["command"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "submit_flag",
            "description": "Submit a flag you found",
            "parameters": {
                "type": "object",
                "properties": {
                    "flag": {"type": "string", "description": "The flag string"},
                },
                "required": ["flag"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "share_insight",
            "description": "Share a finding with other solvers working on this challenge",
            "parameters": {
                "type": "object",
                "properties": {
                    "insight": {"type": "string", "description": "What you found or learned"},
                },
                "required": ["insight"],
            },
        },
    },
]


@dataclass
class SolverResult:
    challenge: str
    model: str
    flag: str | None = None
    elapsed: float = 0.0
    tokens_used: int = 0
    turns: int = 0
    status: str = "running"  # running | solved | timeout | budget_exceeded | error


class Solver:
    """One model instance attacking one challenge."""

    def __init__(
        self,
        model: str,
        challenge_name: str,
        challenge_prompt: str,
        bus: InsightBus,
        fallbacks: list[str] | None = None,
        router: RouterClient | None = None,
    ) -> None:
        self.model = model
        self.challenge_name = challenge_name
        self.prompt = challenge_prompt
        self.bus = bus
        self.fallbacks = fallbacks or []
        self.router = router or RouterClient()
        self.result = SolverResult(challenge=challenge_name, model=model)
        self.sandbox: Sandbox | None = None
        self.messages: list[dict] = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": challenge_prompt},
        ]
        self._stop = asyncio.Event()

    async def run(self) -> SolverResult:
        """Main solver loop. Runs until flag found, budget exceeded, or stopped."""
        budget = TokenBudget(
            max_tokens=settings.swarm_max_tokens,
            max_seconds=settings.swarm_max_minutes * 60,
        )
        self.sandbox = Sandbox(name=f"{self.challenge_name}-{self.model.replace('/', '-')}")

        started = time.monotonic()
        try:
            await self.sandbox.start()

            while not self._stop.is_set() and not budget.exceeded:
                # Drain any guidance/insights from bus
                insights = await self.bus.recent(self.challenge_name, limit=5)
                guidance_texts = [
                    i.text for i in insights if i.kind == "guidance"
                ]
                if guidance_texts:
                    self.messages.append({
                        "role": "user",
                        "content": f"[COORDINATOR GUIDANCE]: {'; '.join(guidance_texts)}",
                    })

                # Call model
                model_used, resp = await self.router.chat(
                    model=self.model,
                    messages=self.messages,
                    tools=TOOLS,
                    fallbacks=self.fallbacks,
                    temperature=0.7,
                    max_tokens=4096,
                )
                self.result.model = model_used
                usage = resp.get("usage")
                budget.record(usage)
                self.result.tokens_used = budget.used_tokens
                self.result.turns += 1

                choice = resp["choices"][0]
                msg = choice["message"]
                self.messages.append(msg)

                # Handle tool calls
                if msg.get("tool_calls"):
                    for tc in msg["tool_calls"]:
                        fn = tc["function"]["name"]
                        args = tc["function"]["arguments"]
                        if isinstance(args, str):
                            import json
                            args = json.loads(args)

                        if fn == "run_command":
                            cmd = args["command"]
                            timeout = args.get("timeout", 120)
                            rc, stdout, stderr = await self.sandbox.exec(cmd, timeout=timeout)
                            tool_resp = f"rc={rc}\nstdout:\n{stdout}\nstderr:\n{stderr}"
                            # Truncate huge outputs
                            if len(tool_resp) > 8000:
                                tool_resp = tool_resp[:4000] + "\n...TRUNCATED...\n" + tool_resp[-2000:]
                            self.messages.append({
                                "role": "tool",
                                "tool_call_id": tc["id"],
                                "content": tool_resp,
                            })

                        elif fn == "submit_flag":
                            self.result.flag = args["flag"]
                            self.result.status = "solved"
                            await self.bus.publish(Insight(
                                challenge=self.challenge_name,
                                model=model_used,
                                kind="finding",
                                text=f"FLAG FOUND: {args['flag']}",
                            ))
                            return self._finish(started)

                        elif fn == "share_insight":
                            await self.bus.publish(Insight(
                                challenge=self.challenge_name,
                                model=model_used,
                                kind="finding",
                                text=args["insight"],
                            ))
                            self.messages.append({
                                "role": "tool",
                                "tool_call_id": tc["id"],
                                "content": "Insight shared.",
                            })

                # Check for flags in text output too
                content = msg.get("content") or ""
                if isinstance(content, str):
                    match = FLAG_RE.search(content)
                    if match and not self.result.flag:
                        self.result.flag = match.group(0)
                        self.result.status = "solved"
                        return self._finish(started)

                # Small delay between turns
                await asyncio.sleep(0.5)

            if not self.result.flag:
                self.result.status = (
                    "budget_exceeded" if budget.exceeded else "timeout"
                )
        except Exception as e:
            log.error("solver %s error: %s", self.model, e)
            self.result.status = "error"
        finally:
            if self.sandbox:
                await self.sandbox.stop()

        return self._finish(started if 'started' in dir() else time.monotonic())

    def stop(self) -> None:
        self._stop.set()

    def _finish(self, started: float) -> SolverResult:
        self.result.elapsed = time.monotonic() - started
        log.info(
            "solver %s/%s: %s in %.1fs, %d tokens, %d turns",
            self.challenge_name, self.model,
            self.result.status, self.result.elapsed,
            self.result.tokens_used, self.result.turns,
        )
        return self.result

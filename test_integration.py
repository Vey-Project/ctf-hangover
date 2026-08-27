#!/usr/bin/env python3
"""Integration test — solver loop without Docker sandbox."""

import asyncio
import logging
from ctf_hangover.bus import InsightBus
from ctf_hangover.router import RouterClient

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("test")


class MockSandbox:
    """Fake sandbox that just runs commands locally via subprocess."""

    async def start(self): pass
    async def stop(self): pass

    async def exec(self, cmd: str, timeout: float = 10.0):
        proc = await asyncio.create_subprocess_shell(
            cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            out, err = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        except asyncio.TimeoutError:
            proc.kill()
            return -1, "", "TIMEOUT"
        return proc.returncode or 0, out.decode(), err.decode()


async def main():
    bus = InsightBus()
    router = RouterClient()

    # Simple challenge: find a flag in a string
    challenge_prompt = (
        "You have access to run_command. "
        "The flag is hidden in a file called /tmp/test_flag.txt. "
        "First create the file with: echo 'flag{integration_test_ok}' > /tmp/test_flag.txt "
        "Then read it with: cat /tmp/test_flag.txt "
        "When you find the flag, call submit_flag."
    )

    from ctf_hangover.solver.core import Solver, TOOLS

    solver = Solver(
        model="30-C",
        challenge_name="test-integration",
        challenge_prompt=challenge_prompt,
        bus=bus,
        fallbacks=["combo-prem", "general-pool"],
        router=router,
    )
    solver.sandbox = MockSandbox()  # type: ignore

    result = await solver.run()

    print(f"\n=== RESULT ===")
    print(f"status: {result.status}")
    print(f"flag: {result.flag}")
    print(f"elapsed: {result.elapsed:.1f}s")
    print(f"tokens: {result.tokens_used}")
    print(f"turns: {result.turns}")

    if result.flag and "integration_test_ok" in result.flag:
        print("\n✅ INTEGRATION TEST PASSED")
    else:
        print("\n⚠️  Flag not found — solver ran but didn't crack the challenge")


asyncio.run(main())

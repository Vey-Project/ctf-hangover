"""CLI entrypoint — ctf-solve command."""

from __future__ import annotations

import asyncio
import logging
import signal
import sys
from pathlib import Path

import click
from rich.console import Console
from rich.logging import RichHandler
from rich.table import Table

log = logging.getLogger(__name__)

from .bus import InsightBus
from .config import Settings, settings
from .coordinator.core import Coordinator
from .ctfd import CTFdClient
from .overkill import auto_decompose, selfplay_variants
from .router import RouterClient
from .solver.core import SolverResult
from .solver.swarm import Swarm

console = Console()


def setup_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(message)s",
        handlers=[RichHandler(console=console, rich_tracebacks=True)],
    )


@click.command()
@click.option("--ctfd-url", default=None, help="CTFd instance URL")
@click.option("--ctfd-token", default=None, help="CTFd API token")
@click.option("--ninerouter-url", default=None, help="9Router base URL")
@click.option("--ninerouter-key", default=None, help="9Router API key")
@click.option("--models", default=None, help="Comma-separated model list")
@click.option("--coordinator-model", default=None, help="Coordinator model")
@click.option("--max-challenges", default=10, help="Max parallel challenges")
@click.option("--max-models", default=4, help="Max models per swarm")
@click.option("--challenges-dir", default="challenges", help="Local challenges dir")
@click.option("--no-selfplay", is_flag=True, help="Disable self-play variants")
@click.option("--no-decompose", is_flag=True, help="Disable auto-decompose")
@click.option("--no-smart-routing", is_flag=True, help="Disable smart model routing")
@click.option("-v", "--verbose", is_flag=True, help="Verbose logging")
def main(
    ctfd_url: str | None,
    ctfd_token: str | None,
    ninerouter_url: str | None,
    ninerouter_key: str | None,
    models: str | None,
    coordinator_model: str | None,
    max_challenges: int,
    max_models: int,
    challenges_dir: str,
    no_selfplay: bool,
    no_decompose: bool,
    no_smart_routing: bool,
    verbose: bool,
) -> None:
    """CTF Hangover — autonomous CTF solver powered by 9Router."""
    setup_logging(verbose)

    # Override settings from CLI
    if ctfd_url:
        settings.ctfd_url = ctfd_url
    if ctfd_token:
        settings.ctfd_token = ctfd_token
    if ninerouter_url:
        settings.ninerouter_base_url = ninerouter_url
    if ninerouter_key:
        settings.ninerouter_api_key = ninerouter_key
    if models:
        settings.ninerouter_models = models
    if coordinator_model:
        settings.coordinator_model = coordinator_model
    settings.max_parallel_swarms = max_challenges
    settings.max_models_per_swarm = max_models
    settings.enable_selfplay = not no_selfplay
    settings.enable_auto_decompose = not no_decompose
    settings.enable_smart_routing = not no_smart_routing

    try:
        asyncio.run(run_competition(challenges_dir))
    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted by user[/yellow]")
        sys.exit(1)


async def run_competition(challenges_dir: str) -> None:
    """Main competition loop."""
    bus = InsightBus()
    router = RouterClient()

    # Discover available models
    available = settings.model_list
    if not available:
        try:
            available = await router.list_models()
            console.print(f"[green]Auto-discovered {len(available)} models from 9Router[/green]")
        except Exception as e:
            console.print(f"[red]Failed to list models: {e}[/red]")
            return

    console.print(f"[bold]Models: {', '.join(available)}[/bold]")

    # Start coordinator
    coordinator = Coordinator(bus=bus, router=router)
    coord_task = asyncio.create_task(coordinator.run())

    # Load challenges
    results: list[SolverResult] = []
    swarm_tasks: list[asyncio.Task] = []

    chal_dir = Path(challenges_dir)
    if chal_dir.exists():
        for f in sorted(chal_dir.glob("*.md")):
            prompt = f.read_text()
            name = f.stem
            category = guess_category(name, prompt)
            console.print(f"[cyan]Challenge: {name} ({category})[/cyan]")

            # Auto-decompose if enabled
            if settings.enable_auto_decompose:
                subtasks = await auto_decompose(
                    name, prompt, category,
                    model=settings.coordinator_model,
                    router=router,
                )
                if subtasks:
                    for st in subtasks:
                        swarm = Swarm(
                            challenge_name=f"{name}/{st['name']}",
                            challenge_prompt=st["prompt"],
                            category=st["category"],
                            bus=bus,
                            available_models=available,
                            router=router,
                        )
                        swarm_tasks.append(asyncio.create_task(swarm.run()))
                else:
                    swarm = Swarm(
                        challenge_name=name,
                        challenge_prompt=prompt,
                        category=category,
                        bus=bus,
                        available_models=available,
                        router=router,
                    )
                    swarm_tasks.append(asyncio.create_task(swarm.run()))
            else:
                swarm = Swarm(
                    challenge_name=name,
                    challenge_prompt=prompt,
                    category=category,
                    bus=bus,
                    available_models=available,
                    router=router,
                )
                swarm_tasks.append(asyncio.create_task(swarm.run()))

            # Self-play: spawn additional swarms for alternative
            # interpretations of the challenge (when enabled). Each variant
            # races the same model roster against a reframed prompt, so a
            # non-obvious angle can surface a flag the primary swarm missed.
            if settings.enable_selfplay:
                variants = await selfplay_variants(
                    prompt,
                    model=settings.coordinator_model,
                    n=3,
                    router=router,
                )
                for vi, variant in enumerate(variants):
                    swarm = Swarm(
                        challenge_name=f"{name}/selfplay-{vi + 1}",
                        challenge_prompt=variant,
                        category=category,
                        bus=bus,
                        available_models=available,
                        router=router,
                    )
                    swarm_tasks.append(asyncio.create_task(swarm.run()))

            # Throttle parallel swarms
            if len(swarm_tasks) >= settings.max_parallel_swarms:
                done, pending = await asyncio.wait(
                    swarm_tasks, return_when=asyncio.FIRST_COMPLETED,
                )
                for t in done:
                    results.append(t.result())
                swarm_tasks = list(pending)

    # Wait for remaining
    if swarm_tasks:
        done, _ = await asyncio.wait(swarm_tasks)
        for t in done:
            results.append(t.result())

    # Submit solved flags to CTFd so the platform records them (even when a
    # swarm's winning solver ran on a fallback model that skipped submit_flag).
    solved = [r for r in results if r.flag]
    if solved and settings.ctfd_url and settings.ctfd_token:
        try:
            ctfd = CTFdClient(settings.ctfd_url, settings.ctfd_token)
            for r in solved:
                if not r.flag:
                    continue
                chal = await ctfd.challenge_by_name(r.challenge.split("/")[0])
                if chal:
                    await ctfd.submit_flag(chal["id"], r.flag)
            await ctfd.close()
        except Exception as e:
            log.warning("CTFd submission pass failed: %s", e)

    # Stop coordinator
    coordinator.stop()
    coord_task.cancel()

    # Print results
    table = Table(title="Results")
    table.add_column("Challenge", style="cyan")
    table.add_column("Model", style="green")
    table.add_column("Status", style="yellow")
    table.add_column("Flag", style="bold red")
    table.add_column("Time", justify="right")
    table.add_column("Tokens", justify="right")

    solved = 0
    for r in results:
        flag = r.flag or "-"
        if r.flag:
            solved += 1
        table.add_row(
            r.challenge, r.model, r.status,
            flag, f"{r.elapsed:.1f}s", str(r.tokens_used),
        )

    console.print(table)
    console.print(f"\n[bold green]Solved: {solved}/{len(results)}[/bold green]")


def guess_category(name: str, prompt: str) -> str:
    """Heuristic category guess from name + prompt.

    Matches Cyber Academy (Indonesian) labels first so the solver routes to the
    correct model roster — the routing table keys are English ("soc",
    "services", "web", "forensics", "stego").
    """
    text = (name + " " + prompt).lower()
    for cat, keys in (
        ("soc", ("soc", "wazuh", "siem", "elastic", "kibana", "defacement", "ransomware", "mitre", "sysmon")),
        ("services", ("services", "ssh", "smb", "ftp", "samba", "mysql")),
        ("forensics", ("forensic", "pcap", "volatility", "memory dump", "steganografi", "stegano", "stego", "gambar", "image")),
        ("web", ("website", "web", "http", "sql injection", "sqli", "lfi", "rfi", "xss", "upload", "wordpress", "php")),
        ("crypto", ("crypto", "cipher", "rsa", "aes", "xor", "hash", "vigenere", "caesar", "base64")),
        ("rev", ("reverse", "rev ", "gdb", "radare", "ida", "elf", "binary exploitation", "assembly", "disassembl")),
        ("osint", ("osint", "open source", "instagram", "twitter", "google dork", "metadata", "geolocat")),
        ("pwn", ("pwn", "buffer overflow", "ret2", "shellcode", "format string", "heap", "stack")),
    ):
        if any(k in text for k in keys):
            return cat
    return "misc"


if __name__ == "__main__":
    main()

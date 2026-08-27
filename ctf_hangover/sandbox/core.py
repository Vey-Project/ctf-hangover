"""Docker sandbox — isolated container with CTF toolkit."""

from __future__ import annotations

import asyncio
import logging

log = logging.getLogger(__name__)

DOCKERFILE = """\
FROM kalilinux/kali-rolling

RUN apt-get update && apt-get install -y \\
    python3 python3-pip python3-venv \\
    gdb radare2 binwalk binutils file \\
    nmap sqlmap gobuster curl wget netcat-traditional \\
    steghide stegseek foremost exiftool \\
    imagemagick tesseract-ocr \\
    ffmpeg sox \\
    git vim less \\
    && rm -rf /var/lib/apt/lists/*

RUN pip3 install --break-system-packages \\
    pwntools ROPgadget angr capstone unicorn \\
    z3-solver gmpy2 pycryptodome \\
    volatility3 \\
    pillow numpy scipy torch \\
    flask requests beautifulsoup4 \\
    r2pipe

RUN git clone https://github.com/RsaCtfTool/RsaCtfTool /opt/RsaCtfTool \\
    && pip3 install --break-system-packages -r /opt/RsaCtfTool/requirements.txt

RUN useradd -m -s /bin/bash ctf
USER ctf
WORKDIR /home/ctf
"""


class Sandbox:
    """Run commands inside an isolated Docker container."""

    def __init__(self, name: str, image: str = "ctf-hangover-sandbox:latest") -> None:
        self.name = name
        self.image = image
        self._container: str | None = None

    async def start(self) -> str:
        """Start container, return container ID."""
        proc = await asyncio.create_subprocess_exec(
            "docker", "run", "-d", "--rm",
            "--name", f"ctf-{self.name}",
            "--network", "host",
            self.image,
            "sleep", "3600",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        out, err = await proc.communicate()
        if proc.returncode != 0:
            raise RuntimeError(f"sandbox start failed: {err.decode()}")
        self._container = out.decode().strip()
        log.info("sandbox %s started: %s", self.name, self._container[:12])
        return self._container

    async def exec(self, cmd: str, timeout: float = 120.0) -> tuple[int, str, str]:
        """Run a shell command inside the sandbox. Returns (rc, stdout, stderr)."""
        if not self._container:
            raise RuntimeError("sandbox not started")
        proc = await asyncio.create_subprocess_exec(
            "docker", "exec", self._container,
            "bash", "-c", cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            out, err = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        except asyncio.TimeoutError:
            proc.kill()
            return -1, "", "TIMEOUT"
        return proc.returncode or 0, out.decode(), err.decode()

    async def write_file(self, path: str, content: str) -> None:
        """Write a file inside the sandbox via stdin."""
        if not self._container:
            raise RuntimeError("sandbox not started")
        proc = await asyncio.create_subprocess_exec(
            "docker", "exec", "-i", self._container,
            "bash", "-c", f"cat > {path}",
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await proc.communicate(content.encode())

    async def read_file(self, path: str) -> str:
        rc, out, err = await self.exec(f"cat {path}")
        if rc != 0:
            raise RuntimeError(f"read failed: {err}")
        return out

    async def stop(self) -> None:
        if self._container:
            proc = await asyncio.create_subprocess_exec(
                "docker", "stop", self._container,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            await proc.communicate()
            log.info("sandbox %s stopped", self.name)
            self._container = None

    async def __aenter__(self) -> "Sandbox":
        await self.start()
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.stop()

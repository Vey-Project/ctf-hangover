"""CTFd platform integration — poll challenges, submit flags."""

from __future__ import annotations

import asyncio
import logging

import httpx
from bs4 import BeautifulSoup

log = logging.getLogger(__name__)


# Platform detection: CTFd uses /api/v1/* endpoints + /login.
# Cyber Academy (cyberacademy.id) appears to be CTFd-based.
KNOWN_CTFD_HOSTS = {
    "cyberacademy.id",
    "www.cyberacademy.id",
    "ctf.cyberacademy.id",
    "lab.cyberacademy.id",
}


async def detect_platform(base_url: str) -> str:
    """Detect whether the target URL is CTFd-based or custom.

    Returns one of: 'ctfd', 'unknown'.
    Detection logic:
      1. Try GET /api/v1/challenges → if 200 or 401/403, likely CTFd.
      2. Try GET /api/v1/notifications → same.
      3. Fallback: check if hostname is in KNOWN_CTFD_HOSTS allowlist.
    """
    base = base_url.rstrip("/")
    parsed_httpx = httpx.URL(base)
    host = parsed_httpx.host.lower() if parsed_httpx.host else ""

    if host in KNOWN_CTFD_HOSTS:
        log.info("platform detect: %s is in CTFd allowlist", host)
        return "ctfd"

    try:
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=False) as c:
            # CTFd returns 401 (no auth) or 200 with empty list, never 404
            r = await c.get(f"{base}/api/v1/challenges")
            if r.status_code in (200, 401, 403):
                log.info("platform detect: %s exposes /api/v1/challenges (%d) -> CTFd", base, r.status_code)
                return "ctfd"
            # CTFd serves /login as 200 HTML; custom platforms may not
            r2 = await c.get(f"{base}/login")
            if r2.status_code == 200 and "csrf" in r2.text.lower():
                log.info("platform detect: %s has CSRF form -> CTFd", base)
                return "ctfd"
    except Exception as e:
        log.warning("platform detect failed for %s: %s", base, e)

    log.info("platform detect: %s -> unknown (not CTFd)", base)
    return "unknown"


class CTFdClient:
    """Async CTFd API client."""

    def __init__(self, base_url: str, token: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.client = httpx.AsyncClient(
            base_url=self.base_url,
            headers={"Authorization": f"Token {token}"},
            timeout=30.0,
        )

    async def challenges(self) -> list[dict]:
        resp = await self.client.get("/api/v1/challenges")
        resp.raise_for_status()
        return resp.json().get("data", [])

    async def challenge_detail(self, chal_id: int) -> dict:
        resp = await self.client.get(f"/api/v1/challenges/{chal_id}")
        resp.raise_for_status()
        data = resp.json().get("data", {})
        # Strip HTML from description
        if "description" in data:
            soup = BeautifulSoup(data["description"], "html.parser")
            data["description_text"] = soup.get_text(separator="\n", strip=True)
        return data

    async def download_file(self, url: str, dest: str) -> str:
        resp = await self.client.get(url)
        resp.raise_for_status()
        with open(dest, "wb") as f:
            f.write(resp.content)
        return dest

    async def submit_flag(self, chal_id: int, flag: str) -> dict:
        resp = await self.client.post(
            "/api/v1/challenges/attempt",
            json={"challenge_id": chal_id, "submission": flag},
        )
        resp.raise_for_status()
        return resp.json().get("data", {})

    async def poll_new(self, known_ids: set[int], interval: float = 5.0) -> list[dict]:
        """Poll for new challenges. Returns list of new challenge dicts."""
        while True:
            try:
                challenges = await self.challenges()
                new = [c for c in challenges if c["id"] not in known_ids]
                if new:
                    return new
            except Exception as e:
                log.warning("CTFd poll error: %s", e)
            await asyncio.sleep(interval)

    async def close(self) -> None:
        await self.client.aclose()

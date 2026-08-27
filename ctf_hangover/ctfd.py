"""CTFd platform integration — poll challenges, submit flags."""

from __future__ import annotations

import asyncio
import logging

import httpx
from bs4 import BeautifulSoup

log = logging.getLogger(__name__)


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

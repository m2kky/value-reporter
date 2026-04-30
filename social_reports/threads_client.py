"""Threads API client using graph.threads.net (Meta Graph API)."""
import aiohttp
import logging
from typing import Any

from .base_client import PlatformApiError

logger = logging.getLogger(__name__)


class ThreadsApiError(PlatformApiError):
    """Threads specific API error."""
    pass


class ThreadsClient:
    """Client for the Threads API (graph.threads.net)."""

    BASE_URL = "https://graph.threads.net/v1.0"

    def __init__(self, access_token: str):
        self.access_token = access_token

    async def get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        query = dict(params or {})
        query["access_token"] = self.access_token
        url = f"{self.BASE_URL}/{path.lstrip('/')}"

        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=query) as response:
                data = await response.json()

                # Threads returns {"error": {...}} on failures
                if "error" in data:
                    err = data["error"]
                    raise ThreadsApiError(
                        f"Threads API Error [{err.get('code')}]: {err.get('message')}"
                    )

                response.raise_for_status()
                return data

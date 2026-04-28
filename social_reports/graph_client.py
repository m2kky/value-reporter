from __future__ import annotations

import json
import asyncio
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlencode

import aiohttp
from tenacity import retry, wait_exponential, stop_after_attempt, retry_if_exception_type

from .base_client import BasePlatformClient, PlatformApiError


class GraphApiError(PlatformApiError):
    pass


@dataclass
class GraphClient(BasePlatformClient):
    access_token: str
    api_version: str = "v25.0"
    timeout_seconds: int = 60

    @property
    def graph_base_url(self) -> str:
        return f"https://graph.facebook.com/{self.api_version}"

    async def get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        query = dict(params or {})
        query["access_token"] = self.access_token
        async with aiohttp.ClientSession() as session:
            return await self._get_json(session, f"{self.graph_base_url}/{path.lstrip('/')}?{urlencode(query)}")

    async def get_paginated(
        self,
        path: str,
        params: dict[str, Any] | None = None,
        *,
        max_rows: int = 100,
    ) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        query = dict(params or {})
        query["access_token"] = self.access_token
        next_url = f"{self.graph_base_url}/{path.lstrip('/')}?{urlencode(query)}"

        async with aiohttp.ClientSession() as session:
            while next_url and len(rows) < max_rows:
                payload = await self._get_json(session, next_url)
                rows.extend(payload.get("data", []))
                next_url = payload.get("paging", {}).get("next")

        return rows[:max_rows]

    @retry(
        wait=wait_exponential(multiplier=1, min=2, max=10),
        stop=stop_after_attempt(4),
        retry=retry_if_exception_type((aiohttp.ClientError, asyncio.TimeoutError, GraphApiError)),
        reraise=True
    )
    async def _get_json(self, session: aiohttp.ClientSession, url: str) -> dict[str, Any]:
        try:
            async with session.get(url, headers={"User-Agent": "monthly-social-report/0.1"}, timeout=self.timeout_seconds) as response:
                if not response.ok:
                    body = await response.text()
                    if response.status in {429, 500, 502, 503, 504}:
                        raise GraphApiError(f"Graph API HTTP {response.status}: {body}")
                    else:
                        raise PlatformApiError(f"Graph API HTTP {response.status}: {body}")
                return await response.json()
        except aiohttp.ClientError as error:
            raise GraphApiError(f"Graph API network error: {error}") from error

    async def fetch_insights(self, since: str, until: str, **kwargs) -> list[dict[str, Any]]:
        """Concrete implementation of BasePlatformClient.fetch_insights for Meta Graph API."""
        path = kwargs.get("path", "/insights")
        params = dict(kwargs.get("params", {}))
        params["since"] = since
        params["until"] = until
        return await self.get_paginated(path, params, max_rows=kwargs.get("max_rows", 500))



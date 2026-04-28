from __future__ import annotations

import json
import asyncio
from dataclasses import dataclass
from datetime import date
from typing import Any
from urllib.parse import urlencode

import aiohttp
from tenacity import retry, wait_exponential, stop_after_attempt, retry_if_exception_type

from .base_client import BasePlatformClient, PlatformApiError


class MetaApiError(PlatformApiError):
    pass


def is_retryable_error(exception: Exception) -> bool:
    if isinstance(exception, aiohttp.ClientResponseError):
        return exception.status in {429, 500, 502, 503, 504}
    if isinstance(exception, (aiohttp.ClientError, asyncio.TimeoutError)):
        return True
    return False


@dataclass
class MetaClient(BasePlatformClient):
    access_token: str
    ad_account_id: str
    api_version: str = "v22.0"
    timeout_seconds: int = 60

    @property
    def base_url(self) -> str:
        account_id = self.ad_account_id
        if account_id and not account_id.startswith("act_"):
            account_id = f"act_{account_id}"
        return f"https://graph.facebook.com/{self.api_version}/{account_id}"

    async def fetch_insights(
        self,
        *,
        since: date,
        until: date,
        fields: list[str],
        level: str | None = None,
        time_increment: int | None = None,
    ) -> list[dict[str, Any]]:
        params: dict[str, Any] = {
            "access_token": self.access_token,
            "fields": ",".join(fields),
            "time_range": json.dumps(
                {"since": since.isoformat(), "until": until.isoformat()}
            ),
            "limit": 500,
            "use_account_attribution_setting": "true",
        }
        if level:
            params["level"] = level
        if time_increment:
            params["time_increment"] = time_increment

        return await self._get_paginated(f"{self.base_url}/insights", params)

    async def get_account_currency(self) -> str:
        params = {"access_token": self.access_token, "fields": "currency"}
        async with aiohttp.ClientSession() as session:
            try:
                res = await self._get_json(session, self.base_url + "?" + urlencode(params))
                return res.get("currency", "USD")
            except Exception:
                return "USD"

    async def _get_paginated(self, url: str, params: dict[str, Any]) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        next_url = f"{url}?{urlencode(params)}"

        async with aiohttp.ClientSession() as session:
            while next_url:
                payload = await self._get_json(session, next_url)
                rows.extend(payload.get("data", []))
                next_url = payload.get("paging", {}).get("next")

        return rows

    @retry(
        wait=wait_exponential(multiplier=1, min=2, max=10),
        stop=stop_after_attempt(4),
        retry=retry_if_exception_type((aiohttp.ClientError, asyncio.TimeoutError, MetaApiError))
    )
    async def _get_json(self, session: aiohttp.ClientSession, url: str) -> dict[str, Any]:
        try:
            async with session.get(url, headers={"User-Agent": "monthly-social-report/0.1"}, timeout=self.timeout_seconds) as response:
                if not response.ok:
                    body = await response.text()
                    if response.status in {429, 500, 502, 503, 504}:
                        raise MetaApiError(f"Meta API HTTP {response.status}: {body}")
                    else:
                        # Non-retryable
                        raise PlatformApiError(f"Meta API HTTP {response.status}: {body}")
                return await response.json()
        except aiohttp.ClientError as error:
            raise MetaApiError(f"Meta API network error: {error}") from error


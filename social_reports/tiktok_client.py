import aiohttp
import asyncio
import logging
import json
from typing import Dict, Any, Optional

from .base_client import PlatformApiError

logger = logging.getLogger(__name__)

class TikTokApiError(PlatformApiError):
    """TikTok specific API error"""
    pass

class TikTokClient:
    """Client for interacting with TikTok Research API v2"""
    
    BASE_URL = "https://open.tiktokapis.com/v2"
    
    def __init__(self, access_token: str, session: Optional[aiohttp.ClientSession] = None):
        self.access_token = access_token
        self.session = session
        self._owns_session = False
        
    async def _ensure_session(self) -> aiohttp.ClientSession:
        if self.session is None:
            self.session = aiohttp.ClientSession()
            self._owns_session = True
        return self.session
    
    async def close(self):
        if self._owns_session and self.session:
            await self.session.close()
            self.session = None
        
    async def get(self, endpoint: str, fields: list[str] | None = None) -> Dict[str, Any]:
        """Make a GET request to TikTok API with fields as query params"""
        session = await self._ensure_session()
        url = f"{self.BASE_URL}{endpoint}"
        
        params = {}
        if fields:
            params["fields"] = ",".join(fields)
        
        headers = {"Authorization": f"Bearer {self.access_token}"}
        
        try:
            async with session.get(url, params=params, headers=headers) as response:
                response.raise_for_status()
                data = await response.json()
                
                error_block = data.get("error", {})
                if error_block.get("code") != "ok":
                    raise TikTokApiError(
                        f"TikTok API Error [{error_block.get('code')}]: {error_block.get('message')}"
                    )
                return data.get("data", {})
        except aiohttp.ClientResponseError as e:
            logger.error(f"TikTok HTTP Error {e.status}: {url}")
            raise TikTokApiError(f"HTTP Error {e.status}") from e
        
    async def post(self, endpoint: str, fields: list[str] | None = None, 
                   body: Dict[str, Any] | None = None) -> Dict[str, Any]:
        """Make a POST request to TikTok API with fields as query params and JSON body"""
        session = await self._ensure_session()
        url = f"{self.BASE_URL}{endpoint}"
        
        params = {}
        if fields:
            params["fields"] = ",".join(fields)
        
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }
        
        try:
            async with session.post(url, params=params, headers=headers, json=body or {}) as response:
                response.raise_for_status()
                data = await response.json()
                
                error_block = data.get("error", {})
                if error_block.get("code") != "ok":
                    raise TikTokApiError(
                        f"TikTok API Error [{error_block.get('code')}]: {error_block.get('message')}"
                    )
                return data.get("data", {})
        except aiohttp.ClientResponseError as e:
            logger.error(f"TikTok HTTP Error {e.status}: {url}")
            raise TikTokApiError(f"HTTP Error {e.status}") from e

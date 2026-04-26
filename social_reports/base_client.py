from abc import ABC, abstractmethod
import aiohttp
from typing import Any

class PlatformApiError(RuntimeError):
    """Base exception for all platform API errors."""
    pass

class BasePlatformClient(ABC):
    """Abstract base class for all social media platform clients."""

    def __init__(self, access_token: str):
        self.access_token = access_token
    
    @abstractmethod
    async def fetch_insights(self, since: str, until: str, **kwargs) -> list[dict[str, Any]]:
        """Fetch insights for a given time window. Must be implemented by subclasses."""
        pass

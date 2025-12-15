import httpx
from typing import Optional
import logging

from app.config import get_settings

logger = logging.getLogger(__name__)


class FetcherService:
    def __init__(self):
        self.settings = get_settings()
        self.timeout = httpx.Timeout(self.settings.request_timeout)
        self.headers = {
            "User-Agent": self.settings.user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate",
            "Connection": "keep-alive",
        }
    
    async def fetch(self, url: str) -> tuple[Optional[str], Optional[str]]:
        try:
            async with httpx.AsyncClient(
                timeout=self.timeout,
                follow_redirects=True,
                max_redirects=5
            ) as client:
                response = await client.get(url, headers=self.headers)
                response.raise_for_status()
                
                content_length = len(response.content)
                if content_length > self.settings.max_content_length:
                    return None, f"Content too large: {content_length} bytes"
                
                logger.info(f"Fetched {url} ({content_length} bytes)")
                return response.text, None
                
        except httpx.TimeoutException:
            return None, f"Timeout fetching {url}"
        except httpx.HTTPStatusError as e:
            return None, f"HTTP {e.response.status_code} for {url}"
        except httpx.RequestError as e:
            return None, f"Request error: {str(e)}"
        except Exception as e:
            return None, f"Error fetching {url}: {str(e)}"


_fetcher_instance: Optional[FetcherService] = None


def get_fetcher() -> FetcherService:
    global _fetcher_instance
    if _fetcher_instance is None:
        _fetcher_instance = FetcherService()
    return _fetcher_instance

import aiohttp
from typing import Dict, Any, Optional

class AsyncHTTPClient:
    @staticmethod
    async def post(
        url: str,
        json: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        timeout: float = 300.0,
    ) -> Dict[str, Any]:
        """Async POST request helper."""
        client_timeout = aiohttp.ClientTimeout(total=timeout)
        async with aiohttp.ClientSession(timeout=client_timeout) as session:
            async with session.post(url, json=json, headers=headers) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise RuntimeError(f"HTTP Return Code Error: Status {response.status}, text: {error_text}")
                return await response.json()

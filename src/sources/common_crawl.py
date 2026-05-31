from __future__ import annotations
import aiohttp
from typing import Any, Dict, List, Optional
from ..models.source import SourceResult, SourceMetadata, SourceType, FetchStatus


class CommonCrawlClient:
    BASE_URL = "https://index.commoncrawl.org"

    def __init__(self, max_pages: int = 50, timeout: int = 60) -> None:
        self.max_pages = max_pages
        self.timeout = timeout
        self._indexes: List[str] = []

    async def _get_indexes(self) -> List[str]:
        if self._indexes:
            return self._indexes
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{self.BASE_URL}/collinfo.json",
                timeout=aiohttp.ClientTimeout(total=30),
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    self._indexes = [idx["id"] for idx in data[:3]]
        return self._indexes

    async def search(self, query: str, limit: int = 10) -> List[SourceResult]:
        indexes = await self._get_indexes()
        if not indexes:
            return []

        results = []
        # CC-CS-API doesn't support text search directly; we search URLs
        # In practice you'd use a regex/prefix on URL patterns
        params: Dict[str, Any] = {
            "q": query,
            "output": "json",
            "limit": limit,
            "fl": "url,timestamp,status,filename,offset,length",
        }

        async with aiohttp.ClientSession() as session:
            for index in indexes[:1]:  # Use newest index
                try:
                    async with session.get(
                        f"{self.BASE_URL}/{index}-cdx",
                        params=params,
                        timeout=aiohttp.ClientTimeout(total=self.timeout),
                    ) as resp:
                        if resp.status != 200:
                            continue
                        text = await resp.text()
                        for line in text.strip().split("\n"):
                            try:
                                import json
                                item = json.loads(line)
                            except json.JSONDecodeError:
                                continue

                            metadata = SourceMetadata(
                                url=item.get("url", ""),
                                timestamp=item.get("timestamp", ""),
                                language="unknown",
                                source_type=SourceType.COMMON_CRAWL,
                                query_used=query,
                                status_code=int(item.get("status", 0)) if item.get("status") else None,
                                fetch_status=FetchStatus.SUCCESS,
                            )
                            results.append(SourceResult(
                                source_metadata=metadata,
                                raw_response=item,
                            ))
                            if len(results) >= self.max_pages:
                                break
                except Exception:
                    continue

        return results

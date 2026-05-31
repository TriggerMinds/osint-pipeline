from __future__ import annotations

from ..config import get_settings
from ..models.source import SourceMetadata, SourceResult, SourceType, FetchStatus
from .base import BaseConnector, ConnectorResult


class CommonCrawlConnector(BaseConnector):
    def __init__(self) -> None:
        self.settings = get_settings()
        self._indexes: list[str] = []

    async def _get_indexes(self) -> list[str]:
        if self._indexes:
            return self._indexes
        import httpx

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(f"{self.settings.commoncrawl_base_url}/collinfo.json")
                if resp.status_code == 200:
                    data = resp.json()
                    self._indexes = [idx["id"] for idx in data[:3]]
        except Exception:
            self._indexes = []
        return self._indexes

    async def search(self, query: str, **kwargs) -> ConnectorResult:
        import httpx

        indexes = await self._get_indexes()
        if not indexes:
            return ConnectorResult(sources=[], error="No CC indexes available")

        sources: list[SourceResult] = []
        params = {
            "q": query,
            "output": "json",
            "limit": 50,
            "fl": "url,timestamp,status,filename",
        }

        async with httpx.AsyncClient(timeout=self.settings.request_timeout) as client:
            for index in indexes[:1]:
                try:
                    resp = await client.get(
                        f"{self.settings.commoncrawl_base_url}/{index}-cdx",
                        params=params,
                    )
                    if resp.status_code != 200:
                        continue
                    text = resp.text
                    for line in text.strip().split("\n"):
                        import json as j

                        try:
                            item = j.loads(line)
                        except Exception:
                            continue
                        sources.append(
                            SourceResult(
                                metadata=SourceMetadata(
                                    url=item.get("url", ""),
                                    source_type=SourceType.COMMON_CRAWL,
                                    language="unknown",
                                    discovered_by_query=query,
                                    snapshot_date=item.get("timestamp", ""),
                                    status_code=int(item.get("status", 0)) or None,
                                    fetch_status=FetchStatus.SUCCESS,
                                ),
                            )
                        )
                except Exception:
                    continue

        return ConnectorResult(sources=sources)

    async def health(self) -> bool:
        try:
            idx = await self._get_indexes()
            return len(idx) > 0
        except Exception:
            return False

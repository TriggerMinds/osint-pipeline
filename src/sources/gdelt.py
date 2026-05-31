from __future__ import annotations
import aiohttp
import json
from typing import Any, Dict, List, Optional
from ..models.source import SourceResult, SourceMetadata, SourceType, FetchStatus


class GDELTClient:
    BASE_URL = "https://api.gdeltproject.org/api/v2"

    def __init__(self, max_records: int = 250, timeout: int = 30) -> None:
        self.max_records = max_records
        self.timeout = timeout

    async def search(
        self, query: str, mode: str = "ArtList", timeframe: str = "7d",
    ) -> List[SourceResult]:
        params: Dict[str, Any] = {
            "query": query,
            "mode": mode,
            "format": "json",
            "maxrecords": self.max_records,
            "timespan": timeframe,
        }

        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(
                    f"{self.BASE_URL}/doc/doc",
                    params=params,
                    timeout=aiohttp.ClientTimeout(total=self.timeout),
                ) as resp:
                    if resp.status != 200:
                        return []
                    data = await resp.json()
            except Exception:
                return []

        results = []
        articles = data.get("articles", data.get("results", []))
        if isinstance(articles, dict):
            articles = [articles]

        for article in articles[:self.max_records]:
            url = article.get("url", article.get("link", ""))
            metadata = SourceMetadata(
                url=url,
                timestamp=article.get("seendate", article.get("date", "")),
                language=article.get("language", "en"),
                source_type=SourceType.GDELT,
                query_used=query,
                title=article.get("title", ""),
                domain=article.get("domain", ""),
                fetch_status=FetchStatus.SUCCESS,
            )
            results.append(SourceResult(
                source_metadata=metadata,
                content_text=article.get("summary", ""),
                raw_response=article,
            ))

        return results

    async def event_search(
        self, query: str, timeframe: str = "7d",
    ) -> List[Dict[str, Any]]:
        params: Dict[str, Any] = {
            "query": query,
            "mode": "EventList",
            "format": "json",
            "maxrecords": self.max_records,
            "timespan": timeframe,
        }

        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(
                    f"{self.BASE_URL}/doc/doc",
                    params=params,
                    timeout=aiohttp.ClientTimeout(total=self.timeout),
                ) as resp:
                    if resp.status != 200:
                        return []
                    data = await resp.json()
                    return data.get("events", data.get("results", []))
            except Exception:
                return []

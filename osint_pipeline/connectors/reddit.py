from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

import httpx

from ..models.source import SourceMetadata, SourceResult, SourceType, FetchStatus
from .base import BaseConnector, ConnectorResult, _compact_error
from .errors import ConnectorError


@dataclass
class RedditParams:
    query: str
    sort: str = "relevance"  # relevance, hot, top, new, comments
    time_filter: str = "all"  # hour, day, week, month, year, all
    limit: int = 25


class RedditConnector(BaseConnector):
    BASE_URL = "https://www.reddit.com"

    def __init__(self) -> None:
        super().__init__()

    async def search(
        self, query: str, sort: str = "relevance", limit: int = 25, **kwargs,
    ) -> ConnectorResult:
        params = RedditParams(query=query, sort=sort, limit=limit)
        return await self._search(params)

    async def _search(self, params: RedditParams) -> ConnectorResult:
        now = datetime.now(timezone.utc).isoformat()

        headers = {
            "User-Agent": self.settings.reddit_user_agent,
        }

        async with httpx.AsyncClient(timeout=self.settings.request_timeout) as client:
            try:
                resp = await self._request_with_retry(
                    client, "GET", f"{self.BASE_URL}/search.json",
                    params={
                        "q": params.query,
                        "sort": params.sort,
                        "t": params.time_filter,
                        "limit": params.limit,
                        "restrict_sr": "off",
                    },
                    headers=headers,
                )
            except ConnectorError as exc:
                return ConnectorResult(sources=[], error=_compact_error(exc))

            if resp.status_code == 429:
                return ConnectorResult(sources=[], error="Reddit rate limited")
            if resp.status_code != 200:
                return ConnectorResult(sources=[], error=f"Reddit HTTP {resp.status_code}")

            data = resp.json()

        sources: list[SourceResult] = []
        for child in data.get("data", {}).get("children", []):
            item = child.get("data", {})
            url = item.get("url", item.get("permalink", ""))
            full_url = f"https://www.reddit.com{url}" if url.startswith("/") else url

            sources.append(
                SourceResult(
                    metadata=SourceMetadata(
                        url=full_url,
                        source_type=SourceType.REDDIT,
                        language="en",
                        discovered_by_query=params.query,
                        discovered_at=now,
                        title=item.get("title", ""),
                        domain="reddit.com",
                        fetch_status=FetchStatus.SUCCESS,
                    ),
                    content=item.get("selftext", item.get("body", "")),
                )
            )

        return ConnectorResult(sources=sources)

    async def health(self) -> bool:
        async with httpx.AsyncClient(timeout=5) as client:
            try:
                resp = await client.get(
                    f"{self.BASE_URL}/.json",
                    headers={"User-Agent": self.settings.reddit_user_agent},
                )
                return resp.status_code == 200
            except Exception:
                return False

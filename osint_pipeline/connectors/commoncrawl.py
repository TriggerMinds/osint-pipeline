from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

import httpx

from ..models.source import SourceMetadata, SourceResult, SourceType, FetchStatus
from .base import BaseConnector, ConnectorResult, _compact_error
from .errors import ConnectorError


@dataclass
class CommonCrawlParams:
    url: str
    index: Optional[str] = None
    limit: int = 50


@dataclass
class CCIndexInfo:
    id: str
    name: str
    created: str


class CommonCrawlConnector(BaseConnector):
    def __init__(self) -> None:
        super().__init__()
        self._timeout = self.settings.commoncrawl_timeout
        self._index_cache: list[CCIndexInfo] = []

    async def _fetch_indexes(self) -> list[CCIndexInfo]:
        if self._index_cache:
            return self._index_cache

        async with httpx.AsyncClient(timeout=15) as client:
            try:
                resp = await self._request_with_retry(
                    client, "GET", f"{self.settings.commoncrawl_base_url}/collinfo.json",
                    timeout=15,
                )
            except Exception:
                return []

            if resp.status_code != 200:
                return []

            raw = resp.json()
            self._index_cache = [
                CCIndexInfo(
                    id=idx.get("id", ""),
                    name=idx.get("name", ""),
                    created=idx.get("created", ""),
                )
                for idx in raw[:5]
            ]

        return self._index_cache

    async def search(
        self,
        query: str,
        index: Optional[str] = None,
        limit: int = 50,
        **kwargs,
    ) -> ConnectorResult:
        params = CommonCrawlParams(url=query, index=index, limit=limit)
        return await self._search(params)

    async def _search(self, params: CommonCrawlParams) -> ConnectorResult:
        now = datetime.now(timezone.utc).isoformat()

        indexes = await self._fetch_indexes()
        if not indexes:
            return ConnectorResult(sources=[], error="No Common Crawl indexes available")

        if params.index:
            indexes = [i for i in indexes if i.id == params.index]
            if not indexes:
                return ConnectorResult(
                    sources=[], error=f"Index '{params.index}' not found"
                )

        sources: list[SourceResult] = []
        query_params: dict = {
            "output": "json",
            "limit": str(params.limit),
            "fl": "url,timestamp,status,filename,length",
        }

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            for idx in indexes[:1]:  # Newest index only
                try:
                    resp = await self._request_with_retry(
                        client, "GET",
                        f"{self.settings.commoncrawl_base_url}/{idx.id}-cdx",
                        params={**query_params, "q": params.url},
                        timeout=self._timeout,
                    )
                except ConnectorError as exc:
                    return ConnectorResult(
                        sources=sources,
                        error=_compact_error(exc),
                    )

                if resp.status_code != 200:
                    continue

                for line in resp.text.strip().split("\n"):
                    try:
                        item = json.loads(line)
                    except json.JSONDecodeError:
                        continue

                    url = item.get("url", "")
                    ts = item.get("timestamp", "")
                    snapshot = self._parse_ts(ts) if ts else ""

                    sources.append(
                        SourceResult(
                            metadata=SourceMetadata(
                                url=url,
                                source_type=SourceType.COMMON_CRAWL,
                                language="unknown",
                                discovered_by_query=params.url,
                                discovered_at=now,
                                snapshot_date=snapshot,
                                domain=self._extract_domain(url),
                                status_code=self._safe_int(item.get("status")),
                                fetch_status=FetchStatus.SUCCESS,
                            ),
                        )
                    )

        return ConnectorResult(sources=sources)

    async def health(self) -> bool:
        indexes = await self._fetch_indexes()
        return len(indexes) > 0

    @staticmethod
    def _parse_ts(ts: str) -> str:
        try:
            return datetime.strptime(ts[:14], "%Y%m%d%H%M%S").isoformat()
        except (ValueError, IndexError):
            return ts

    @staticmethod
    def _safe_int(val: str | None) -> int | None:
        if val is None:
            return None
        try:
            return int(val)
        except (ValueError, TypeError):
            return None

    @staticmethod
    def _extract_domain(url: str) -> str:
        from urllib.parse import urlparse
        try:
            return urlparse(url).netloc
        except Exception:
            return ""

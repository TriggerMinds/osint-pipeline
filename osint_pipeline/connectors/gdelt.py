from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

import httpx

from ..models.source import SourceMetadata, SourceResult, SourceType, FetchStatus
from .base import BaseConnector, ConnectorResult


@dataclass
class GDELTParams:
    query: str
    mode: str = "ArtList"
    max_records: int = 250
    timespan: str = "7d"
    language: Optional[str] = None


class GDELTConnector(BaseConnector):
    def __init__(self) -> None:
        super().__init__()
        self._timeout = self.settings.gdelt_timeout

    async def search(
        self,
        query: str,
        language: Optional[str] = None,
        timespan: str = "7d",
        mode: str = "ArtList",
        max_records: int = 250,
        **kwargs,
    ) -> ConnectorResult:
        params = GDELTParams(
            query=query,
            mode=mode,
            max_records=max_records,
            timespan=timespan,
            language=language,
        )
        return await self._search(params)

    async def _search(self, params: GDELTParams) -> ConnectorResult:
        now = datetime.now(timezone.utc).isoformat()

        query_params: dict = {
            "query": params.query,
            "mode": params.mode,
            "format": "json",
            "maxrecords": str(params.max_records),
            "timespan": params.timespan,
        }
        if params.language:
            query_params["language"] = params.language

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            try:
                resp = await self._request_with_retry(
                    client, "GET", f"{self.settings.gdelt_base_url}/doc/doc",
                    params=query_params,
                    timeout=self._timeout,
                )
            except Exception as exc:
                return ConnectorResult(
                    sources=[], error=f"GDELT request failed: {type(exc).__name__}"
                )

            if resp.status_code != 200:
                return ConnectorResult(
                    sources=[], error=f"GDELT HTTP {resp.status_code}"
                )

            raw = resp.json()

        articles = raw.get("articles", raw.get("results", []))
        if isinstance(articles, dict):
            articles = [articles]

        sources: list[SourceResult] = []
        for art in articles[:params.max_records]:
            url = art.get("url", art.get("link", ""))
            domain = self._extract_domain(url)
            sources.append(
                SourceResult(
                    metadata=SourceMetadata(
                        url=url,
                        source_type=SourceType.GDELT,
                        language=art.get("language", params.language or "en"),
                        discovered_by_query=params.query,
                        discovered_at=now,
                        snapshot_date=art.get("seendate", art.get("date")),
                        title=art.get("title"),
                        domain=domain,
                        status_code=resp.status_code,
                        fetch_status=FetchStatus.SUCCESS,
                    ),
                    content=art.get("summary"),
                )
            )

        return ConnectorResult(sources=sources)

    async def health(self) -> bool:
        async with httpx.AsyncClient(timeout=5) as client:
            try:
                resp = await client.get(
                    f"{self.settings.gdelt_base_url}/doc/doc",
                    params={"query": "test", "mode": "ArtList", "format": "json"},
                )
                return resp.status_code == 200
            except Exception:
                return False

    @staticmethod
    def _extract_domain(url: str) -> str:
        from urllib.parse import urlparse
        try:
            return urlparse(url).netloc
        except Exception:
            return ""

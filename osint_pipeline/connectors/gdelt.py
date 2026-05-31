from __future__ import annotations

from datetime import datetime, timezone

from ..config import get_settings
from ..models.source import SourceMetadata, SourceResult, SourceType, FetchStatus
from .base import BaseConnector, ConnectorResult


class GDELTConnector(BaseConnector):
    def __init__(self) -> None:
        self.settings = get_settings()

    async def search(self, query: str, timeframe: str = "7d", **kwargs) -> ConnectorResult:
        import httpx

        params = {
            "query": query,
            "mode": "ArtList",
            "format": "json",
            "maxrecords": 250,
            "timespan": timeframe,
        }

        try:
            async with httpx.AsyncClient(timeout=self.settings.request_timeout) as client:
                resp = await client.get(
                    f"{self.settings.gdelt_base_url}/doc/doc",
                    params=params,
                )
                if resp.status_code != 200:
                    return ConnectorResult(sources=[], error=f"HTTP {resp.status_code}")
                data = resp.json()
        except Exception as e:
            return ConnectorResult(sources=[], error=str(e))

        articles = data.get("articles", data.get("results", []))
        sources: list[SourceResult] = []
        now = datetime.now(timezone.utc).isoformat()

        for art in articles[:250]:
            sources.append(
                SourceResult(
                    metadata=SourceMetadata(
                        url=art.get("url", art.get("link", "")),
                        source_type=SourceType.GDELT,
                        language=art.get("language", "en"),
                        discovered_by_query=query,
                        discovered_at=now,
                        title=art.get("title"),
                        domain=art.get("domain"),
                        fetch_status=FetchStatus.SUCCESS,
                    ),
                    content=art.get("summary"),
                )
            )

        return ConnectorResult(sources=sources)

    async def health(self) -> bool:
        import httpx

        try:
            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.get(
                    f"{self.settings.gdelt_base_url}/doc/doc",
                    params={"query": "test", "mode": "ArtList", "format": "json"},
                )
                return resp.status_code == 200
        except Exception:
            return False

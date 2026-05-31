from __future__ import annotations

from ..config import get_settings
from ..models.source import SourceMetadata, SourceResult, SourceType, FetchStatus
from .base import BaseConnector, ConnectorResult


class SearXNGConnector(BaseConnector):
    def __init__(self) -> None:
        self.settings = get_settings()
        self.instances = [
            s.strip()
            for s in self.settings.searxng_instances.split(",")
            if s.strip()
        ]

    async def search(self, query: str, language: str = "en", **kwargs) -> ConnectorResult:
        import httpx

        results: list[SourceResult] = []

        for instance in self.instances:
            try:
                async with httpx.AsyncClient(timeout=self.settings.request_timeout) as client:
                    resp = await client.get(
                        f"{instance}/search",
                        params={"q": query, "format": "json", "language": language},
                    )
                    if resp.status_code != 200:
                        continue
                    data = resp.json()
                    for item in data.get("results", []):
                        results.append(
                            SourceResult(
                                metadata=SourceMetadata(
                                    url=item.get("url", ""),
                                    source_type=SourceType.SEARXNG,
                                    language=item.get("language", language),
                                    discovered_by_query=query,
                                    title=item.get("title"),
                                    fetch_status=FetchStatus.SUCCESS,
                                ),
                                content=item.get("content"),
                            )
                        )
            except Exception:
                continue

        return ConnectorResult(sources=results)

    async def health(self) -> bool:
        import httpx

        for instance in self.instances:
            try:
                async with httpx.AsyncClient(timeout=5) as client:
                    resp = await client.get(f"{instance}/search", params={"q": "test", "format": "json"})
                    if resp.status_code == 200:
                        return True
            except Exception:
                continue
        return False

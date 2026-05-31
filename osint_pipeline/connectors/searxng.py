from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

import httpx

from ..models.source import SourceMetadata, SourceResult, SourceType, FetchStatus
from .base import BaseConnector, ConnectorResult, _compact_error
from .errors import ConnectorError


@dataclass
class SearXNGParams:
    query: str
    language: str = "en"
    categories: tuple[str, ...] = ("general",)
    time_range: Optional[str] = None
    engines: tuple[str, ...] = ()
    max_results: int = 20


class SearXNGConnector(BaseConnector):
    def __init__(self) -> None:
        super().__init__()
        self.instances = [
            s.strip()
            for s in self.settings.searxng_instances.split(",")
            if s.strip()
        ]
        self._timeout = self.settings.searxng_timeout

    async def search(
        self,
        query: str,
        language: str = "en",
        categories: tuple[str, ...] = ("general",),
        time_range: Optional[str] = None,
        engines: tuple[str, ...] = (),
        **kwargs,
    ) -> ConnectorResult:
        params = SearXNGParams(
            query=query,
            language=language,
            categories=categories,
            time_range=time_range,
            engines=engines,
        )
        return await self._search(params)

    async def _search(self, params: SearXNGParams) -> ConnectorResult:
        now = datetime.now(timezone.utc).isoformat()
        results: list[SourceResult] = []

        last_error: str | None = None
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            for instance in self.instances:
                query_params: dict = {
                    "q": params.query,
                    "format": "json",
                    "language": params.language,
                    "categories": ",".join(params.categories),
                }
                if params.time_range:
                    query_params["time_range"] = params.time_range
                if params.engines:
                    query_params["engines"] = ",".join(params.engines)

                try:
                    resp = await self._request_with_retry(
                        client, "GET", f"{instance}/search",
                        params=query_params,
                        timeout=self._timeout,
                    )
                except ConnectorError as exc:
                    last_error = _compact_error(exc)
                    continue

                if resp.status_code != 200:
                    continue

                raw = resp.json()
                for item in raw.get("results", [])[:params.max_results]:
                    url = item.get("url", "")
                    domain = self._extract_domain(url)
                    results.append(
                        SourceResult(
                            metadata=SourceMetadata(
                                url=url,
                                source_type=SourceType.SEARXNG,
                                language=item.get("language", params.language),
                                discovered_by_query=params.query,
                                discovered_at=now,
                                snapshot_date=None,
                                title=item.get("title"),
                                domain=domain,
                                status_code=resp.status_code,
                                fetch_status=FetchStatus.SUCCESS,
                            ),
                            content=item.get("content"),
                        )
                    )

        if not results and last_error:
            return ConnectorResult(sources=results, error=last_error)
        return ConnectorResult(sources=results)

    async def health(self) -> bool:
        async with httpx.AsyncClient(timeout=5) as client:
            for instance in self.instances:
                try:
                    resp = await client.get(
                        f"{instance}/search",
                        params={"q": "test", "format": "json"},
                    )
                    if resp.status_code == 200:
                        return True
                except Exception:
                    continue
        return False

    @staticmethod
    def _extract_domain(url: str) -> str:
        from urllib.parse import urlparse
        try:
            return urlparse(url).netloc
        except Exception:
            return ""

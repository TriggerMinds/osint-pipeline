from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

import httpx

from ..models.source import SourceMetadata, SourceResult, SourceType, FetchStatus
from .base import BaseConnector, ConnectorResult, _compact_error
from .errors import ConnectorError


@dataclass
class OpenAlexParams:
    query: str
    per_page: int = 25
    sort: Optional[str] = None


class OpenAlexConnector(BaseConnector):
    BASE_URL = "https://api.openalex.org"

    def __init__(self) -> None:
        super().__init__()

    async def search(
        self, query: str, per_page: int = 25, **kwargs,
    ) -> ConnectorResult:
        params = OpenAlexParams(query=query, per_page=per_page)
        return await self._search(params)

    async def _search(self, params: OpenAlexParams) -> ConnectorResult:
        now = datetime.now(timezone.utc).isoformat()
        query_params: dict = {
            "search": params.query,
            "per-page": str(params.per_page),
        }
        if self.settings.openalex_email:
            query_params["mailto"] = self.settings.openalex_email

        async with httpx.AsyncClient(timeout=self.settings.request_timeout) as client:
            try:
                resp = await self._request_with_retry(
                    client, "GET", f"{self.BASE_URL}/works",
                    params=query_params,
                )
            except ConnectorError as exc:
                return ConnectorResult(sources=[], error=_compact_error(exc))

            if resp.status_code != 200:
                return ConnectorResult(sources=[], error=f"OpenAlex HTTP {resp.status_code}")

            data = resp.json()

        sources: list[SourceResult] = []
        for work in data.get("results", []):
            url = work.get("id", "")
            title = work.get("title", "")
            doi = work.get("doi", "")
            display_url = f"https://doi.org/{doi}" if doi else url

            sources.append(
                SourceResult(
                    metadata=SourceMetadata(
                        url=display_url or url,
                        source_type=SourceType.OPENALEX,
                        language=work.get("language", "en"),
                        discovered_by_query=params.query,
                        discovered_at=now,
                        title=title,
                        domain="openalex.org",
                        fetch_status=FetchStatus.SUCCESS,
                    ),
                    content=work.get("abstract_inverted_index", None) and str(work["abstract_inverted_index"]),
                )
            )

        return ConnectorResult(sources=sources)

    async def health(self) -> bool:
        async with httpx.AsyncClient(timeout=5) as client:
            try:
                resp = await client.get(f"{self.BASE_URL}/works", params={"search": "test", "per-page": "1"})
                return resp.status_code == 200
            except Exception:
                return False

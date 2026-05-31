from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

import httpx

from ..models.source import SourceMetadata, SourceResult, SourceType, FetchStatus
from .base import BaseConnector, ConnectorResult, _compact_error
from .errors import ConnectorError, ConnectorHTTPStatusError


@dataclass
class GitHubParams:
    query: str
    search_type: str = "repos"  # repos, code, issues
    per_page: int = 30


class GitHubSearchConnector(BaseConnector):
    BASE_URL = "https://api.github.com"

    def __init__(self) -> None:
        super().__init__()

    async def search(
        self, query: str, search_type: str = "repos", **kwargs,
    ) -> ConnectorResult:
        params = GitHubParams(query=query, search_type=search_type)
        return await self._search(params)

    async def _search(self, params: GitHubParams) -> ConnectorResult:
        now = datetime.now(timezone.utc).isoformat()
        headers: dict = {"Accept": "application/vnd.github.v3+json"}
        token = self.settings.github_token
        if token:
            headers["Authorization"] = f"Bearer {token}"

        endpoint = f"{self.BASE_URL}/search/{params.search_type}"

        async with httpx.AsyncClient(timeout=self.settings.request_timeout) as client:
            try:
                resp = await self._request_with_retry(
                    client, "GET", endpoint,
                    params={"q": params.query, "per_page": params.per_page},
                    headers=headers,
                )
            except ConnectorHTTPStatusError as exc:
                if exc.status == 403:
                    return ConnectorResult(sources=[], error="GitHub rate limit exceeded")
                return ConnectorResult(sources=[], error=_compact_error(exc))
            except ConnectorError as exc:
                return ConnectorResult(sources=[], error=_compact_error(exc))

            if resp.status_code != 200:
                return ConnectorResult(sources=[], error=f"GitHub HTTP {resp.status_code}")

            data = resp.json()

        sources: list[SourceResult] = []
        for item in data.get("items", []):
            url = item.get("html_url", item.get("url", ""))
            sources.append(
                SourceResult(
                    metadata=SourceMetadata(
                        url=url,
                        source_type=SourceType.GITHUB,
                        language="en",
                        discovered_by_query=params.query,
                        discovered_at=now,
                        title=item.get("name", item.get("title", "")),
                        domain="github.com",
                        fetch_status=FetchStatus.SUCCESS,
                    ),
                    content=item.get("description", item.get("body", "")),
                )
            )

        return ConnectorResult(sources=sources)

    async def health(self) -> bool:
        async with httpx.AsyncClient(timeout=5) as client:
            try:
                resp = await client.get(f"{self.BASE_URL}/zen")
                return resp.status_code == 200
            except Exception:
                return False

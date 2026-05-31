from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

import httpx

from ..models.source import SourceMetadata, SourceResult, SourceType, FetchStatus
from .base import BaseConnector, ConnectorResult, _compact_error
from .errors import ConnectorError

# MediaWiki API endpoint for Wikidata entity search (no SPARQL injection risk).
_WIKIDATA_API_URL = "https://www.wikidata.org/w/api.php"

# Characters that are never valid in a Wikidata entity search query.
_WIKIDATA_REJECT_RE = re.compile(r'["{};\\\n\r\t]')


def _sanitize_wikidata_search_query(query: str, max_len: int = 200) -> str:
    """Validate and sanitize a Wikidata entity search query.

    Raises ConnectorError if the query is empty, too long, or contains
    characters that could break the request or be used for injection.
    Returns the sanitised (trimmed) query string.
    """
    q = query.strip()
    if not q:
        raise ConnectorError("wikidata query is empty")
    if len(q) > max_len:
        q = q[:max_len]
    if _WIKIDATA_REJECT_RE.search(q):
        raise ConnectorError(
            "wikidata query contains unsupported characters"
        )
    return q


@dataclass
class WikidataParams:
    query: str
    limit: int = 25


# Sane upper bound enforced server-side, but we limit client-side too.
_MAX_WIKIDATA_LIMIT = 50


class WikidataConnector(BaseConnector):
    def __init__(self) -> None:
        super().__init__()

    async def search(
        self, query: str, limit: int = 25, **kwargs,
    ) -> ConnectorResult:
        params = WikidataParams(query=query, limit=limit)
        return await self._search(params)

    async def _search(self, params: WikidataParams) -> ConnectorResult:
        now = datetime.now(timezone.utc).isoformat()

        # Validate and sanitise — raises ConnectorError on bad input.
        safe_query = _sanitize_wikidata_search_query(params.query)
        safe_limit = min(params.limit, _MAX_WIKIDATA_LIMIT)

        # Use the MediaWiki action=wbsearchentities API instead of
        # constructing SPARQL with string interpolation.  This API
        # accepts the search term as a plain HTTP parameter, so there
        # is no vector for SPARQL injection.
        api_params: dict = {
            "action": "wbsearchentities",
            "search": safe_query,
            "language": "en",
            "uselang": "en",
            "format": "json",
            "limit": str(safe_limit),
        }

        headers = {
            "User-Agent": "osint-pipeline/0.1 (OSINT research pipeline; bot)",
            "Accept": "application/json",
        }

        async with httpx.AsyncClient(timeout=self.settings.request_timeout) as client:
            try:
                resp = await self._request_with_retry(
                    client, "GET", _WIKIDATA_API_URL,
                    params=api_params,
                    headers=headers,
                )
            except ConnectorError as exc:
                return ConnectorResult(sources=[], error=_compact_error(exc))

            if resp.status_code != 200:
                return ConnectorResult(sources=[], error=f"Wikidata API HTTP {resp.status_code}")

            data = resp.json()

        sources: list[SourceResult] = []

        for result in data.get("search", []):
            item_id = result.get("id", "")
            label = result.get("label", "")
            desc = result.get("description", "")
            # wbsearchentities does not return a Wikipedia article URL
            # directly; fall back to the Wikidata item page.
            item_url = f"https://www.wikidata.org/entity/{item_id}" if item_id else ""

            sources.append(
                SourceResult(
                    metadata=SourceMetadata(
                        url=item_url,
                        source_type=SourceType.WIKIDATA,
                        language="en",
                        discovered_by_query=safe_query,
                        discovered_at=now,
                        title=label,
                        domain="wikidata.org",
                        fetch_status=FetchStatus.SUCCESS,
                    ),
                    content=desc,
                )
            )

        return ConnectorResult(sources=sources)

    async def health(self) -> bool:
        headers = {
            "User-Agent": "osint-pipeline/0.1 (OSINT research pipeline; health)",
        }
        async with httpx.AsyncClient(timeout=5) as client:
            try:
                resp = await client.get(
                    _WIKIDATA_API_URL,
                    params={
                        "action": "wbsearchentities",
                        "search": "test",
                        "format": "json",
                        "limit": "1",
                    },
                    headers=headers,
                )
                return resp.status_code == 200
            except Exception:
                return False

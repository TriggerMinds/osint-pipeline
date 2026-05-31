from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

import httpx

from ..models.source import SourceMetadata, SourceResult, SourceType, FetchStatus
from .base import BaseConnector, ConnectorResult, _compact_error
from .errors import ConnectorError


@dataclass
class WikidataParams:
    query: str
    limit: int = 25


ENTITY_SEARCH = """
SELECT ?item ?itemLabel ?itemDescription ?article WHERE {
  SERVICE wikibase:mwapi {
    bd:serviceParam wikibase:endpoint "www.wikidata.org";
                    wikibase:api "EntitySearch";
                    mwapi:search "%s";
                    mwapi:language "en";
                    mwapi:limit %d.
    ?item wikibase:apiOutputItem mwapi:item.
    ?num wikibase:apiOutput "mwapi:score".
  }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en". }
  OPTIONAL { ?article schema:about ?item; schema:isPartOf <https://en.wikipedia.org/>. }
}
ORDER BY DESC(?num)
"""  # noqa: E501


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
        sparql = ENTITY_SEARCH % (params.query, params.limit)

        async with httpx.AsyncClient(timeout=self.settings.request_timeout) as client:
            try:
                resp = await self._request_with_retry(
                    client, "GET", self.settings.wikidata_endpoint,
                    params={"format": "json", "query": sparql},
                )
            except ConnectorError as exc:
                return ConnectorResult(sources=[], error=_compact_error(exc))

            if resp.status_code != 200:
                return ConnectorResult(sources=[], error=f"Wikidata HTTP {resp.status_code}")

            data = resp.json()

        bindings = data.get("results", {}).get("bindings", [])
        sources: list[SourceResult] = []

        for b in bindings:
            item = b.get("item", {}).get("value", "")
            label = b.get("itemLabel", {}).get("value", "")
            desc = b.get("itemDescription", {}).get("value", "")
            article = b.get("article", {}).get("value", "")

            sources.append(
                SourceResult(
                    metadata=SourceMetadata(
                        url=article or item,
                        source_type=SourceType.WIKIDATA,
                        language="en",
                        discovered_by_query=params.query,
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
        async with httpx.AsyncClient(timeout=5) as client:
            try:
                resp = await client.get(
                    self.settings.wikidata_endpoint,
                    params={"format": "json", "query": "SELECT * WHERE {?s ?p ?o} LIMIT 1"},
                )
                return resp.status_code == 200
            except Exception:
                return False

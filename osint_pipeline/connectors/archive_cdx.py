from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

import httpx

from ..models.source import SourceMetadata, SourceResult, SourceType, FetchStatus
from .base import BaseConnector, ConnectorResult, _compact_error
from .errors import ConnectorError


@dataclass
class ArchiveCDXParams:
    url: str
    from_date: Optional[str] = None
    to_date: Optional[str] = None
    limit: int = 20
    filter_status: Optional[str] = "200"
    collapse: Optional[str] = "urlkey"
    fl: str = "original,timestamp,endtimestamp,statuscode,digest,length"


class ArchiveCDXConnector(BaseConnector):
    def __init__(self) -> None:
        super().__init__()
        self._timeout = self.settings.archive_timeout

    async def search(
        self,
        query: str,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        **kwargs,
    ) -> ConnectorResult:
        params = ArchiveCDXParams(
            url=query,
            from_date=from_date,
            to_date=to_date,
        )
        return await self._search(params)

    async def _search(self, params: ArchiveCDXParams) -> ConnectorResult:
        query_params: dict = {
            "url": params.url,
            "output": "json",
            "limit": str(params.limit),
            "fl": params.fl,
        }
        if params.from_date:
            query_params["from"] = params.from_date
        if params.to_date:
            query_params["to"] = params.to_date
        if params.filter_status:
            query_params["filter"] = f"statuscode:{params.filter_status}"
        if params.collapse:
            query_params["collapse"] = params.collapse

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            try:
                resp = await self._request_with_retry(
                    client, "GET", self.settings.archive_cdx_url,
                    params=query_params,
                    timeout=self._timeout,
                )
            except ConnectorError as exc:
                return ConnectorResult(
                    sources=[], error=_compact_error(exc)
                )

            if resp.status_code != 200:
                return ConnectorResult(
                    sources=[], error=f"Archive CDX HTTP {resp.status_code}"
                )

            raw = resp.json()

        if not raw or len(raw) < 2:
            return ConnectorResult(sources=[])

        headers = raw[0]
        sources: list[SourceResult] = []

        for row in raw[1:]:
            row_map = dict(zip(headers, row))
            url = row_map.get("original", "")
            ts = row_map.get("timestamp", "")
            end_ts = row_map.get("endtimestamp", "")
            snapshot = self._parse_ts(ts)

            wayback_url = f"{self.settings.archive_wayback_url}/{ts}/{url}" if ts else ""

            sources.append(
                SourceResult(
                    metadata=SourceMetadata(
                        url=url,
                        source_type=SourceType.INTERNET_ARCHIVE,
                        language="unknown",
                        discovered_by_query=params.url,
                        discovered_at=snapshot or "",
                        snapshot_date=snapshot,
                        domain=self._extract_domain(url),
                        status_code=self._safe_int(row_map.get("statuscode")),
                        fetch_status=FetchStatus.SUCCESS,
                        archive_url=wayback_url,
                    ),
                )
            )

        return ConnectorResult(sources=sources)

    async def health(self) -> bool:
        async with httpx.AsyncClient(timeout=5) as client:
            try:
                resp = await client.get(
                    self.settings.archive_cdx_url,
                    params={"url": "example.com", "output": "json", "limit": 1},
                )
                return resp.status_code == 200
            except Exception:
                return False

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

from __future__ import annotations

from datetime import datetime

from ..config import get_settings
from ..models.source import SourceMetadata, SourceResult, SourceType, FetchStatus
from .base import BaseConnector, ConnectorResult


class ArchiveCDXConnector(BaseConnector):
    def __init__(self) -> None:
        self.settings = get_settings()

    async def search(self, query: str, **kwargs) -> ConnectorResult:
        import httpx

        params = {
            "url": query,
            "output": "json",
            "limit": 20,
            "fl": "original,timestamp,statuscode,digest",
        }
        if kwargs.get("from_date"):
            params["from"] = kwargs["from_date"]
        if kwargs.get("to_date"):
            params["to"] = kwargs["to_date"]

        try:
            async with httpx.AsyncClient(timeout=self.settings.request_timeout) as client:
                resp = await client.get(self.settings.archive_cdx_url, params=params)
                if resp.status_code != 200:
                    return ConnectorResult(sources=[], error=f"CDX HTTP {resp.status_code}")
                data = resp.json()
        except Exception as e:
            return ConnectorResult(sources=[], error=str(e))

        if not data or len(data) < 2:
            return ConnectorResult(sources=[])

        headers = data[0]
        sources: list[SourceResult] = []

        for row in data[1:]:
            row_map = dict(zip(headers, row))
            url = row_map.get("original", "")
            ts = row_map.get("timestamp", "")
            snapshot = ""
            try:
                snapshot = datetime.strptime(ts[:14], "%Y%m%d%H%M%S").isoformat()
            except (ValueError, IndexError):
                snapshot = ts

            wayback_url = f"{self.settings.archive_wayback_url}/{ts}/{url}" if ts else ""

            sources.append(
                SourceResult(
                    metadata=SourceMetadata(
                        url=url,
                        source_type=SourceType.INTERNET_ARCHIVE,
                        language="unknown",
                        discovered_by_query=query,
                        snapshot_date=snapshot,
                        status_code=int(row_map.get("statuscode", 0)) or None,
                        fetch_status=FetchStatus.SUCCESS,
                        archive_url=wayback_url,
                    ),
                )
            )

        return ConnectorResult(sources=sources)

    async def health(self) -> bool:
        import httpx

        try:
            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.get(
                    self.settings.archive_cdx_url,
                    params={"url": "example.com", "output": "json", "limit": 1},
                )
                return resp.status_code == 200
        except Exception:
            return False

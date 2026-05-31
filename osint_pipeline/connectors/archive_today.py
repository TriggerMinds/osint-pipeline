from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import re

import httpx

from ..models.source import SourceMetadata, SourceResult, SourceType, FetchStatus
from .base import BaseConnector, ConnectorResult, _compact_error
from .errors import ConnectorError


@dataclass
class ArchiveTodayParams:
    url: str
    limit: int = 20


class ArchiveTodayConnector(BaseConnector):
    BASE_URL = "https://archive.ph"

    def __init__(self) -> None:
        super().__init__()

    async def search(self, query: str, **kwargs) -> ConnectorResult:
        params = ArchiveTodayParams(url=query)
        return await self._search(params)

    async def _search(self, params: ArchiveTodayParams) -> ConnectorResult:
        now = datetime.now(timezone.utc).isoformat()
        sources: list[SourceResult] = []
        domains = ["https://archive.ph", "https://archive.is", "https://archive.fo"]

        for domain in domains:
            search_url = f"{domain}/search/"
            async with httpx.AsyncClient(
                timeout=self.settings.request_timeout, follow_redirects=True
            ) as client:
                try:
                    resp = await self._request_with_retry(
                        client, "GET", search_url, params={"q": params.url},
                    )
                except ConnectorError:
                    continue

                if resp.status_code != 200:
                    continue

                snapshot_pattern = re.compile(rf'{re.escape(domain)}/(\d{{14}})/')
                for match in snapshot_pattern.finditer(resp.text):
                    ts = match.group(1)
                    snapshot_url = f"{domain}/{ts}/{params.url}"
                    try:
                        sd = datetime.strptime(ts[:14], "%Y%m%d%H%M%S").isoformat()
                    except (ValueError, IndexError):
                        sd = ts
                    sources.append(SourceResult(
                        metadata=SourceMetadata(
                            url=params.url,
                            source_type=SourceType.ARCHIVE_TODAY,
                            language="unknown",
                            discovered_by_query=params.url,
                            discovered_at=now,
                            snapshot_date=sd,
                            domain=domain.replace("https://", ""),
                            fetch_status=FetchStatus.SUCCESS,
                            archive_url=snapshot_url,
                        ),
                    ))
                    if len(sources) >= params.limit:
                        break

        return ConnectorResult(sources=sources)

    async def health(self) -> bool:
        async with httpx.AsyncClient(timeout=5) as client:
            try:
                resp = await client.get(f"{self.BASE_URL}/", follow_redirects=True)
                return resp.status_code == 200
            except Exception:
                return False

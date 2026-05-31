from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional

import httpx

from ..config import get_settings
from ..models.source import SourceResult


@dataclass
class ConnectorResult:
    sources: list[SourceResult]
    error: Optional[str] = None


class BaseConnector(ABC):
    def __init__(self) -> None:
        self.settings = get_settings()

    @abstractmethod
    async def search(self, query: str, **kwargs) -> ConnectorResult:
        ...

    @abstractmethod
    async def health(self) -> bool:
        ...

    async def _request_with_retry(
        self,
        client: httpx.AsyncClient,
        method: str,
        url: str,
        *,
        params: dict | None = None,
        json: dict | None = None,
        headers: dict | None = None,
        timeout: int | None = None,
    ) -> httpx.Response:
        last_exc: Exception | None = None
        retries = self.settings.request_retries
        base_delay = self.settings.request_backoff_factor

        for attempt in range(retries + 1):
            try:
                resp = await client.request(
                    method, url,
                    params=params,
                    json=json,
                    headers=headers,
                    timeout=timeout or self.settings.request_timeout,
                )
                return resp
            except (httpx.TimeoutException, httpx.ConnectError, httpx.RemoteProtocolError) as exc:
                last_exc = exc
                if attempt < retries:
                    delay = base_delay * (2 ** attempt)
                    await asyncio.sleep(delay)
                continue

        raise last_exc  # type: ignore[misc]

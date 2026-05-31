from __future__ import annotations

import asyncio
import random
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
        self._retry_codes = {
            int(c.strip())
            for c in self.settings.retry_status_codes.split(",")
            if c.strip()
        }
        self._no_retry_codes = {400, 401, 403, 404, 410}

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
        max_backoff = self.settings.request_max_backoff
        jitter = self.settings.request_jitter

        for attempt in range(retries + 1):
            try:
                resp = await client.request(
                    method, url,
                    params=params,
                    json=json,
                    headers=headers,
                    timeout=timeout or self.settings.request_timeout,
                )

                status = resp.status_code

                if status in self._no_retry_codes:
                    return resp

                if status in self._retry_codes:
                    if attempt < retries:
                        delay = self._get_retry_delay(resp, attempt, base_delay, max_backoff, jitter)
                        await asyncio.sleep(delay)
                        continue
                    raise RuntimeError(
                        f"Request to {url} returned status {status} "
                        f"after {retries + 1} attempt(s)"
                    )

                return resp

            except (httpx.TimeoutException, httpx.ConnectError, httpx.RemoteProtocolError) as exc:
                last_exc = exc
                if attempt < retries:
                    delay = min(base_delay * (2 ** attempt), max_backoff)
                    if jitter > 0:
                        delay += random.uniform(0, jitter)
                    await asyncio.sleep(delay)
                continue

        if last_exc:
            raise last_exc  # type: ignore[misc]

        raise RuntimeError(
            f"Request to {url} failed after {retries + 1} attempt(s)"
        )

    @staticmethod
    def _get_retry_delay(
        resp: httpx.Response,
        attempt: int,
        base_delay: float,
        max_backoff: float,
        jitter: float,
    ) -> float:
        retry_after = resp.headers.get("Retry-After")
        if retry_after is not None:
            try:
                delay = float(retry_after)
                return min(delay, max_backoff)
            except (ValueError, TypeError):
                pass

        delay = base_delay * (2 ** attempt)
        if jitter > 0:
            delay += random.uniform(0, jitter)
        return min(delay, max_backoff)

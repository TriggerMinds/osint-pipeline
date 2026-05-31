from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional

from ..models.source import SourceResult


@dataclass
class ConnectorResult:
    sources: list[SourceResult]
    error: Optional[str] = None


class BaseConnector(ABC):
    @abstractmethod
    async def search(self, query: str, **kwargs) -> ConnectorResult:
        ...

    @abstractmethod
    async def health(self) -> bool:
        ...

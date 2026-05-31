from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class RuntimeCheckResult:
    available: bool
    message: str = ""
    details: dict = field(default_factory=dict)


@dataclass
class BrowserRenderResult:
    html: str
    markdown: str = ""
    text: str = ""
    screenshot: Optional[bytes] = None
    error: Optional[str] = None


class BrowserRuntime(ABC):
    @abstractmethod
    async def health(self) -> RuntimeCheckResult:
        ...

    @abstractmethod
    async def render(self, url: str) -> BrowserRenderResult:
        ...

    @abstractmethod
    async def close(self) -> None:
        ...

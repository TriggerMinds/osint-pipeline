from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Dict, List, Optional


@dataclass
class ProviderConfig:
    name: str
    model: str
    api_key: str
    base_url: str
    temperature: float = 0.1
    max_tokens: int = 4096
    extra_params: Dict[str, Any] = field(default_factory=dict)


class LLMProvider(ABC):
    def __init__(self, config: ProviderConfig) -> None:
        self.config = config

    @abstractmethod
    async def chat(
        self,
        messages: List[Dict[str, str]],
        response_format: Optional[Dict[str, str]] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> str:
        ...

    @abstractmethod
    async def chat_stream(
        self,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> AsyncIterator[str]:
        ...

    @abstractmethod
    async def embed(self, texts: List[str]) -> List[List[float]]:
        ...

from __future__ import annotations

from typing import Optional
from pydantic import BaseModel, Field


class ExpandedQuery(BaseModel):
    original: str
    variants: list[str] = Field(default_factory=list)
    language: str = "en"
    rationale: str = ""


class MultilingualQuery(BaseModel):
    original: str
    target_language: str
    translated: str
    transliteration: Optional[str] = None

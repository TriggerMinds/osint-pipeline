from __future__ import annotations

from typing import Optional
from pydantic import BaseModel, Field


class ExpandedQuery(BaseModel):
    original: str
    variants: list[str] = Field(min_length=1)
    language: str
    rationale: str = ""


class MultilingualQuery(BaseModel):
    original: str
    target_language: str
    translated: str
    transliteration: Optional[str] = None

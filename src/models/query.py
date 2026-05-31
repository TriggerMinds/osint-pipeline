from __future__ import annotations
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class DorkOperator(str, Enum):
    SITE = "site"
    INTITLE = "intitle"
    INURL = "inurl"
    INTEXT = "intext"
    FILETYPE = "filetype"
    INANCHOR = "inanchor"
    LINK = "link"
    RELATED = "related"
    CACHE = "cache"
    NUMRANGE = "numrange"
    DATERANGE = "daterange"
    BEFORE = "before"
    AFTER = "after"
    ALLINTITLE = "allintitle"
    ALLINURL = "allinurl"
    ALLINTEXT = "allintext"
    SOURCE = "source"


class DorkQuery(BaseModel):
    raw_query: str
    operators: Dict[DorkOperator, List[str]] = Field(default_factory=dict)
    target_source: str = "google"
    description: str = ""
    language: str = "en"


class ExpandedQuery(BaseModel):
    original_intent: str
    queries: List[str] = Field(default_factory=list)
    dork_queries: List[DorkQuery] = Field(default_factory=list)
    expansion_rationale: str = ""


class MultilingualQuery(BaseModel):
    original_query: str
    language: str
    translated_query: str
    transliteration: Optional[str] = None
    source_language: str = "en"


class QueryBatch(BaseModel):
    intent_id: str
    expanded_queries: List[ExpandedQuery] = Field(default_factory=list)
    multilingual_queries: List[MultilingualQuery] = Field(default_factory=list)
    dork_queries: List[DorkQuery] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)

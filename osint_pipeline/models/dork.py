from __future__ import annotations

from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class DorkOperator(str, Enum):
    SITE = "site"
    INTITLE = "intitle"
    INURL = "inurl"
    INTEXT = "intext"
    FILETYPE = "filetype"
    INANCHOR = "inanchor"
    BEFORE = "before"
    AFTER = "after"
    ALLINTITLE = "allintitle"
    ALLINURL = "allinurl"
    ALLINTEXT = "allintext"
    SOURCE = "source"
    NUMRANGE = "numrange"


class DorkTarget(str, Enum):
    GOOGLE = "google"
    BING = "bing"
    DUCKDUCKGO = "duckduckgo"
    YANDEX = "yandex"
    SEARXNG = "searxng"
    ARCHIVE_CDX = "archive_cdx"
    GDELT = "gdelt"
    COMMONCRAWL = "commoncrawl"
    OPENALEX = "openalex"
    GITHUB = "github"
    REDDIT = "reddit"
    WIKIDATA = "wikidata"


class RiskLevel(str, Enum):
    SAFE = "safe"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class DorkQuery(BaseModel):
    raw: str = Field(min_length=1)
    operators: dict[DorkOperator, list[str]] = Field(default_factory=dict)
    target: DorkTarget = DorkTarget.GOOGLE
    description: str = ""
    language: str = ""
    purpose: str = ""
    expected_signal: str = ""
    risk_level: RiskLevel = RiskLevel.SAFE


class ExpandedIntent(BaseModel):
    original_query: str = ""
    intent: str = ""
    entities: list[str] = Field(default_factory=list)
    languages: list[str] = Field(default_factory=lambda: ["nl", "en", "de", "fr"])


class DorkSchema(BaseModel):
    schema_version: str = "1.0"
    description: str = ""
    intent: ExpandedIntent = Field(default_factory=ExpandedIntent)
    entities: list[str] = Field(default_factory=list)
    languages: list[str] = Field(default_factory=lambda: ["nl", "en", "de", "fr"])
    negative_terms: list[str] = Field(default_factory=list)
    validation_rules: dict[str, str] = Field(default_factory=dict)
    dork_queries: list[DorkQuery] = Field(default_factory=list)

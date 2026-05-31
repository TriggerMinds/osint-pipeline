from __future__ import annotations

from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


ALLOWED_CONNECTORS = [
    "searxng", "gdelt", "openalex", "archive_cdx",
    "commoncrawl", "archive_today", "github", "wikidata", "reddit",
]

ALLOWED_PROFILES = [
    "smoke", "archive_first", "deleted_content",
    "multi_engine", "foreign_index", "deep_archive",
]

ALLOWED_ARCHIVE_PREFERENCES = ["live_first", "archive_first", "archive_only"]

FORBIDDEN_PHRASES = ["zero-attribution", "100% anonymous", "no DNS leaks guaranteed", "uncensored"]


class ResearchIntent(str, Enum):
    GENERAL_RESEARCH = "general_research"
    DELETED_CONTENT = "deleted_content"
    ARCHIVE_LOOKUP = "archive_lookup"
    ENTITY_INVESTIGATION = "entity_investigation"
    NEWS_MONITORING = "news_monitoring"
    ACADEMIC_RESEARCH = "academic_research"
    CODE_SEARCH = "code_search"
    SOCIAL_DISCUSSION = "social_discussion"
    DOCUMENT_SEARCH = "document_search"
    CROSS_LANGUAGE_SEARCH = "cross_language_search"
    VERIFICATION = "verification"


class QuerySeed(BaseModel):
    raw_query: str
    entities: list[str] = Field(default_factory=list)
    domains: list[str] = Field(default_factory=list)
    urls: list[str] = Field(default_factory=list)
    filenames: list[str] = Field(default_factory=list)
    quoted_phrases: list[str] = Field(default_factory=list)
    languages_hint: list[str] = Field(default_factory=list)
    date_range: Optional[dict] = None


class ConnectorPlan(BaseModel):
    connector: str
    reason: str = ""
    required: bool = False
    max_tasks: int = 3
    max_results: int = 20


class ResearchPlan(BaseModel):
    intent: ResearchIntent = ResearchIntent.GENERAL_RESEARCH
    confidence: float = Field(default=0.7, ge=0.0, le=1.0)
    profile: str = "multi_engine"
    query_seed: QuerySeed = Field(default_factory=lambda: QuerySeed(raw_query=""))
    languages: list[str] = Field(default_factory=lambda: ["nl", "en"])
    archive_preference: str = "live_first"
    searxng_strategy: str = "multi_engine"
    connectors: list[ConnectorPlan] = Field(default_factory=list)
    required_connectors: list[str] = Field(default_factory=list)
    query_strategies: list[str] = Field(default_factory=list)
    second_pass: bool = True
    planner_warnings: list[str] = Field(default_factory=list)

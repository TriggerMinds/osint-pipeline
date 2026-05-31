from __future__ import annotations

import re

from .models import (
    ResearchIntent, ResearchPlan, QuerySeed, ConnectorPlan,
    ALLOWED_CONNECTORS, ALLOWED_PROFILES, ALLOWED_ARCHIVE_PREFERENCES,
)
from .extract import extract_query_seed

DELETED_TRIGGERS = [
    "verwijderd", "deleted", "offline", "verdwenen",
    "niet meer online", "oude versie", "archief", "snapshot",
    "wayback", "archive", "archive.today", "archive.ph", "cache",
]

DOCUMENT_TRIGGERS = [
    ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".csv", ".zip",
    "rapport", "document", "bestand", "filename", "filetype",
]

ACADEMIC_TRIGGERS = [
    "paper", "onderzoek", "studie", "doi", "universiteit",
    "journal", "wetenschappelijk", "academic", "research",
]

NEWS_TRIGGERS = [
    "nieuws", "media", "artikel", "berichtgeving",
    "vandaag", "gisteren", "laatste", "recent", "news",
    "report", "coverage",
]


def _has_trigger(query_lower: str, triggers: list[str]) -> bool:
    return any(t in query_lower for t in triggers)


def rule_based_plan(query: str) -> ResearchPlan:
    seed = extract_query_seed(query)
    query_lower = query.lower()

    # Deleted content
    if _has_trigger(query_lower, DELETED_TRIGGERS):
        return ResearchPlan(
            intent=ResearchIntent.DELETED_CONTENT,
            confidence=0.85,
            profile="deleted_content",
            query_seed=seed,
            languages=seed.languages_hint,
            archive_preference="archive_only",
            searxng_strategy="file_discovery",
            connectors=[
                ConnectorPlan(connector="archive_cdx", reason="URL/domain archive lookup", required=True),
                ConnectorPlan(connector="commoncrawl", reason="Historical web crawl", required=True),
                ConnectorPlan(connector="archive_today", reason="archive.today snapshot search", required=True),
                ConnectorPlan(connector="searxng", reason="Web index for cached/archived references"),
            ],
            required_connectors=["archive_cdx", "commoncrawl", "archive_today"],
            query_strategies=["exact_url", "domain", "filename", "quoted_phrase", "archive_lookup"],
        )

    # URL/domain
    if seed.urls or seed.domains:
        return ResearchPlan(
            intent=ResearchIntent.ARCHIVE_LOOKUP,
            confidence=0.8,
            profile="archive_first",
            query_seed=seed,
            languages=seed.languages_hint,
            archive_preference="archive_first",
            searxng_strategy="file_discovery",
            connectors=[
                ConnectorPlan(connector="archive_cdx", reason="Specific URL/domain archive lookup", required=True),
                ConnectorPlan(connector="archive_today", reason="archive.today snapshot", required=True),
                ConnectorPlan(connector="commoncrawl", reason="Historical web crawl data"),
                ConnectorPlan(connector="searxng", reason="Web index for cached references"),
            ],
            required_connectors=["archive_cdx", "archive_today"],
            query_strategies=["exact_url", "url_without_params", "domain", "archive_lookup"],
        )

    # Document search
    if _has_trigger(query_lower, DOCUMENT_TRIGGERS) or seed.filenames:
        return ResearchPlan(
            intent=ResearchIntent.DOCUMENT_SEARCH,
            confidence=0.8,
            profile="multi_engine",
            query_seed=seed,
            languages=seed.languages_hint,
            archive_preference="archive_first",
            searxng_strategy="multi_engine",
            connectors=[
                ConnectorPlan(connector="searxng", reason="Web search for documents"),
                ConnectorPlan(connector="archive_cdx", reason="Archived document lookup"),
                ConnectorPlan(connector="commoncrawl", reason="Historical document crawl"),
                ConnectorPlan(connector="github", reason="Documents stored in repositories"),
            ],
            query_strategies=["filename", "filetype", "exact_title", "archive_lookup"],
        )

    # Academic
    if _has_trigger(query_lower, ACADEMIC_TRIGGERS):
        return ResearchPlan(
            intent=ResearchIntent.ACADEMIC_RESEARCH,
            confidence=0.85,
            profile="multi_engine",
            query_seed=seed,
            languages=seed.languages_hint,
            archive_preference="archive_first",
            searxng_strategy="multi_engine",
            connectors=[
                ConnectorPlan(connector="openalex", reason="Academic publications", required=True),
                ConnectorPlan(connector="searxng", reason="General web for academic content"),
                ConnectorPlan(connector="archive_cdx", reason="Archived academic pages"),
            ],
            required_connectors=["openalex"],
            query_strategies=["academic", "title", "author", "doi"],
        )

    # News
    if _has_trigger(query_lower, NEWS_TRIGGERS):
        return ResearchPlan(
            intent=ResearchIntent.NEWS_MONITORING,
            confidence=0.85,
            profile="multi_engine",
            query_seed=seed,
            languages=seed.languages_hint,
            archive_preference="archive_first",
            searxng_strategy="multi_engine",
            connectors=[
                ConnectorPlan(connector="gdelt", reason="Global news monitoring", required=True),
                ConnectorPlan(connector="searxng", reason="General web for news context"),
                ConnectorPlan(connector="archive_cdx", reason="Archived news articles"),
            ],
            required_connectors=["gdelt"],
            query_strategies=["news", "timeline", "archive"],
        )

    # Entity investigation (names with capitals, >4 chars)
    if seed.entities and not seed.urls:
        return ResearchPlan(
            intent=ResearchIntent.ENTITY_INVESTIGATION,
            confidence=0.7,
            profile="foreign_index",
            query_seed=seed,
            languages=seed.languages_hint + ["en", "ru", "zh", "ar"],
            archive_preference="archive_first",
            searxng_strategy="regional_diverse",
            connectors=[
                ConnectorPlan(connector="searxng", reason="Multi-regional entity search"),
                ConnectorPlan(connector="gdelt", reason="News about entity"),
                ConnectorPlan(connector="wikidata", reason="Entity data from Wikidata", required=True),
                ConnectorPlan(connector="archive_cdx", reason="Historical entity references"),
                ConnectorPlan(connector="commoncrawl", reason="Historical web data"),
            ],
            required_connectors=["wikidata"],
            query_strategies=["exact_name", "aliases", "organizations", "news", "archive"],
        )

    # Default
    return ResearchPlan(
        intent=ResearchIntent.GENERAL_RESEARCH,
        confidence=0.6,
        profile="multi_engine",
        query_seed=seed,
        languages=seed.languages_hint,
        archive_preference="archive_first",
        searxng_strategy="multi_engine",
        connectors=[
            ConnectorPlan(connector="searxng", reason="General web search"),
            ConnectorPlan(connector="gdelt", reason="News and current events"),
            ConnectorPlan(connector="openalex", reason="Academic publications"),
            ConnectorPlan(connector="archive_cdx", reason="Archival web records"),
            ConnectorPlan(connector="commoncrawl", reason="Historical web crawl data"),
        ],
        query_strategies=["web", "news", "academic", "archive"],
    )

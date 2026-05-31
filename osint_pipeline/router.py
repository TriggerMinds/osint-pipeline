from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .models.dork import DorkQuery, DorkTarget
from .models.evidence import EvidenceCollection
from .models.lineage import QueryLineage


class RouterError(Exception):
    """Raised when a dork target cannot be routed."""

    def __init__(self, target: str, map_name: str) -> None:
        self.target = target
        self.map_name = map_name
        super().__init__(f"Unknown target '{target}' in {map_name}")


TARGET_CONNECTOR_MAP: dict[DorkTarget, str] = {
    DorkTarget.GOOGLE: "searxng",
    DorkTarget.BING: "searxng",
    DorkTarget.DUCKDUCKGO: "searxng",
    DorkTarget.YANDEX: "searxng",
    DorkTarget.SEARXNG: "searxng",
    DorkTarget.ARCHIVE_CDX: "archive_cdx",
    DorkTarget.GDELT: "gdelt",
    DorkTarget.COMMONCRAWL: "commoncrawl",
    DorkTarget.OPENALEX: "openalex",
    DorkTarget.GITHUB: "github",
    DorkTarget.REDDIT: "reddit",
    DorkTarget.WIKIDATA: "wikidata",
}

TARGET_EXECUTION_MODE: dict[DorkTarget, str] = {
    DorkTarget.GOOGLE: "web_search",
    DorkTarget.BING: "web_search",
    DorkTarget.DUCKDUCKGO: "web_search",
    DorkTarget.YANDEX: "web_search",
    DorkTarget.SEARXNG: "web_search",
    DorkTarget.ARCHIVE_CDX: "archive_lookup",
    DorkTarget.GDELT: "news_search",
    DorkTarget.COMMONCRAWL: "archive_lookup",
    DorkTarget.OPENALEX: "academic_search",
    DorkTarget.GITHUB: "code_search",
    DorkTarget.REDDIT: "social_search",
    DorkTarget.WIKIDATA: "entity_search",
}

TARGET_REASON: dict[DorkTarget, str] = {
    DorkTarget.GOOGLE: "General web index via SearXNG metasearch",
    DorkTarget.BING: "Microsoft web index via SearXNG metasearch",
    DorkTarget.DUCKDUCKGO: "Privacy-focused search via SearXNG metasearch",
    DorkTarget.YANDEX: "Eastern European web index via SearXNG metasearch",
    DorkTarget.SEARXNG: "Direct SearXNG metasearch instance",
    DorkTarget.ARCHIVE_CDX: "Internet Archive CDX for historical webpage snapshots",
    DorkTarget.GDELT: "Global news and events monitoring via GDELT API",
    DorkTarget.COMMONCRAWL: "Historical web crawl data via Common Crawl index",
    DorkTarget.OPENALEX: "Academic publications and research works",
    DorkTarget.GITHUB: "Source code, repositories and issues on GitHub",
    DorkTarget.REDDIT: "Social media discussions and posts on Reddit",
    DorkTarget.WIKIDATA: "Structured entity data from Wikidata SPARQL endpoint",
}


@dataclass
class RouteResult:
    connector: str
    execution_mode: str
    reason: str
    target: DorkTarget
    purpose: str = ""
    risk_level: str = ""
    language: str = ""


class SourceRouter:
    def route(self, dork: DorkQuery) -> RouteResult:
        target = dork.target
        target_str = target.value if isinstance(target, DorkTarget) else str(target)

        if target not in TARGET_CONNECTOR_MAP:
            raise RouterError(target_str, "TARGET_CONNECTOR_MAP")
        if target not in TARGET_EXECUTION_MODE:
            raise RouterError(target_str, "TARGET_EXECUTION_MODE")
        if target not in TARGET_REASON:
            raise RouterError(target_str, "TARGET_REASON")

        connector = TARGET_CONNECTOR_MAP[target]
        exec_mode = TARGET_EXECUTION_MODE[target]
        reason = TARGET_REASON[target]

        return RouteResult(
            connector=connector,
            execution_mode=exec_mode,
            reason=reason,
            target=target,
            purpose=dork.purpose,
            risk_level=dork.risk_level.value,
            language=dork.language,
        )

    def route_schema(self, dorks: list[DorkQuery]) -> list[RouteResult]:
        return [self.route(d) for d in dorks]

    def build_lineage(
        self,
        dork: DorkQuery,
        route: RouteResult,
        lineage_id: str = "",
        original_query: str = "",
    ) -> QueryLineage:
        return QueryLineage(
            id=lineage_id,
            original_query=original_query,
            expanded_query=dork.raw,
            language=dork.language or "en",
            dork_raw=dork.raw,
            dork_target=dork.target.value,
            connector=route.connector,
        )

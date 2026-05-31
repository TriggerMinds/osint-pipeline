from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Optional

from ..config import get_settings
from ..query_expansion import QueryExpander, QueryExpanderError
from ..dork_generation import DorkGenerator, DorkGeneratorError
from ..connectors import (
    SearXNGConnector, GDELTConnector, ArchiveCDXConnector, CommonCrawlConnector,
    OpenAlexConnector, GitHubSearchConnector, WikidataConnector, RedditConnector,
)
from ..extraction import EvidenceExtractor, EvidenceExtractorError
from ..ranking import EvidenceRanker
from ..crawler import Crawl4AIAdapter
from ..router import RouterError, SourceRouter
from ..graphrag import EvidenceGraphBuilder
from ..models.source import SourceResult
from ..models.lineage import ResearchRun, QueryLineage
from ..models.evidence import EvidenceCollection
from .artifacts import ResearchArtifact, ConnectorExecutionResult, TimingBreakdown, GraphSummary
from .sanitize import sanitize_error_message


@dataclass
class ResearchRunConfig:
    max_results: int = 50
    enrich: bool = False
    max_crawl_urls: int = 10


_CONNECTOR_INSTANCES: dict[str, object] | None = None


def _get_connector(name: str):
    global _CONNECTOR_INSTANCES
    if _CONNECTOR_INSTANCES is None:
        _CONNECTOR_INSTANCES = {
            "searxng": SearXNGConnector(),
            "gdelt": GDELTConnector(),
            "archive_cdx": ArchiveCDXConnector(),
            "commoncrawl": CommonCrawlConnector(),
            "openalex": OpenAlexConnector(),
            "github": GitHubSearchConnector(),
            "wikidata": WikidataConnector(),
            "reddit": RedditConnector(),
        }
    return _CONNECTOR_INSTANCES.get(name)


def _dedup_sources(sources: list[SourceResult]) -> list[SourceResult]:
    seen: set[str] = set()
    deduped: list[SourceResult] = []
    for s in sources:
        key = s.metadata.url.rstrip("/").lower()
        if key not in seen:
            seen.add(key)
            deduped.append(s)
    return deduped


class ResearchRunner:
    def __init__(self) -> None:
        self.settings = get_settings()

    async def run(self, query: str, config: ResearchRunConfig | None = None) -> ResearchArtifact:
        cfg = config or ResearchRunConfig()
        run_id = f"run_{uuid.uuid4().hex[:12]}"
        artifact = ResearchArtifact(run_id=run_id, query=query)
        run_model = ResearchRun(id=run_id, original_query=query)
        timing = TimingBreakdown()

        # Step 1: Expand
        t0 = time.time()
        try:
            expander = QueryExpander()
            expanded = await expander.expand(query)
        except QueryExpanderError as e:
            artifact.add_error(f"expansion failed: {e}")
            expanded = []
        timing.expand = time.time() - t0

        # Step 2: Generate dorks
        t0 = time.time()
        try:
            dork_gen = DorkGenerator()
            schema = await dork_gen.generate(query, expanded or None)
        except DorkGeneratorError as e:
            artifact.add_error(f"dork generation failed: {e}")
            schema = None
        timing.dork = time.time() - t0

        # Step 3: Route & execute
        t0 = time.time()
        router = SourceRouter()
        all_sources: list[SourceResult] = []
        lineages: list[QueryLineage] = []
        conn_results: list[ConnectorExecutionResult] = []

        dorks = (schema.dork_queries if schema else [])[:cfg.max_results]

        for i, d in enumerate(dorks):
            try:
                route = router.route(d)
            except RouterError as e:
                artifact.add_error(f"dork[{i}]: {e}")
                continue

            conn = _get_connector(route.connector)
            if conn is None:
                artifact.add_error(f"dork[{i}]: no connector for '{route.connector}'")
                continue

            li = router.build_lineage(d, route, lineage_id=f"l_{i:03d}", original_query=query)
            lineages.append(li)

            query_for_search = d.raw or d.description or query
            try:
                result = await conn.search(query_for_search, language=d.language or "en")  # type: ignore
            except Exception as exc:
                artifact.add_error(f"dork[{i}] ({route.connector}): {type(exc).__name__}: {exc}")
                continue

            if result.error:
                artifact.add_error(f"dork[{i}] ({route.connector}): {result.error}")

            for src in result.sources:
                src.metadata.run_id = run_id
                src.metadata.query_lineage_id = li.id
                src.metadata.discovered_by_query = query_for_search

            all_sources.extend(result.sources)

            conn_results.append(ConnectorExecutionResult(
                connector=route.connector,
                query=query_for_search,
                sources_found=len(result.sources),
                error=result.error,
            ))

        # Step 4: Deduplicate
        all_sources = _dedup_sources(all_sources)
        timing.fetch = time.time() - t0

        # Step 5: Crawl enrichment (optional)
        t0 = time.time()
        if cfg.enrich:
            crawl_adapter = Crawl4AIAdapter()
            if crawl_adapter.available:
                proxy = self.settings.proxy_url or None
                for src in all_sources[:cfg.max_crawl_urls]:
                    if src.content is None or not src.content.strip():
                        try:
                            crawled = await crawl_adapter.crawl_url(src.metadata.url, proxy_url=proxy)
                            if crawled and crawled.content:
                                src.content = crawled.content
                        except Exception as exc:
                            artifact.add_error(f"crawl enrichment: {type(exc).__name__}: {exc}")
        timing.crawl = time.time() - t0

        # Step 6: Extract evidence
        t0 = time.time()
        try:
            extractor = EvidenceExtractor()
            evidence = await extractor.extract(all_sources)
        except (EvidenceExtractorError, Exception) as exc:
            artifact.add_error(f"evidence extraction: {type(exc).__name__}: {exc}")
            evidence = EvidenceCollection(query=query)
        timing.extract = time.time() - t0

        # Step 7: Rank
        t0 = time.time()
        ranker = EvidenceRanker()
        evidence = ranker.rank(evidence)
        timing.rank = time.time() - t0

        # Step 8: Build graph
        graph_builder = EvidenceGraphBuilder()
        graph = graph_builder.build(evidence, lineage=lineages)

        # Assemble artifact
        artifact.status = "completed_with_errors" if artifact.errors else "completed"
        artifact.timing = timing
        artifact.expansions = [e.model_dump() for e in expanded]
        artifact.dorks = [d.model_dump() for d in dorks]
        artifact.routes = len(lineages)
        artifact.connector_results = conn_results
        artifact.sources_fetched = len(all_sources)
        artifact.claims_extracted = sum(len(ev.claims) for ev in evidence.items)
        artifact.lineages = [li.model_dump() for li in lineages]
        artifact.evidence = {
            "items": [ev.model_dump() for ev in evidence.items[:50]],
            "conflicting_claims": [
                {"claim": c.claim, "confidence": c.confidence, "conflict_status": c.conflict_status.value}
                for ev in evidence.items for c in ev.claims
                if c.conflict_status.value in ("conflicting", "archive_only", "disappeared")
            ],
        }
        artifact.graph = GraphSummary(nodes=len(graph.nodes), edges=len(graph.edges))

        # Sanitize all collected errors
        artifact.errors = [sanitize_error_message(e) for e in artifact.errors]

        run_model.status = artifact.status
        run_model.total_sources = artifact.sources_fetched

        return artifact

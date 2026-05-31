from __future__ import annotations

import re
import time
import uuid
from dataclasses import dataclass, field
from typing import Optional
from urllib.parse import urlparse, urlencode, parse_qs, urlunparse

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
from ..models.evidence import EvidenceCollection, EvidenceClaim
from .artifacts import ResearchArtifact, ConnectorExecutionResult, TimingBreakdown, GraphSummary
from .sanitize import sanitize_error_message

_TRACKING_PARAMS = re.compile(r"^(utm_|fbclid|gclid|mc_cid|mc_eid|_ga|_gl)", re.IGNORECASE)


@dataclass
class ResearchRunConfig:
    max_dorks: int = 25
    max_results: int = 50
    max_results_per_connector: int = 20
    max_crawl_urls: int = 10
    enrich: bool = False
    enabled_connectors: Optional[list[str]] = None
    disabled_connectors: Optional[list[str]] = None
    enabled_languages: Optional[list[str]] = None
    min_evidence_confidence: float = 0.0
    dedup_mode: str = "url"  # url, canonical_url, domain_url
    crawl_enrichment_policy: str = "missing_content"  # none, missing_content, top_ranked
    archive_preference: str = "live_first"  # live_first, archive_first, archive_only
    source_score_threshold: float = 0.0


_ALL_CONNECTORS = [
    "searxng", "gdelt", "archive_cdx", "commoncrawl",
    "openalex", "github", "wikidata", "reddit",
]

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


def _canonical_url(url: str, mode: str = "url") -> str:
    if mode == "domain_url":
        try:
            parsed = urlparse(url)
            return f"{parsed.scheme}://{parsed.netloc.lower()}"
        except Exception:
            return url
    key = url.rstrip("/").lower()
    if mode == "canonical_url":
        try:
            parsed = urlparse(key)
            params = parse_qs(parsed.query, keep_blank_values=True)
            clean = {k: v for k, v in params.items() if not _TRACKING_PARAMS.match(k)}
            query = urlencode(clean, doseq=True) if clean else ""
            key = urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, query, parsed.fragment))
        except Exception:
            pass
    return key


def _dedup_sources(sources: list[SourceResult], mode: str = "url") -> list[SourceResult]:
    seen: set[str] = set()
    deduped: list[SourceResult] = []
    for s in sources:
        key = _canonical_url(s.metadata.url, mode)
        if key not in seen:
            seen.add(key)
            deduped.append(s)
    return deduped


def _filter_by_confidence(collection: EvidenceCollection, min_conf: float) -> EvidenceCollection:
    for ev in collection.items:
        ev.claims = [c for c in ev.claims if c.confidence >= min_conf]
    collection.items = [ev for ev in collection.items if ev.claims]
    return collection


class ResearchRunner:
    def __init__(self) -> None:
        self.settings = get_settings()

    async def run(self, query: str, config: ResearchRunConfig | None = None) -> ResearchArtifact:
        cfg = config or ResearchRunConfig()
        run_id = f"run_{uuid.uuid4().hex[:12]}"
        artifact = ResearchArtifact(run_id=run_id, query=query)
        run_model = ResearchRun(id=run_id, original_query=query)
        timing = TimingBreakdown()

        # Build connector allowlist
        enabled = cfg.enabled_connectors or _ALL_CONNECTORS
        if cfg.disabled_connectors:
            enabled = [c for c in enabled if c not in cfg.disabled_connectors]
        enabled_set = set(enabled)

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
        per_connector_counts: dict[str, int] = {}

        dorks = (schema.dork_queries if schema else [])[:cfg.max_dorks]

        # Filter dorks by language if enabled_languages set
        if cfg.enabled_languages:
            dorks = [d for d in dorks if d.language in cfg.enabled_languages or not d.language]

        for i, d in enumerate(dorks):
            try:
                route = router.route(d)
            except RouterError as e:
                artifact.add_error(f"dork[{i}]: {e}")
                continue

            if route.connector not in enabled_set:
                continue

            # Per-connector limit
            conn_count = per_connector_counts.get(route.connector, 0)
            if conn_count >= cfg.max_results_per_connector:
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

            # Cap sources per connector
            results_for_connector = result.sources[:cfg.max_results_per_connector]
            per_connector_counts[route.connector] = conn_count + len(results_for_connector)

            for src in results_for_connector:
                src.metadata.run_id = run_id
                src.metadata.query_lineage_id = li.id
                src.metadata.discovered_by_query = query_for_search

            all_sources.extend(results_for_connector)

            conn_results.append(ConnectorExecutionResult(
                connector=route.connector,
                query=sanitize_error_message(query_for_search),
                sources_found=len(results_for_connector),
                error=sanitize_error_message(result.error) if result.error else None,
            ))

        # Step 4: Deduplicate
        all_sources = _dedup_sources(all_sources, mode=cfg.dedup_mode)
        timing.fetch = time.time() - t0

        # Step 5: Source pre-scoring + archive filtering
        if cfg.archive_preference == "archive_only":
            all_sources = [s for s in all_sources if s.metadata.archive_url]
        elif cfg.archive_preference == "archive_first":
            all_sources.sort(key=lambda s: 0 if s.metadata.archive_url else 1)

        if cfg.source_score_threshold > 0:
            all_sources = [s for s in all_sources if self._score_source(s) >= cfg.source_score_threshold]

        all_sources = all_sources[:cfg.max_results]

        # Step 6: Crawl enrichment
        t0 = time.time()
        if cfg.enrich:
            crawl_adapter = Crawl4AIAdapter()
            if crawl_adapter.available:
                proxy = self.settings.proxy_url or None
                candidates = list(all_sources)

                if cfg.crawl_enrichment_policy == "top_ranked":
                    candidates = candidates[:cfg.max_crawl_urls]
                elif cfg.crawl_enrichment_policy == "missing_content":
                    candidates = [s for s in candidates if s.content is None or not s.content.strip()][:cfg.max_crawl_urls]

                for src in candidates:
                    try:
                        crawled = await crawl_adapter.crawl_url(src.metadata.url, proxy_url=proxy)
                        if crawled and crawled.content:
                            src.content = crawled.content
                    except Exception as exc:
                        artifact.add_error(f"crawl enrichment: {type(exc).__name__}: {exc}")
        timing.crawl = time.time() - t0

        # Step 7: Extract evidence
        t0 = time.time()
        try:
            extractor = EvidenceExtractor()
            evidence = await extractor.extract(all_sources)
        except (EvidenceExtractorError, Exception) as exc:
            artifact.add_error(f"evidence extraction: {type(exc).__name__}: {exc}")
            evidence = EvidenceCollection(query=query)
        timing.extract = time.time() - t0

        # Step 8: Rank + filter evidence
        t0 = time.time()
        ranker = EvidenceRanker()
        evidence = ranker.rank(evidence)
        if cfg.min_evidence_confidence > 0:
            evidence = _filter_by_confidence(evidence, cfg.min_evidence_confidence)
        timing.rank = time.time() - t0

        # Step 9: Build graph
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
        artifact.quality_controls = {
            "max_dorks": cfg.max_dorks,
            "max_results": cfg.max_results,
            "max_results_per_connector": cfg.max_results_per_connector,
            "enabled_connectors": sorted(enabled_set),
            "enabled_languages": cfg.enabled_languages,
            "min_evidence_confidence": cfg.min_evidence_confidence,
            "dedup_mode": cfg.dedup_mode,
            "crawl_enrichment_policy": cfg.crawl_enrichment_policy,
            "archive_preference": cfg.archive_preference,
            "source_score_threshold": cfg.source_score_threshold,
        }

        artifact.errors = [sanitize_error_message(e) for e in artifact.errors]

        run_model.status = artifact.status
        run_model.total_sources = artifact.sources_fetched

        return artifact

    @staticmethod
    def _score_source(src: SourceResult) -> float:
        score = 1.0
        if src.metadata.archive_url:
            score -= 0.1
        if src.metadata.fetch_status.value == "error":
            score -= 0.3
        if src.metadata.language == "en":
            score += 0.05
        if src.metadata.snapshot_date:
            score += 0.05
        if src.content:
            score += 0.1
        return min(score, 1.0)

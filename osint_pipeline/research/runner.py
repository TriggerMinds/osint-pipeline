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
    ArchiveTodayConnector,
)
from ..extraction import EvidenceExtractor, EvidenceExtractorError
from ..ranking import EvidenceRanker
from ..crawler import Crawl4AIAdapter
from ..router import RouterError, SourceRouter
from ..graphrag import EvidenceGraphBuilder
from ..models.source import SourceResult
from ..models.lineage import ResearchRun, QueryLineage
from ..models.evidence import EvidenceCollection, EvidenceClaim
from ..models.dork import DorkQuery, DorkTarget
from .artifacts import ResearchArtifact, ConnectorExecutionResult, TimingBreakdown, GraphSummary
from .sanitize import sanitize_error_message
from .executor import AsyncConnectorExecutor, ConnectorExecutionConfig, ConnectorTask, ConnectorTaskResult
from .strategies import build_discovery_strategy

_TRACKING_PARAMS = re.compile(r"^(utm_|fbclid|gclid|mc_cid|mc_eid|_ga|_gl)", re.IGNORECASE)


@dataclass
class ResearchRunConfig:
    max_dorks: int = 25
    max_results: int = 50
    max_tasks_per_connector: int = 3
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
    dry_run: bool = False
    fixture_mode: bool = False
    fixture_dir: Optional[str] = None
    required_connectors: Optional[list[str]] = None
    _profile_name: Optional[str] = None
    max_concurrency: int = 5
    max_concurrency_per_connector: int = 2
    connector_timeout_seconds: float = 30.0
    searxng_strategy: str = "default"
    searxng_engines: tuple[str, ...] = ()


_ALL_CONNECTORS = [
    "searxng", "gdelt", "archive_cdx", "commoncrawl",
    "openalex", "github", "wikidata", "reddit", "archive_today",
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
            "archive_today": ArchiveTodayConnector(),
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
        if cfg.fixture_mode:
            expanded = await self._load_expansions_fixture(cfg, query)
        else:
            try:
                expander = QueryExpander()
                expanded = await expander.expand(query)
            except QueryExpanderError as e:
                artifact.add_error(f"expansion failed: {e}")
                expanded = []
        timing.expand = time.time() - t0

        # Step 2: Generate dorks
        t0 = time.time()
        if cfg.fixture_mode:
            schema = await self._load_dorks_fixture(cfg, query, expanded or None)
        else:
            try:
                dork_gen = DorkGenerator()
                schema = await dork_gen.generate(query, expanded or None)
            except DorkGeneratorError as e:
                artifact.add_error(f"dork generation failed: {e}")
                schema = None
        timing.dork = time.time() - t0

        # Step 3: Route & build task list
        t0 = time.time()
        router = SourceRouter()
        all_sources: list[SourceResult] = []
        lineages: list[QueryLineage] = []
        conn_results: list[ConnectorExecutionResult] = []
        executor_tasks: list[ConnectorTask] = []

        dorks = (schema.dork_queries if schema else [])[:cfg.max_dorks]

        if cfg.enabled_languages:
            dorks = [d for d in dorks if d.language in cfg.enabled_languages or not d.language]

        per_connector_counts: dict[str, int] = {}

        # Inject deleted-content queries for deleted_content profile
        if cfg._profile_name == "deleted_content":
            from .strategies import build_deleted_content_queries
            deleted_targets = [
                ("archive_cdx", DorkTarget.ARCHIVE_CDX),
                ("commoncrawl", DorkTarget.COMMONCRAWL),
                ("archive_today", DorkTarget.ARCHIVE_TODAY),
                ("searxng", DorkTarget.SEARXNG),
            ]
            dc_queries = build_deleted_content_queries(query)
            for conn_name, target in deleted_targets:
                if conn_name not in enabled_set:
                    continue
                cc = per_connector_counts.get(conn_name, 0)
                max_for_connector = cfg.max_tasks_per_connector - cc
                for qi, q in enumerate(dc_queries[:max_for_connector]):
                    dorks.append(DorkQuery(
                        raw=q, target=target,
                        description=f"deleted-content strategy: {q}",
                    ))

        for i, d in enumerate(dorks):
            try:
                route = router.route(d)
            except RouterError as e:
                artifact.add_error(f"dork[{i}]: {e}")
                continue
            if route.connector not in enabled_set:
                continue
            cc = per_connector_counts.get(route.connector, 0)
            if cc >= cfg.max_tasks_per_connector:
                continue
            _c = _get_connector(route.connector)
            if _c is None:
                artifact.add_error(f"dork[{i}]: no connector for '{route.connector}'")
                continue

            li = router.build_lineage(d, route, lineage_id=f"l_{i:03d}", original_query=query)
            lineages.append(li)
            per_connector_counts[route.connector] = cc + 1

            query_for_search = d.raw or d.description or query

            if cfg.dry_run:
                conn_results.append(ConnectorExecutionResult(
                    connector=route.connector, query=sanitize_error_message(query_for_search), sources_found=0,
                ))
                continue

            if cfg.fixture_mode:
                fixture_r = await self._load_fixture(cfg, route.connector, query_for_search)
                if fixture_r is None:
                    artifact.add_error(f"dork[{i}] ({route.connector}): no fixture found")
                    continue
                for src in fixture_r.sources[:cfg.max_results_per_connector]:
                    src.metadata.run_id = run_id
                    src.metadata.query_lineage_id = li.id
                    src.metadata.discovered_by_query = query_for_search
                all_sources.extend(fixture_r.sources[:cfg.max_results_per_connector])
                conn_results.append(ConnectorExecutionResult(
                    connector=route.connector, query=sanitize_error_message(query_for_search),
                    sources_found=min(len(fixture_r.sources), cfg.max_results_per_connector),
                    error=sanitize_error_message(fixture_r.error) if fixture_r.error else None,
                ))
                continue

            executor_tasks.append(ConnectorTask(
                connector=route.connector,
                query=query_for_search,
                language=d.language or "en",
                lineage_id=li.id,
                run_id=run_id,
                engines=cfg.searxng_engines if route.connector == "searxng" else (),
            ))

        # Synthetic required-connector dorks
        synthetic_added = 0
        required_active = []
        if cfg.required_connectors and enabled_set:
            for req_name in cfg.required_connectors:
                if req_name not in enabled_set:
                    continue
                required_active.append(req_name)
                has_real = any(
                    not getattr(t, "synthetic", False) and t.connector == req_name
                    for t in executor_tasks
                )
                if has_real:
                    continue
                _cs = _get_connector(req_name)
                if _cs is None:
                    continue
                synthetic_added += 1

                li_s = QueryLineage(
                    id=f"l_required_{req_name}", original_query=query,
                    expanded_query=f"required connector: {req_name}", language="en",
                    connector=req_name, dork_raw=query, dork_target=req_name,
                )
                lineages.append(li_s)

                if cfg.dry_run:
                    conn_results.append(ConnectorExecutionResult(
                        connector=req_name, query=query, sources_found=0,
                    ))
                    continue
                if cfg.fixture_mode:
                    fx = await self._load_fixture(cfg, req_name, query)
                    if fx is None:
                        artifact.add_error(f"required {req_name}: no fixture found")
                        continue
                    for src in fx.sources[:cfg.max_results_per_connector]:
                        src.metadata.run_id = run_id
                        src.metadata.query_lineage_id = li_s.id
                        src.metadata.discovered_by_query = query
                    all_sources.extend(fx.sources[:cfg.max_results_per_connector])
                    conn_results.append(ConnectorExecutionResult(
                        connector=req_name, query=query,
                        sources_found=min(len(fx.sources), cfg.max_results_per_connector),
                    ))
                    continue

                executor_tasks.append(ConnectorTask(
                    connector=req_name, query=query, language="en",
                    lineage_id=li_s.id, run_id=run_id, synthetic=True,
                    engines=cfg.searxng_engines if req_name == "searxng" else (),
                ))

        # Execute all live connector tasks in parallel
        if executor_tasks:
            exec_config = ConnectorExecutionConfig(
                max_concurrency=cfg.max_concurrency,
                max_concurrency_per_connector=cfg.max_concurrency_per_connector,
                timeout_seconds=cfg.connector_timeout_seconds,
            )
            executor = AsyncConnectorExecutor(exec_config)
            task_results = await executor.execute_batch(executor_tasks, _CONNECTOR_INSTANCES or {})

            for tr in task_results:
                capped = tr.sources[:cfg.max_results_per_connector]
                all_sources.extend(capped)
                conn_results.append(ConnectorExecutionResult(
                    connector=tr.connector,
                    query=tr.query,
                    sources_found=len(capped),
                    error=tr.error,
                ))
                if tr.error:
                    artifact.add_error(f"{tr.connector}: {tr.error}")

        # Coverage tracking
        covered = list({cr.connector for cr in conn_results})
        missing = [r for r in required_active if r not in covered]
        coverage = {
            "required_connectors": required_active,
            "covered_connectors": covered,
            "missing_connectors": missing,
            "synthetic_dorks_added": synthetic_added,
        }

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

        # Step 6: Crawl enrichment (skipped in dry_run / fixture_mode)
        t0 = time.time()
        if cfg.dry_run or cfg.fixture_mode:
            pass  # skip crawl in dry-run
        elif cfg.enrich:
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

        # Step 7: Extract evidence (skipped in dry_run / fixture_mode)
        t0 = time.time()
        if cfg.dry_run or cfg.fixture_mode:
            evidence = EvidenceCollection(query=query)
        else:
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
        if not cfg.dry_run and cfg.min_evidence_confidence > 0:
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
        artifact.dry_run = cfg.dry_run
        artifact.coverage = coverage
        # Build discovery_strategy from context
        strategy = build_discovery_strategy(
            profile_name=getattr(cfg, "_profile_name", None),
            searxng_strategy=cfg.searxng_strategy,
            searxng_engines=cfg.searxng_engines,
            connectors_used=[cr.connector for cr in conn_results],
        )
        artifact.discovery_strategy = strategy
        artifact.quality_controls = {
            "dry_run": cfg.dry_run,
            "fixture_mode": cfg.fixture_mode,
            "max_dorks": cfg.max_dorks,
            "max_results": cfg.max_results,
            "max_tasks_per_connector": cfg.max_tasks_per_connector,
            "max_results_per_connector": cfg.max_results_per_connector,
            "enabled_connectors": sorted(enabled_set),
            "enabled_languages": cfg.enabled_languages,
            "min_evidence_confidence": cfg.min_evidence_confidence,
            "dedup_mode": cfg.dedup_mode,
            "crawl_enrichment_policy": cfg.crawl_enrichment_policy,
            "archive_preference": cfg.archive_preference,
            "source_score_threshold": cfg.source_score_threshold,
            "required_connectors": cfg.required_connectors,
            "max_concurrency": cfg.max_concurrency,
            "max_concurrency_per_connector": cfg.max_concurrency_per_connector,
            "connector_timeout_seconds": cfg.connector_timeout_seconds,
            "searxng_strategy": cfg.searxng_strategy,
            "searxng_engines": list(cfg.searxng_engines),
        }

        artifact.errors = [sanitize_error_message(e) for e in artifact.errors]

        run_model.status = artifact.status
        run_model.total_sources = artifact.sources_fetched

        return artifact

    async def _load_expansions_fixture(self, cfg: ResearchRunConfig, query: str) -> list:
        import json
        from pathlib import Path
        from ..models.query import ExpandedQuery

        fixture_dir = Path(cfg.fixture_dir or "tests/fixtures/connectors")
        path = fixture_dir / "expansions.json"
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                return [ExpandedQuery(**e) for e in data.get("expansions", [])]
            except Exception:
                pass
        # Fallback: provide a single default expansion
        return [ExpandedQuery(original=query, variants=[query], language="en", rationale="fixture fallback")]

    async def _load_dorks_fixture(self, cfg: ResearchRunConfig, query: str, expanded=None):
        import json
        from pathlib import Path
        from ..dork_generation.generator import DorkGenerator
        from ..models.dork import DorkSchema, DorkQuery, DorkTarget

        fixture_dir = Path(cfg.fixture_dir or "tests/fixtures/connectors")
        path = fixture_dir / "dorks.json"
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                return DorkSchema(**data)
            except Exception:
                pass
        # Fallback: generate a single minimal dork based on the query
        return DorkSchema(
            description=f"Fixture dork for: {query}",
            dork_queries=[
                DorkQuery(raw=query, target=DorkTarget.SEARXNG, description="fixture fallback"),
                DorkQuery(raw=query, target=DorkTarget.GDELT, description="fixture fallback"),
                DorkQuery(raw=query, target=DorkTarget.OPENALEX, description="fixture fallback"),
            ],
        )

    async def _load_fixture(self, cfg: ResearchRunConfig, connector: str, query: str) -> object | None:
        import json
        from pathlib import Path
        from ..connectors.base import ConnectorResult

        fixture_dir = Path(cfg.fixture_dir or "tests/fixtures/connectors")
        # Map query to a fixture filename: searxng + query → searxng_hydrogen.json
        safe_query = query.replace(" ", "_")[:30]
        name = f"{connector}_{safe_query}.json"
        fixture_path = fixture_dir / name
        if not fixture_path.exists():
            # Try a generic fallback: connector.json
            fixture_path = fixture_dir / f"{connector}.json"
            if not fixture_path.exists():
                return None
        try:
            data = json.loads(fixture_path.read_text(encoding="utf-8"))
            sources = []
            for s in data.get("sources", []):
                meta = s.get("metadata", {})
                from ..models.source import SourceMetadata, SourceResult, SourceType, FetchStatus
                sm = SourceMetadata(
                    url=meta.get("url", ""),
                    source_type=SourceType(meta["source_type"]) if "source_type" in meta else SourceType.SEARXNG,
                    language=meta.get("language", "en"),
                    discovered_by_query=meta.get("discovered_by_query", query),
                    title=meta.get("title"),
                    domain=meta.get("domain"),
                )
                sources.append(SourceResult(metadata=sm, content=s.get("content")))
            return ConnectorResult(sources=sources)
        except Exception:
            return None

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

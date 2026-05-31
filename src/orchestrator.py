from __future__ import annotations
import asyncio
import json
import time
from typing import Any, Dict, List, Optional

from .config import Config
from .models.intent import UserIntent
from .models.query import QueryBatch, ExpandedQuery, MultilingualQuery, DorkQuery
from .models.source import SourceResult, SourceType, FetchStatus
from .models.evidence import EvidenceCollection, EvidenceClaim, ConflictMarker
from .models.graph import KnowledgeGraph
from .providers import init_providers
from .sources import SearXNGSearcher, GDELTClient, CommonCrawlClient, InternetArchiveClient

from .pipeline.intent_parser import IntentParser
from .pipeline.query_expansion import QueryExpansionAgent
from .pipeline.multilingual_generator import MultilingualQueryGenerator
from .pipeline.dork_generator import DorkGenerator
from .pipeline.source_router import SourceRouter
from .pipeline.fetch_layer import FetchLayer
from .pipeline.archive_lookup import ArchiveLookup
from .pipeline.evidence_extractor import EvidenceExtractor
from .pipeline.graphrag_builder import GraphRAGBuilder
from .pipeline.ranking import EvidenceRanking


class PipelineResult:
    def __init__(self) -> None:
        self.query: str = ""
        self.intent: Optional[UserIntent] = None
        self.query_batch: Optional[QueryBatch] = None
        self.source_plan: Dict[SourceType, List[str]] = {}
        self.fetched_sources: Dict[SourceType, List[SourceResult]] = {}
        self.evidence: Optional[EvidenceCollection] = None
        self.graph: Optional[KnowledgeGraph] = None
        self.timing: Dict[str, float] = {}
        self.errors: List[str] = []
        self.warnings: List[str] = []


class Pipeline:
    def __init__(self, config_path: Optional[str] = None) -> None:
        self.config = Config(config_path)
        self._init_components()

    def _init_components(self) -> None:
        init_providers()

        source_cfg = self.config.sources

        searxng_cfg = source_cfg.get("searxng", {})
        searxng = SearXNGSearcher(
            instances=searxng_cfg.get("instances", ["http://localhost:8888"]),
            max_results=searxng_cfg.get("max_results", 20),
        )

        gdelt_cfg = source_cfg.get("gdelt", {})
        gdelt = GDELTClient(
            max_records=gdelt_cfg.get("max_records", 250),
        )

        cc_cfg = source_cfg.get("common_crawl", {})
        common_crawl = CommonCrawlClient(
            max_pages=cc_cfg.get("max_pages", 50),
        )

        ia_cfg = source_cfg.get("internet_archive", {})
        internet_archive = InternetArchiveClient(
            max_snapshots=ia_cfg.get("max_snapshots", 20),
        )

        pipeline_cfg = self.config.pipeline
        multilingual_cfg = self.config.multilingual

        self.intent_parser = IntentParser()
        self.query_expansion = QueryExpansionAgent(
            max_queries=pipeline_cfg.get("max_queries_per_intent", 25),
        )
        self.multilingual_gen = MultilingualQueryGenerator(
            target_languages=multilingual_cfg.get("target_languages"),
        )
        self.dork_gen = DorkGenerator()

        self.source_router = SourceRouter()
        self.fetch_layer = FetchLayer(
            searxng=searxng,
            gdelt=gdelt,
            common_crawl=common_crawl,
            internet_archive=internet_archive,
            max_concurrent=pipeline_cfg.get("max_concurrent_fetches", 10),
        )
        self.archive_lookup = ArchiveLookup(
            internet_archive=internet_archive,
            common_crawl=common_crawl,
        )
        self.evidence_extractor = EvidenceExtractor()
        self.graphrag_builder = GraphRAGBuilder()
        self.ranking = EvidenceRanking(
            max_citations=self.config.output.get("max_citations_per_claim", 5),
        )

    async def run(self, query: str) -> PipelineResult:
        result = PipelineResult()
        result.query = query

        try:
            step = "intent_parse"
            t0 = time.time()
            intent = await self.intent_parser.parse(query)
            result.intent = intent
            result.timing["intent_parse"] = time.time() - t0

            step = "query_expansion"
            t0 = time.time()
            expanded = await self.query_expansion.expand(intent)
            result.timing["query_expansion"] = time.time() - t0

            step = "multilingual_gen"
            t0 = time.time()
            all_queries = []
            for eq in expanded:
                all_queries.extend(eq.queries)

            if intent.requires_multilingual:
                multilingual = []
                for q in all_queries[:3]:
                    batch = await self.multilingual_gen.generate(q, intent.preferred_languages)
                    multilingual.extend(batch)
            else:
                multilingual = []

            result.timing["multilingual_gen"] = time.time() - t0

            step = "dork_gen"
            t0 = time.time()
            dorks = await self.dork_gen.generate(intent, expanded)
            result.timing["dork_gen"] = time.time() - t0

            query_batch = QueryBatch(
                intent_id=id(intent),
                expanded_queries=expanded,
                multilingual_queries=multilingual,
                dork_queries=dorks,
            )
            result.query_batch = query_batch

            step = "source_routing"
            t0 = time.time()
            source_plan = self.source_router.route(intent, query_batch)
            result.source_plan = source_plan
            result.timing["source_routing"] = time.time() - t0

            step = "fetch"
            t0 = time.time()
            fetched = await self.fetch_layer.fetch_all(source_plan, multilingual)
            result.fetched_sources = fetched
            result.timing["fetch"] = time.time() - t0

            step = "archive_lookup"
            t0 = time.time()
            all_sources = []
            for sources in fetched.values():
                all_sources.extend(sources)
            # Mark NOT_FOUND sources for archive lookup
            not_found_urls = set(
                s.source_metadata.url for s in all_sources
                if s.source_metadata.fetch_status == FetchStatus.NOT_FOUND
            )
            if not_found_urls:
                archives = await self.archive_lookup.lookup_urls(not_found_urls)
                for s in all_sources:
                    if s.source_metadata.url in archives and archives[s.source_metadata.url]:
                        s.is_archive_only = True
                        s.archive_url = archives[s.source_metadata.url][0].archive_url
            result.timing["archive_lookup"] = time.time() - t0

            step = "evidence_extraction"
            t0 = time.time()
            evidence = await self.evidence_extractor.extract_all(fetched)
            result.evidence = evidence
            result.timing["evidence_extraction"] = time.time() - t0

            step = "graphrag"
            t0 = time.time()
            graph = await self.graphrag_builder.build(evidence)
            result.graph = graph
            result.timing["graphrag"] = time.time() - t0

            step = "ranking"
            t0 = time.time()
            result.evidence = self.ranking.rank(evidence, graph)
            result.timing["ranking"] = time.time() - t0

        except Exception as e:
            result.errors.append(f"Error in step '{step}': {str(e)}")

        total_time = sum(result.timing.values())
        result.timing["total"] = total_time

        return result

    def result_to_dict(self, result: PipelineResult) -> Dict[str, Any]:
        output: Dict[str, Any] = {
            "query": result.query,
            "timing": result.timing,
            "errors": result.errors if result.errors else None,
            "warnings": result.warnings if result.warnings else None,
        }

        if result.intent:
            intent = result.intent
            output["intent"] = {
                "question_type": intent.question_type.value,
                "primary_entities": intent.primary_entities,
                "secondary_entities": intent.secondary_entities,
                "locations": intent.locations,
                "timeframe": {
                    "start": intent.timeframe_start,
                    "end": intent.timeframe_end,
                },
                "requires_multilingual": intent.requires_multilingual,
                "requires_archival": intent.requires_archival,
                "sub_questions": intent.sub_questions,
            }

        if result.query_batch:
            qb = result.query_batch
            output["queries"] = {
                "expanded": [
                    {"queries": eq.queries, "rationale": eq.expansion_rationale}
                    for eq in qb.expanded_queries
                ],
                "multilingual": [
                    {"query": mq.translated_query, "language": mq.language}
                    for mq in qb.multilingual_queries
                ],
                "dorks": [
                    {"query": d.raw_query, "target": d.target_source, "description": d.description}
                    for d in qb.dork_queries
                ],
            }

        if result.evidence:
            evidence = result.evidence
            output["evidence"] = {
                "total_sources": len(evidence.evidence_list),
                "conflicting_claims": len(evidence.conflicting_claims),
                "archive_only": evidence.archive_only_sources,
                "disappeared": evidence.disappeared_sources,
                "ranked_claims": [],
            }

            evidence.evidence_list.sort(key=lambda e: e.confidence_score, reverse=True)
            for ev in evidence.evidence_list[:20]:
                for claim in ev.extracted_claims:
                    citations = self.ranking.get_citations(claim, evidence)
                    output["evidence"]["ranked_claims"].append({
                        "claim": claim.claim_text,
                        "confidence": claim.confidence,
                        "conflict_status": claim.conflict_status.value,
                        "category": claim.category,
                        "language": ev.language,
                        "citations": citations,
                    })

        if result.graph:
            graph = result.graph
            output["graph"] = {
                "entities": [
                    {"name": e.name, "type": e.type, "aliases": e.aliases}
                    for e in graph.entities.values()
                ],
                "relations": [
                    {
                        "source": graph.entities.get(r.source_entity_id, GraphEntity(id="", name="")).name,
                        "target": graph.entities.get(r.target_entity_id, GraphEntity(id="", name="")).name,
                        "type": r.relation_type,
                        "temporal": r.temporal_context,
                    }
                    for r in graph.relations
                ],
                "metadata": graph.metadata,
            }

        return output

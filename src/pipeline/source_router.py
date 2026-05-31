from __future__ import annotations
from typing import Dict, List, Set
from ..models.intent import UserIntent
from ..models.query import QueryBatch
from ..models.source import SourceType


SOURCE_TYPES = {
    "searxng": SourceType.SEARXNG,
    "gdelt": SourceType.GDELT,
    "common_crawl": SourceType.COMMON_CRAWL,
    "internet_archive": SourceType.INTERNET_ARCHIVE,
    "wayback": SourceType.WAYBACK,
    "waymore": SourceType.WAYMORE,
    "crawl4ai": SourceType.CRAWL4AI,
}


class SourceRouter:
    def route(self, intent: UserIntent, query_batch: QueryBatch) -> Dict[SourceType, List[str]]:
        plan: Dict[SourceType, List[str]] = {}

        explicit_targets = intent.target_sources
        all_queries = []
        for eq in query_batch.expanded_queries:
            all_queries.extend(eq.queries)
        for mq in query_batch.multilingual_queries:
            all_queries.append(mq.translated_query)

        if explicit_targets:
            for target in explicit_targets:
                st = SOURCE_TYPES.get(target)
                if st:
                    plan[st] = all_queries[:10]

        if not plan:
            plan[SourceType.SEARXNG] = all_queries[:10]

        if intent.requires_multilingual or intent.locations:
            langs = intent.preferred_languages - {"en"}
            if langs and SourceType.SEARXNG not in plan:
                plan[SourceType.SEARXNG] = plan.get(SourceType.SEARXNG, []) + all_queries[:5]

        if intent.requires_archival or intent.question_type.value in ("temporal", "investigative", "verification"):
            plan[SourceType.INTERNET_ARCHIVE] = all_queries[:5]
            plan[SourceType.COMMON_CRAWL] = all_queries[:3]

        if "gdelt" in intent.target_sources or intent.question_type.value in ("temporal", "investigative"):
            news_queries = []
            for eq in query_batch.expanded_queries:
                news_queries.extend(eq.queries[:3])
            plan[SourceType.GDELT] = news_queries

        return plan

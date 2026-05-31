from __future__ import annotations
import json
from typing import List
from ..models.intent import UserIntent
from ..models.query import ExpandedQuery, DorkQuery
from ..providers import LLMProvider, get_provider

EXPANSION_SYSTEM_PROMPT = """You are a query expansion specialist for OSINT research. Given a user intent, generate diverse search queries.

Output valid JSON with:
- queries: array of 5-15 search query strings covering different angles
- dork_queries: array of objects with {raw_query, operators: {operator: [values]}, target_source, description, language}
- expansion_rationale: brief explanation of expansion strategy

Strategies:
1. Synonym/paraphrase expansion
2. Entity-specific queries (names, orgs, locations)
3. Temporal framing (if timeframe exists)
4. Source-specific queries (report, document, dataset, leak)
5. Relationship queries (connections between entities)
6. Negative/investigative angle queries
7. Technical/document queries (PDF, XLS, CSV)

For dork queries, valid operators: site, intitle, inurl, intext, filetype, inanchor, before, after, source"""


class QueryExpansionAgent:
    def __init__(self, provider_name: str = "deepseek", max_queries: int = 25) -> None:
        self.provider: LLMProvider = get_provider(provider_name)
        self.max_queries = max_queries

    async def expand(self, intent: UserIntent) -> List[ExpandedQuery]:
        context_parts = []
        if intent.primary_entities:
            context_parts.append(f"Primary entities: {', '.join(intent.primary_entities)}")
        if intent.secondary_entities:
            context_parts.append(f"Secondary entities: {', '.join(intent.secondary_entities)}")
        if intent.locations:
            context_parts.append(f"Locations: {', '.join(intent.locations)}")
        if intent.timeframe_start or intent.timeframe_end:
            context_parts.append(f"Timeframe: {intent.timeframe_start or '...'} to {intent.timeframe_end or '...'}")
        if intent.sub_questions:
            context_parts.append(f"Sub-questions: {' | '.join(intent.sub_questions)}")

        context = "\n".join(context_parts)

        messages = [
            {"role": "system", "content": EXPANSION_SYSTEM_PROMPT},
            {"role": "user", "content": (
                f"Original query: {intent.original_query}\n\n"
                f"Question type: {intent.question_type.value}\n\n"
                f"Context:\n{context}\n\n"
                f"Generate up to {self.max_queries} expanded queries and relevant dork queries."
            )},
        ]

        raw = await self.provider.chat(
            messages,
            response_format={"type": "json_object"},
            temperature=0.3,
        )

        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            data = {}

        queries = data.get("queries", [intent.original_query])
        dorks_raw = data.get("dork_queries", [])

        dork_queries = []
        for d in dorks_raw:
            dork_queries.append(DorkQuery(
                raw_query=d.get("raw_query", ""),
                operators=d.get("operators", {}),
                target_source=d.get("target_source", "google"),
                description=d.get("description", ""),
                language=d.get("language", "en"),
            ))

        return [
            ExpandedQuery(
                original_intent=intent.original_query,
                queries=queries[:self.max_queries],
                dork_queries=dork_queries,
                expansion_rationale=data.get("expansion_rationale", ""),
            )
        ]

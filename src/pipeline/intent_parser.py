from __future__ import annotations
import json
from typing import List, Optional
from ..models.intent import UserIntent, QuestionType, IntentConfidence
from ..providers import LLMProvider, get_provider

INTENT_SYSTEM_PROMPT = """You are an intent parser for an OSINT research pipeline. Analyze the user's query and extract structured intent.

Output valid JSON with these fields:
- question_type: one of ["factual", "investigative", "temporal", "comparative", "verification", "relationship"]
- primary_entities: list of main entities (people, orgs, subjects)
- secondary_entities: list of secondary/contextual entities
- locations: geographic locations mentioned
- timeframe_start: YYYY-MM-DD or null if not specified
- timeframe_end: YYYY-MM-DD or null if not specified
- preferred_languages: list of ISO language codes (default ["en"])
- target_sources: suggested source types ["searxng", "gdelt", "common_crawl", "internet_archive"]
- dork_friendly: boolean - whether this benefits from search dorks
- requires_archival: boolean - whether archival sources may be needed
- requires_multilingual: boolean - whether non-English sources are likely relevant
- sub_questions: list of sub-questions to answer
- confidence: dict with type_confidence, entity_confidence, temporal_confidence (0-1 each)

Be precise. If uncertain, set confidence low rather than guessing."""


class IntentParser:
    def __init__(self, provider_name: str = "deepseek") -> None:
        self.provider: LLMProvider = get_provider(provider_name)

    async def parse(self, query: str) -> UserIntent:
        messages = [
            {"role": "system", "content": INTENT_SYSTEM_PROMPT},
            {"role": "user", "content": f"Parse this research query:\n\n{query}"},
        ]

        raw = await self.provider.chat(
            messages,
            response_format={"type": "json_object"},
            temperature=0.1,
        )

        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            data = {}

        confidence_data = data.get("confidence", {})
        confidence = IntentConfidence(
            type_confidence=confidence_data.get("type_confidence", 0.3),
            entity_confidence=confidence_data.get("entity_confidence", 0.3),
            temporal_confidence=confidence_data.get("temporal_confidence", 0.3),
        )
        confidence.overall = (
            confidence.type_confidence
            + confidence.entity_confidence
            + confidence.temporal_confidence
        ) / 3.0

        return UserIntent(
            original_query=query,
            question_type=QuestionType(data.get("question_type", "unknown")),
            primary_entities=data.get("primary_entities", []),
            secondary_entities=data.get("secondary_entities", []),
            locations=data.get("locations", []),
            timeframe_start=data.get("timeframe_start"),
            timeframe_end=data.get("timeframe_end"),
            preferred_languages=set(data.get("preferred_languages", ["en"])),
            target_sources=data.get("target_sources", []),
            dork_friendly=data.get("dork_friendly", False),
            requires_archival=data.get("requires_archival", False),
            requires_multilingual=data.get("requires_multilingual", False),
            sub_questions=data.get("sub_questions", []),
            confidence=confidence,
            raw_llm_output=raw,
        )

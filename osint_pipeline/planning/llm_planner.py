from __future__ import annotations

import json

from ..config import get_settings
from ..utils.validation import parse_llm_json, validate_llm_output
from .models import (
    ResearchPlan, ResearchIntent, ConnectorPlan,
    ALLOWED_CONNECTORS, ALLOWED_PROFILES, ALLOWED_ARCHIVE_PREFERENCES, FORBIDDEN_PHRASES,
)

LLM_PROMPT = """You are a research planning assistant for an OSINT pipeline.

Given a user query, refine the base research plan. Output valid JSON matching this schema:
{
  "intent": "one of: general_research, deleted_content, archive_lookup, entity_investigation, news_monitoring, academic_research, code_search, social_discussion, document_search, cross_language_search, verification",
  "confidence": 0.0-1.0,
  "profile": "one of: smoke, archive_first, deleted_content, multi_engine, foreign_index, deep_archive",
  "languages": ["nl", "en"],
  "archive_preference": "live_first | archive_first | archive_only",
  "searxng_strategy": "default | file_discovery | multi_engine | regional_diverse",
  "required_connectors": ["connector1"],
  "connectors": [
    {"connector": "searxng", "reason": "why", "required": false}
  ],
  "query_strategies": ["web", "news"],
  "planner_warnings": []
}

Allowed connectors: searxng, gdelt, openalex, archive_cdx, commoncrawl, archive_today, github, wikidata, reddit
Allowed profiles: smoke, archive_first, deleted_content, multi_engine, foreign_index, deep_archive
Allowed archive preferences: live_first, archive_first, archive_only

Do NOT use these phrases anywhere: zero-attribution, 100% anonymous, no DNS leaks guaranteed, uncensored
Do NOT invent connectors not in the allowed list.
Output ONLY valid JSON."""  # noqa: E501


async def refine_plan_with_llm(query: str, base_plan: ResearchPlan) -> ResearchPlan:
    settings = get_settings()
    if not settings.deepseek_api_key:
        base_plan.planner_warnings.append("LLM planner skipped: no DeepSeek API key")
        return base_plan

    from openai import AsyncOpenAI
    client = AsyncOpenAI(
        api_key=settings.deepseek_api_key,
        base_url=settings.deepseek_base_url,
    )

    base_data = base_plan.model_dump()
    messages = [
        {"role": "system", "content": LLM_PROMPT},
        {"role": "user", "content": f"Query: {query}\n\nBase plan:\n{json.dumps(base_data, indent=2)}"},
    ]

    try:
        resp = await client.chat.completions.create(
            model=settings.deepseek_model,
            messages=messages,
            response_format={"type": "json_object"},
            temperature=0.2,
        )
        raw = resp.choices[0].message.content or "{}"
    except Exception as exc:
        base_plan.planner_warnings.append(f"LLM planner error: {exc}")
        return base_plan

    parse_result = parse_llm_json(raw)
    if not parse_result.success:
        base_plan.planner_warnings.append(f"LLM planner: invalid JSON, using rule-based plan")
        return base_plan

    data = parse_result.data

    # Validate against allowed values
    intent_raw = data.get("intent", "")
    try:
        intent = ResearchIntent(intent_raw)
    except ValueError:
        base_plan.planner_warnings.append(f"LLM planner: unknown intent '{intent_raw}', using rule-based")
        return base_plan

    profile = data.get("profile", base_plan.profile)
    if profile not in ALLOWED_PROFILES:
        base_plan.planner_warnings.append(f"LLM planner: invalid profile '{profile}', using rule-based")
        return base_plan

    archive_pref = data.get("archive_preference", base_plan.archive_preference)
    if archive_pref not in ALLOWED_ARCHIVE_PREFERENCES:
        base_plan.planner_warnings.append(f"LLM planner: invalid archive pref '{archive_pref}', using rule-based")
        return base_plan

    # Check forbidden phrases in LLM output
    raw_lower = raw.lower()
    for phrase in FORBIDDEN_PHRASES:
        if phrase in raw_lower:
            base_plan.planner_warnings.append(f"LLM planner: forbidden phrase '{phrase}' in output, using rule-based")
            return base_plan

    # Build connector plans
    connectors_raw = data.get("connectors", [])
    connectors = []
    for c in connectors_raw:
        conn_name = c.get("connector", "")
        if conn_name not in ALLOWED_CONNECTORS:
            base_plan.planner_warnings.append(f"LLM planner: unknown connector '{conn_name}', skipping")
            continue
        connectors.append(ConnectorPlan(
            connector=conn_name,
            reason=c.get("reason", ""),
            required=c.get("required", False),
        ))

    if not connectors:
        connectors = base_plan.connectors

    new_plan = ResearchPlan(
        intent=intent,
        confidence=data.get("confidence", base_plan.confidence),
        profile=profile,
        query_seed=base_plan.query_seed,
        languages=list(set(data.get("languages", base_plan.languages))),
        archive_preference=archive_pref,
        searxng_strategy=data.get("searxng_strategy", base_plan.searxng_strategy),
        connectors=connectors,
        required_connectors=list(set(data.get("required_connectors", base_plan.required_connectors))),
        query_strategies=data.get("query_strategies", base_plan.query_strategies),
        planner_warnings=base_plan.planner_warnings,
    )

    val = validate_llm_output(ResearchPlan, new_plan.model_dump())
    if not val.success:
        base_plan.planner_warnings.append(f"LLM planner: Pydantic validation failed, using rule-based")
        return base_plan

    return new_plan

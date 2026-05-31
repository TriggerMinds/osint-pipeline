from __future__ import annotations

from ..research.runner import ResearchRunConfig
from .models import ResearchPlan, ALLOWED_CONNECTORS
from .extract import extract_query_seed

PROFILE_SEARXNG_MAP = {
    "smoke": ("default", ()),
    "archive_first": ("file_discovery", ("brave", "mojeek", "bing")),
    "deleted_content": ("file_discovery", ("brave", "mojeek", "bing", "yandex")),
    "multi_engine": ("multi_engine", ("brave", "mojeek", "yandex", "bing", "duckduckgo")),
    "foreign_index": ("regional_diverse", ("yandex", "baidu", "mojeek", "brave", "bing")),
    "deep_archive": ("file_discovery", ("brave", "mojeek", "bing")),
}

PROFILE_DEFAULTS: dict[str, dict] = {
    "smoke": {"max_dorks": 3, "max_results": 10, "max_tasks": 2, "max_per": 10, "enrich": False, "dedup": "canonical_url", "min_conf": 0.3},
    "archive_first": {"max_dorks": 5, "max_results": 30, "max_tasks": 3, "max_per": 15, "enrich": False, "dedup": "url", "min_conf": 0.0},
    "deleted_content": {"max_dorks": 8, "max_results": 50, "max_tasks": 3, "max_per": 20, "enrich": True, "dedup": "canonical_url", "min_conf": 0.0},
    "multi_engine": {"max_dorks": 12, "max_results": 80, "max_tasks": 4, "max_per": 20, "enrich": False, "dedup": "canonical_url", "min_conf": 0.0},
    "foreign_index": {"max_dorks": 10, "max_results": 60, "max_tasks": 3, "max_per": 15, "enrich": False, "dedup": "canonical_url", "min_conf": 0.0},
    "deep_archive": {"max_dorks": 10, "max_results": 80, "max_tasks": 4, "max_per": 25, "enrich": True, "dedup": "canonical_url", "min_conf": 0.0},
}


def apply_plan_to_config(plan: ResearchPlan, base_config: ResearchRunConfig | None = None) -> ResearchRunConfig:
    cfg = base_config or ResearchRunConfig()
    defaults = PROFILE_DEFAULTS.get(plan.profile, {})

    cfg._profile_name = plan.profile
    cfg.enabled_connectors = [c.connector for c in plan.connectors if c.connector in ALLOWED_CONNECTORS]
    cfg.required_connectors = [c for c in plan.required_connectors if c in ALLOWED_CONNECTORS]
    cfg.enabled_languages = list(set(plan.languages)) or ["nl", "en"]
    cfg.archive_preference = plan.archive_preference
    cfg.searxng_strategy = plan.searxng_strategy
    se_engines = PROFILE_SEARXNG_MAP.get(plan.profile, ("default", ()))[1]
    cfg.searxng_engines = tuple(se_engines)

    cfg.max_dorks = defaults.get("max_dorks", cfg.max_dorks)
    cfg.max_results = defaults.get("max_results", cfg.max_results)
    cfg.max_tasks_per_connector = defaults.get("max_tasks", cfg.max_tasks_per_connector)
    cfg.max_results_per_connector = defaults.get("max_per", cfg.max_results_per_connector)
    cfg.enrich = defaults.get("enrich", cfg.enrich)
    cfg.dedup_mode = defaults.get("dedup", cfg.dedup_mode)
    cfg.min_evidence_confidence = defaults.get("min_conf", cfg.min_evidence_confidence)

    # Apply per-connector overrides
    for cp in plan.connectors:
        if cp.connector not in ALLOWED_CONNECTORS:
            continue

    # Remove disabled connectors from enabled list
    if cfg.disabled_connectors:
        cfg.enabled_connectors = [c for c in (cfg.enabled_connectors or [])
                                  if c not in cfg.disabled_connectors]
        cfg.required_connectors = [c for c in cfg.required_connectors
                                   if c not in cfg.disabled_connectors]

    return cfg


def evaluate_plan_coverage(plan: ResearchPlan, artifact_data: dict) -> list[str]:
    warnings: list[str] = []

    conn_results = artifact_data.get("connector_results", [])
    used_connectors = {cr.get("connector") for cr in conn_results} if conn_results else set()
    sources_fetched = artifact_data.get("sources_fetched", 0)
    evidence = artifact_data.get("evidence", {})
    claims = len(evidence.get("items", [])) if evidence else 0

    # Required connectors
    for req in plan.required_connectors:
        if req not in used_connectors:
            warnings.append(f"Required connector '{req}' was not used")

    # Intent-specific
    if plan.intent.value == "deleted_content" and sources_fetched > 0:
        has_archive = any(
            cr.get("connector") in ("archive_cdx", "archive_today", "commoncrawl")
            for cr in conn_results
        ) if conn_results else False
        if not has_archive:
            warnings.append("Deleted content intent but no archive connector returned results")

    if plan.intent.value == "academic_research" and "openalex" not in used_connectors:
        warnings.append("Academic intent but OpenAlex was not used")

    if plan.intent.value == "news_monitoring" and "gdelt" not in used_connectors:
        warnings.append("News intent but GDELT was not used")

    if plan.intent.value == "document_search":
        if "filename" not in plan.query_strategies and "filetype" not in plan.query_strategies:
            warnings.append("Document search but no filename/filetype query strategy")

    if sources_fetched == 0:
        warnings.append("No sources were fetched")

    return warnings

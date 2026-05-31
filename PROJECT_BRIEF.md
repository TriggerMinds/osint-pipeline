# Project Brief: OSINT Research Pipeline

## Goal

Build an AI-driven OSINT/research pipeline for public sources, archives, multilingual discovery, evidence ranking, and knowledge graph construction.

## Core Stack

- Python 3.11+ with Pydantic, Typer CLI, httpx, rich
- DeepSeek API for reasoning, generation, classification, and translation
- 8 connectors: SearXNG, GDELT, Internet Archive CDX, Common Crawl, OpenAlex, GitHub, Wikidata, Reddit
- Optional: Crawl4AI, Playwright, CloakBrowser, Hysteria2 proxy

## Key Principles

1. **Builder-first** — working interfaces over loose ideas
2. **Reproducible output** — every result is traceable to its source via lineage
3. **Metadata-rich** — url, source_type, language, discovered_by_query, discovered_at, snapshot_date, confidence_score, run_id, query_lineage_id
4. **Schema-constrained** — dork generation uses Pydantic-generated JSON Schema, no drift
5. **No hallucinated sources** — all claims must have verifiable backing
6. **No silent fallbacks** — invalid model output raises errors, never silently corrects
7. **No secret leaks** — proxy URLs, API keys, tokens, and bearer auth are sanitized in errors and artifacts

## Architecture

1. ResearchRunner — orchestrates the full pipeline
2. QueryExpander — multilingual expansion via DeepSeek
3. DorkGenerator — schema-validated dork query generation
4. SourceRouter — DorkTarget → connector mapping (12 targets)
5. Connectors — 8 source adapters with retry/backoff/typed params
6. Crawl4AI Adapter — optional content enrichment
7. EvidenceExtractor — claims with confidence + conflict detection
8. EvidenceRanker — confidence-based scoring and sorting
9. EvidenceGraphBuilder — GraphRAG-light (nodes + edges)
10. ResearchArtifact — Pydantic artifact with coverage, timing, quality controls

## Output Requirements

- Each claim must be source-backed
- Preserve URL, timestamp, snapshot_date, language, source_type, discovered_by_query, run_id, query_lineage_id
- Mark conflicting sources (ConflictMarker)
- Mark archive-only or disappeared content separately
- No raw secrets, API keys, or tokens in output

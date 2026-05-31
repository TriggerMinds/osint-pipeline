# Project Brief: OSINT Research Pipeline

## Goal

Build an AI-driven OSINT/research pipeline for public sources, archives, and multilingual discovery.

## Core Stack

- Python 3.11+ with Pydantic models, Typer CLI, httpx async networking
- DeepSeek API for reasoning, generation, classification, and translation
- Optional: Crawl4AI, SearXNG, GDELT, Internet Archive CDX, Common Crawl, GraphRAG

## Key Principles

1. **Builder-first** — working interfaces over loose ideas
2. **Reproducible output** — every result is traceable to its source
3. **Metadata-rich** — url, source_type, language, discovered_by_query, discovered_at, snapshot_date, confidence_score
4. **Schema-constrained** — dork generation uses strict JSON Schema validation
5. **No hallucinated sources** — all claims must have verifiable backing
6. **Adapter pattern** — all external tools via clear interfaces

## Architecture

1. Query Expansion Agent — generates diverse search variants
2. Multilingual Translator — translates queries across languages
3. Dork Generator — creates schema-validated search engine dorks
4. Connectors — SearXNG, GDELT, Internet Archive CDX, Common Crawl
5. Crawler — optional Crawl4AI integration
6. Evidence Extractor — extracts and conflicts claims from sources
7. Evidence Ranker — scores and sorts evidence by reliability
8. GraphRAG Adapter — optional knowledge graph builder

## Output Requirements

- Each claim must be source-backed
- Preserve URL, timestamp, snapshot_date, language, source_type, discovered_by_query
- Mark conflicting sources
- Mark archive-only or disappeared content separately

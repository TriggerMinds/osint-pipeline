# Architecture

## Directory Structure

```
osint_pipeline/
  __init__.py
  config/               # Pydantic Settings loaded from .env
  models/               # Pydantic models: query, source, evidence, dork, graph, lineage
  query_expansion/      # Query expansion via DeepSeek
  multilingual/         # Query translation (13 languages)
  dork_generation/      # Dork generation + Pydantic-generated JSON Schema
  connectors/           # 8 source connectors (BaseConnector interface)
  crawler/              # Crawl4AI adapter (optional dependency)
  extraction/           # Evidence extraction with conflict detection
  ranking/              # Evidence confidence ranking
  graph/                # GraphRAG adapter (optional)
  router.py             # SourceRouter: DorkQuery → connector mapping
  graphrag.py           # GraphRAG-light: EvidenceGraph builder + GraphML/CSV/JSON export
  browser/              # BrowserRuntime: PlaywrightRuntime, CloakBrowserRuntime
  runtime/              # RuntimeChecker for environment health
  export/               # Maltego export (GraphML, CSV, JSONL)
  adapters/             # External adapters: Waymore, Photon, SpiderFoot (optional stubs)
  research/             # ResearchRunner + ResearchArtifact + sanitize
    runner.py           # Full pipeline orchestration
    artifacts.py        # Pydantic artifact schema
    sanitize.py         # Secret sanitization
  cli.py                # Typer CLI with 12 commands

tests/                  # pytest tests (219+)
tests/fixtures/         # Test fixtures for offline runs
```

## Data Flow (Research Run)

```
User Query
  │
  ▼
ResearchRunner.run()
  │
  ├─ 1. QueryExpander.expand()       ───► multilingual variants
  ├─ 2. DorkGenerator.generate()     ───► schema-validated dorks
  ├─ 3. SourceRouter.route()         ───► DorkTarget → connector mapping
  ├─ 4. Connector search()           ───► raw sources (8 connectors)
  ├─ 5. Deduplicate + canonical URL  ───► cleaned source list
  ├─ 6. Crawl4AI enrich (optional)   ───► deeper content extraction
  ├─ 7. EvidenceExtractor.extract()  ───► claims with confidence + conflicts
  ├─ 8. EvidenceRanker.rank()        ───► scored evidence
  ├─ 9. EvidenceGraphBuilder.build() ───► GraphRAG-light (nodes + edges)
  └─ 10. ResearchArtifact export     ───► JSON with coverage + timing
```

## CLI Commands

| Command | Description |
|---|---|
| `osint init` | Show configuration status |
| `osint runtime-check` | Check proxy, Crawl4AI, Playwright, CloakBrowser |
| `osint browser-check` | Validate browser engine config |
| `osint expand-query "..."` | Generate multilingual search variants |
| `osint generate-dorks "..."` | Generate schema-validated dorks |
| `osint search "..." --source ...` | Search a connector (8 sources) |
| `osint archive-lookup "..."` | Internet Archive CDX + Common Crawl |
| `osint route-dork dorks.json` | Route dorks through SourceRouter |
| `osint run-research "..."` | Full pipeline: expand → dork → route → fetch → extract → rank → graph |
| `osint rank-evidence input.json` | Rank evidence from JSON |
| `osint export-graph evidence.json --format graphml` | Build + export evidence graph |
| `osint crawl-url "..."` | Crawl single URL via Crawl4AI |
| `osint validate-artifact run.json` | Schema + secrets + lineage validation |

## Connector Interface

All connectors implement `BaseConnector` with:
- `async def search(query, **kwargs) -> ConnectorResult`
- `async def health() -> bool`
- `_request_with_retry()` — exponential backoff, jitter, Retry-After header support

## SourceRouter

Maps every `DorkTarget` to a connector name, execution mode, and human-readable reason. 12 targets, each with `TARGET_CONNECTOR_MAP`, `TARGET_EXECUTION_MODE`, `TARGET_REASON`. Unknown target raises `RouterError` (no silent fallback).

## EvidenceGraph (GraphRAG-light)

No heavy GraphRAG dependency. Builds:
- Source nodes (URL → domain edges)
- Language nodes (source → language edges)
- Claim nodes (source → claim edges with confidence + conflict status)
- Connector nodes (source → connector lineage edges)

Export: JSON, GraphML, CSV-nodes, CSV-edges (all via `xml.etree.ElementTree`).

## Error Policy

- `ConnectorError` hierarchy: `ConnectorHTTPStatusError`, `ConnectorRetriesExhaustedError`, `ConnectorTimeoutError`
- `sanitize_error_message()` masks proxy credentials, API keys, tokens, bearer auth
- `ResearchArtifact.errors[]` is sanitized before export
- CLI exit code 1 on validation/execution errors

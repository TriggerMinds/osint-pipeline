# Architecture

## Directory Structure

```
osint_pipeline/
  __init__.py
  config/             # Pydantic Settings, loaded from .env
  models/             # Data models (query, source, evidence, dork)
  query_expansion/    # Query expansion via DeepSeek
  multilingual/       # Query translation
  dork_generation/    # Dork generation + JSON Schema validation
  connectors/         # External source adapters
  crawler/            # Crawl4AI adapter (optional)
  extraction/         # Evidence extraction from source content
  ranking/            # Evidence confidence ranking
  graph/              # GraphRAG adapter (optional)
  cli.py              # Typer CLI with 6 commands

tests/                # pytest tests
```

## Data Flow

```
User Query
  │
  ▼
QueryExpander ───► multilingual variants
  │
  ▼
MultilingualTranslator ───► per-language queries
  │
  ▼
DorkGenerator ───► schema-validated dorks
  │
  ▼
Connectors (SearXNG, GDELT, IA CDX, CC)
  │
  ▼
EvidenceExtractor ───► claims with confidence
  │
  ▼
EvidenceRanker ───► sorted by score
  │
  ▼
GraphRAGAdapter ───► knowledge graph (optional)
```

## CLI Commands

| Command | Description |
|---|---|
| `osint init` | Show configuration status |
| `osint expand-query "..."` | Generate multilingual search variants |
| `osint generate-dorks "..."` | Generate schema-validated dorks |
| `osint search "..."` | Search a connector source |
| `osint archive-lookup "..."` | Check Internet Archive + Common Crawl |
| `osint rank-evidence input.json` | Rank evidence from JSON |

## Connector Interface

All connectors implement `BaseConnector` with:
- `async def search(query, **kwargs) -> ConnectorResult`
- `async def health() -> bool`

## Provider Abstraction

Currently DeepSeek-only via OpenAI-compatible SDK. The `config/settings.py` holds all connection details, making it straightforward to swap providers later.

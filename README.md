# OSINT Pipeline

AI-driven OSINT/research pipeline for public sources, archives, multilingual discovery, evidence ranking, and knowledge graph construction.

## Installation

```bash
pip install -e .
cp .env.example .env
# Edit .env — add your DeepSeek API key and configure connectors
pip install "osint-pipeline[crawl]"   # optional: Crawl4AI support
pip install "osint-pipeline[browser]" # optional: Playwright support
```

## Quick Start

```bash
# Check runtime environment
osint runtime-check

# Dry-run: expand, dork, route (no connector calls)
osint run-research "waterstof opslag nederland" --profile smoke --dry-run --output runs/dryrun.json

# Fixture mode: run with pre-recorded test data (no API key needed)
osint run-research "waterstof opslag nederland" --profile smoke --fixture --output runs/fixture.json

# Validate a run artifact
osint validate-artifact runs/fixture.json

# Individual CLI commands
osint init
osint expand-query "waterstof opslag nederland"
osint generate-dorks "waterstof opslag nederland"
osint search "hydrogen storage" --source openalex
osint archive-lookup "https://example.com/doc.pdf"
osint route-dork dorks.json
osint export-graph evidence.json --format graphml
```

## Smoke Profile

```bash
# Live run with SearXNG + GDELT + OpenAlex (requires API key + network)
osint run-research "waterstof opslag nederland" --profile smoke --output runs/smoke.json

# Disable a connector if unavailable
osint run-research "waterstof opslag nederland" --profile smoke --disable-connector searxng --output runs/smoke.json
```

## Architecture

See [ARCHITECTURE.md](ARCHITECTURE.md) for the full design.

## Connectors

| Connector | Type | Auth |
|---|---|---|
| SearXNG | Web metasearch | Public instances |
| GDELT | News/events | Public API |
| Internet Archive CDX | Historical web | Public API |
| Common Crawl | Historical web | Public API |
| OpenAlex | Academic publications | Optional email |
| GitHubSearch | Code repositories | Optional token |
| Wikidata | Entity search | Public SPARQL |
| Reddit | Social media | Public JSON |

## Configuration

Settings are loaded from `.env` with the `OSINT_` prefix. See `.env.example` for all options.

## Requirements

- Python 3.11+
- DeepSeek API key (`OSINT_DEEPSEEK_API_KEY`)
- Optional: SearXNG instance, Hysteria2 proxy, Crawl4AI, Playwright, CloakBrowser

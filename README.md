# OSINT Pipeline

AI-driven OSINT/research pipeline for public sources, archives, multilingual discovery, and evidence ranking.

## Installation

```bash
pip install -e .
cp .env.example .env
# Edit .env — add your DeepSeek API key
```

## Quick Start

```bash
# Initialize configuration
osint init

# Expand a query into multilingual search variants
osint expand-query "waterstof opslag nederland"

# Generate search engine dorks
osint generate-dorks "waterstof opslag nederland"

# Search a source
osint search "hydrogen storage netherlands" --source searxng

# Look up a URL in archives
osint archive-lookup "https://example.com/report.pdf"

# Rank evidence from a JSON file
osint rank-evidence evidence.json
```

## Architecture

See [ARCHITECTURE.md](ARCHITECTURE.md) for the full design.

## Configuration

Settings are loaded from `.env` with the `OSINT_` prefix. See `.env.example` for all options.

## Requirements

- Python 3.11+
- DeepSeek API key
- Optional: SearXNG instance, Crawl4AI, GraphRAG

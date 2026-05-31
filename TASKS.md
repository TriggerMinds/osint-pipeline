# Tasks

## Completed

- [x] Project scaffolding — Pydantic models, Typer CLI, pytest, rich
- [x] Config loader — pydantic-settings from .env
- [x] Query expansion — multilingual via DeepSeek (nl/en/de/fr minimum)
- [x] Multilingual translator — 13 languages
- [x] Dork generator — Pydantic-generated JSON Schema with validation
- [x] Connectors — SearXNG, GDELT, Internet Archive CDX, Common Crawl
- [x] Connector retry — exponential backoff, jitter, Retry-After, status code config
- [x] Typed connector errors — ConnectorError hierarchy (HTTPStatus, Timeout, RetriesExhausted)
- [x] Deep-discovery connectors — OpenAlex, GitHubSearch, Wikidata, Reddit
- [x] SourceRouter — 12 DorkTargets → connector mapping, RouterError (no silent fallback)
- [x] Query lineage — ResearchRun, QueryLineage, run_id + query_lineage_id on metadata
- [x] Evidence extraction — DeepSeek-based claim extraction with conflict detection
- [x] Evidence ranking — confidence scoring, archive-only/disappeared penalties
- [x] Browser runtime — PlaywrightRuntime, CloakBrowserRuntime (optional)
- [x] Runtime checks — runtime-check, browser-check, crawl-url CLI commands
- [x] Proxy masking — mask_proxy_url, sanitize_error_message (secrets/keys/tokens/bearer)
- [x] ResearchRunner — full pipeline extraction from CLI to research/runner.py
- [x] ResearchArtifact — Pydantic artifact schema with model_dump_safe()
- [x] GraphRAG-light — EvidenceGraph builder + GraphML/CSV/JSON export (ElementTree)
- [x] Maltego export — GraphML, CSV, JSONL (no SDK dependency)
- [x] GraphML hardening — ElementTree instead of string formatting, XML-safe
- [x] External adapters — WaymoreAdapter (subprocess), PhotonAdapter (stub), SpiderFootAdapter (import)
- [x] Dry-run mode — expand + dork + route without connector calls
- [x] Fixture mode — offline testing with fixture files
- [x] Smoke profile — safe preset: 3 dorks, 10 results, 3 connectors
- [x] Required connectors — synthetic dork injection for coverage
- [x] Canonical URL dedup — strip tracking params (utm_, fbclid, gclid)
- [x] Quality controls — enabled/disabled connectors, language filter, archive preference, min confidence
- [x] Run artifact validation — validate-artifact CLI with secret detection
- [x] Documentation: README, ARCHITECTURE, PROJECT_BRIEF, .env.example
- [x] 219+ tests, all passing

## Next

- [ ] Docker Compose setup for SearXNG + pipeline
- [ ] CI/CD via GitHub Actions
- [ ] Cached responses (disk/redis)
- [ ] Multi-provider LLM abstraction
- [ ] Web UI (Streamlit)
- [ ] Integration tests with live API keys

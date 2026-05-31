from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from .config import get_settings
from .query_expansion import QueryExpander, QueryExpanderError
from .dork_generation import DorkGenerator, DorkGeneratorError, validate_dork
from .multilingual import MultilingualTranslator
from .runtime.checks import RuntimeChecker, mask_proxy_url
from .research import sanitize_error_message
from .router import RouterError, SourceRouter
from .graphrag import EvidenceGraphExporter
from .models.dork import DorkQuery, DorkSchema
from .connectors import (
    SearXNGConnector, GDELTConnector, ArchiveCDXConnector, CommonCrawlConnector,
    OpenAlexConnector, GitHubSearchConnector, WikidataConnector, RedditConnector,
    ArchiveTodayConnector,
)
from .research import ResearchRunner, ResearchRunConfig, ResearchArtifact
from .research.strategies import PROFILE_SEARXNG
from .runs_manager import RunArchiver

app = typer.Typer(name="osint", help="AI-driven OSINT research pipeline")
console = Console()


def _run_async(coro):
    return asyncio.run(coro)


@app.command()
def init(
    env_file: Optional[Path] = typer.Option(
        None, "--env-file", "-e", help="Path to .env file"
    ),
) -> None:
    """Initialize the OSINT pipeline configuration."""
    settings = get_settings()
    if env_file and env_file.exists():
        from pydantic_settings import SettingsConfigDict
        console.print(f"[green]Loaded config from {env_file}[/green]")

    checker = RuntimeChecker()
    env = checker.check_all()

    proxy_display = env.proxy_url or "[yellow]not configured[/yellow]"

    console.print(Panel.fit(
        "[bold]OSINT Pipeline[/bold]\n\n"
        f"DeepSeek API: {'[green]configured[/green]' if settings.deepseek_api_key else '[red]missing[/red]'}\n"
        f"Proxy: {proxy_display}\n"
        f"Browser engine: {settings.browser_engine}\n"
        f"SearXNG instances: {settings.searxng_instances}\n"
        f"GDELT endpoint: {settings.gdelt_base_url}\n"
        f"Archive CDX: {settings.archive_cdx_url}\n"
        f"Common Crawl: {settings.commoncrawl_base_url}",
        title="Configuration",
    ))


@app.command()
def expand_query(
    query: str = typer.Argument(..., help="Research query to expand"),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Output JSON file"),
) -> None:
    """Expand a query into multiple search variants across languages."""
    try:
        expander = QueryExpander()
        results = _run_async(expander.expand(query))
    except QueryExpanderError as e:
        console.print(f"[red]Query expansion failed: {e}[/red]")
        raise typer.Exit(1)

    table = Table(title="Expanded Queries")
    table.add_column("Language", style="cyan")
    table.add_column("Variants", style="white")
    table.add_column("Rationale", style="dim")

    for r in results:
        table.add_row(r.language, "\n".join(r.variants), r.rationale)

    console.print(table)

    if output:
        output.write_text(
            json.dumps([r.model_dump() for r in results], indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        console.print(f"[green]Written to {output}[/green]")


@app.command()
def generate_dorks(
    query: str = typer.Argument(..., help="Query to generate dorks for"),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Output JSON file"),
) -> None:
    """Generate search engine dork queries from a query."""
    try:
        generator = DorkGenerator()
        schema = _run_async(generator.generate(query))
    except DorkGeneratorError as e:
        console.print(f"[red]Dork generation failed: {e}[/red]")
        raise typer.Exit(1)

    # Validate against JSON schema
    instance = schema.model_dump()
    errors = validate_dork(instance)
    if errors:
        console.print(f"[red]Schema validation errors:[/red]")
        for e in errors:
            console.print(f"  - {e}")
        raise typer.Exit(1)

    table = Table(title=f"Dork Queries: {query}")
    table.add_column("Target", style="cyan")
    table.add_column("Dork", style="white")
    table.add_column("Description", style="dim")

    for d in schema.dork_queries:
        table.add_row(d.target.value, d.raw, d.description)

    console.print(table)

    if output:
        output.write_text(
            json.dumps(instance, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        console.print(f"[green]Written to {output}[/green]")


@app.command()
def search(
    query: str = typer.Argument(..., help="Search query"),
    source: str = typer.Option(
        "searxng", "--source", "-s", help="Source: searxng, gdelt, openalex, github, wikidata, reddit, archive_today"
    ),
    language: str = typer.Option("en", "--language", "-l", help="Language code"),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Output JSON file"),
) -> None:
    """Execute a search against a configured source connector."""
    connectors = {
        "searxng": SearXNGConnector(),
        "gdelt": GDELTConnector(),
        "openalex": OpenAlexConnector(),
        "github": GitHubSearchConnector(),
        "wikidata": WikidataConnector(),
        "reddit": RedditConnector(),
        "archive_today": ArchiveTodayConnector(),
    }

    conn = connectors.get(source)
    if not conn:
        console.print(f"[red]Unknown source: {source}. Options: {list(connectors.keys())}[/red]")
        raise typer.Exit(1)

    result = _run_async(conn.search(query, language=language))

    table = Table(title=f"Results from {source}: {query}")
    table.add_column("URL", style="cyan")
    table.add_column("Title", style="white")
    table.add_column("Language", style="dim")

    for src in result.sources[:20]:
        table.add_row(
            src.metadata.url[:80],
            (src.metadata.title or "")[:60],
            src.metadata.language,
        )

    safe_data = [s.metadata.model_dump() for s in result.sources]

    if output:
        output.write_text(json.dumps(safe_data, indent=2), encoding="utf-8")

    archiver = RunArchiver()
    run_dir = archiver.archive_run(
        query=query,
        artifact_data={"source": source, "query": query, "results": safe_data, "error": result.error},
        profile=f"search_{source}",
        timing=None,
        errors=[result.error] if result.error else None,
    )

    try:
        console.print(table)
    except UnicodeEncodeError:
        console.print(f"[green]{len(result.sources)} results from {source}[/green]")

    if result.error:
        console.print(f"[red]Error: {result.error}[/red]")

    if output:
        console.print(f"[green]Written to {output}[/green]")

    console.print(f"[dim]Archived: {run_dir}[/dim]")


@app.command()
def archive_lookup(
    url: str = typer.Argument(..., help="URL to look up in archives"),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Output JSON file"),
) -> None:
    """Look up a URL in Internet Archive and Common Crawl."""
    ia = ArchiveCDXConnector()
    cc = CommonCrawlConnector()

    ia_result = _run_async(ia.search(url))
    cc_result = _run_async(cc.search(url))

    table = Table(title=f"Archive Results: {url}")
    table.add_column("Source", style="cyan")
    table.add_column("Snapshot URL", style="white")
    table.add_column("Date", style="dim")

    for src in ia_result.sources:
        table.add_row(
            "Internet Archive",
            src.metadata.archive_url or src.metadata.url,
            src.metadata.snapshot_date or "",
        )
    for src in cc_result.sources:
        table.add_row(
            "Common Crawl",
            src.metadata.url,
            src.metadata.snapshot_date or "",
        )

    console.print(table)

    if output:
        combined = {
            "internet_archive": [s.metadata.model_dump() for s in ia_result.sources],
            "common_crawl": [s.metadata.model_dump() for s in cc_result.sources],
        }
        output.write_text(json.dumps(combined, indent=2), encoding="utf-8")
        console.print(f"[green]Written to {output}[/green]")


@app.command()
def rank_evidence(
    input_file: Path = typer.Argument(..., help="JSON file with evidence collection"),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Output JSON file"),
) -> None:
    """Rank evidence from an evidence collection JSON file."""
    from .models.evidence import EvidenceCollection

    data = json.loads(input_file.read_text(encoding="utf-8"))
    collection = EvidenceCollection(**data)

    ranker = EvidenceRanker()
    ranked = ranker.rank(collection)

    table = Table(title="Ranked Evidence")
    table.add_column("Score", style="cyan")
    table.add_column("Source", style="white")
    table.add_column("Claim", style="dim")

    for ev in ranked.items:
        for claim in ev.claims:
            table.add_row(
                f"{ev.confidence_score:.2f}",
                ev.source_url[:60],
                claim.claim[:80],
            )

    console.print(table)

    if output:
        output.write_text(
            json.dumps([e.model_dump() for e in ranked.items], indent=2),
            encoding="utf-8",
        )
        console.print(f"[green]Written to {output}[/green]")


@app.command()
def runtime_check() -> None:
    """Show runtime environment status."""
    checker = RuntimeChecker()
    env = checker.check_all()

    table = Table(title="Runtime Environment")
    table.add_column("Component", style="cyan")
    table.add_column("Status", style="white")
    table.add_column("Detail", style="dim")

    table.add_row(
        "Proxy",
        "[green]configured[/green]" if env.has_proxy else "[yellow]not set[/yellow]",
        env.proxy_url,
    )
    table.add_row(
        "Crawl4AI",
        "[green]ok[/green]" if env.crawl4ai_available else "[red]missing[/red]",
        env.crawl4ai_message,
    )
    table.add_row(
        "Playwright",
        "[green]ok[/green]" if env.playwright_available else "[red]missing[/red]",
        env.playwright_message,
    )
    table.add_row(
        "CloakBrowser",
        "[green]ok[/green]" if env.cloakbrowser_available else "[yellow]not configured[/yellow]",
        env.cloakbrowser_message,
    )

    console.print(table)


@app.command()
def browser_check() -> None:
    """Validate browser runtime configuration."""
    settings = get_settings()
    engine = settings.browser_engine

    if engine not in ("playwright", "cloakbrowser"):
        console.print(f"[red]Unknown browser engine: {engine}. Use 'playwright' or 'cloakbrowser'.[/red]")
        raise typer.Exit(1)

    if engine == "cloakbrowser":
        exe = settings.cloakbrowser_executable
        if not exe:
            console.print("[red]OSINT_CLOAKBROWSER_EXECUTABLE not set.[/red]")
            console.print("  Set it in .env or export it before running.")
            console.print("  Example: OSINT_CLOAKBROWSER_EXECUTABLE=/path/to/cloakbrowser")
            raise typer.Exit(1)
        from pathlib import Path
        if not Path(exe).exists():
            console.print(f"[red]CloakBrowser executable not found at: {exe}[/red]")
            raise typer.Exit(1)
        console.print(f"[green]CloakBrowser configured at: {exe}[/green]")

    elif engine == "playwright":
        import importlib
        try:
            importlib.import_module("playwright")
            console.print("[green]Playwright is installed[/green]")
        except ImportError:
            console.print("[yellow]Playwright not installed. Run: pip install osint-pipeline[browser][/yellow]")

    if settings.proxy_url:
        console.print(f"[dim]Proxy: {mask_proxy_url(settings.proxy_url)}[/dim]")


@app.command()
def crawl_url(
    url: str = typer.Argument(..., help="URL to crawl"),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Output file"),
    output_format: str = typer.Option("markdown", "--format", "-f", help="Output format: markdown, html, text"),
) -> None:
    """Crawl a URL via Crawl4AI adapter."""
    adapter = Crawl4AIAdapter()
    if not adapter.available:
        console.print(f"[red]{adapter.install_hint}[/red]")
        raise typer.Exit(1)

    settings = get_settings()
    proxy = settings.proxy_url or None

    result = _run_async(adapter.crawl_url(
        url,
        proxy_url=proxy,
        output_format=output_format,
    ))

    if result is None:
        console.print("[red]Crawl returned no result[/red]")
        raise typer.Exit(1)

    if result.error:
        console.print(f"[red]Crawl error: {result.error}[/red]")
        raise typer.Exit(1)

    content = result.content or ""
    console.print(Panel.fit(content[:2000] if len(content) > 2000 else content, title=f"Crawl: {url}"))

    if output:
        output.write_text(content, encoding="utf-8")
        console.print(f"[green]Written to {output}[/green]")


@app.command()
def route_dork(
    dork_file: Path = typer.Argument(..., help="JSON file with DorkSchema or DorkQuery"),
) -> None:
    """Route a dork query to the appropriate connector."""
    data = json.loads(dork_file.read_text(encoding="utf-8"))
    router = SourceRouter()

    # Accept either a full DorkSchema or a single DorkQuery
    dorks: list[DorkQuery] = []
    if "dork_queries" in data:
        schema = DorkSchema(**data)
        dorks = schema.dork_queries
    else:
        dorks = [DorkQuery(**data)]

    table = Table(title="Dork Routing Results")
    table.add_column("Target", style="cyan")
    table.add_column("Connector", style="white")
    table.add_column("Mode", style="dim")
    table.add_column("Reason", style="green")

    try:
        for d in dorks:
            route = router.route(d)
            table.add_row(
                d.target.value,
                route.connector,
                route.execution_mode,
                route.reason,
            )
    except RouterError as e:
        console.print(f"[red]Routing failed: {e}[/red]")
        raise typer.Exit(1)

    console.print(table)


@app.command()
def run_research(
    query: str = typer.Argument(..., help="Research query"),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Output JSON file"),
    max_dorks: int = typer.Option(25, "--max-dorks", help="Max dork queries to execute"),
    max_results: int = typer.Option(50, "--max-results", "-n", help="Max sources to process"),
    max_per_connector: int = typer.Option(20, "--max-per-connector", help="Max sources per connector"),
    enrich: bool = typer.Option(False, "--enrich", help="Crawl URLs via Crawl4AI"),
    dedup_mode: str = typer.Option("url", "--dedup", help="Dedup mode: url, canonical_url, domain_url"),
    min_confidence: float = typer.Option(0.0, "--min-confidence", help="Min evidence confidence (0-1)"),
    disable_connector: Optional[list[str]] = typer.Option(None, "--disable-connector", help="Disable connector"),
    language: Optional[list[str]] = typer.Option(None, "--language", "-l", help="Allowed language codes"),
    archive: str = typer.Option("live_first", "--archive", help="live_first, archive_first, archive_only"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Expand+dork+route only, no connector calls"),
    concurrency: Optional[int] = typer.Option(None, "--concurrency", help="Max concurrent connector calls"),
    per_connector_concurrency: Optional[int] = typer.Option(None, "--per-connector-concurrency", help="Max concurrent calls per connector"),
    connector_timeout: float = typer.Option(30.0, "--connector-timeout", help="Connector timeout in seconds"),
    profile: Optional[str] = typer.Option(None, "--profile", help="Config preset: smoke, archive_first, deleted_content, multi_engine, foreign_index, deep_archive"),
    fixture_mode: bool = typer.Option(False, "--fixture", help="Use test fixtures instead of live connectors"),
    fixture_dir: Optional[Path] = typer.Option(None, "--fixture-dir", help="Fixture directory path"),
) -> None:
    """Execute a full research pipeline: expand, dork, route, fetch, extract, rank."""
    p = profile
    _disabled = disable_connector

    if p is None:
        presets = dict(max_dorks=25, max_results=50, max_tasks=3, max_per=20,
                       enrich=False, dedup="canonical_url", min_conf=0.0,
                       concur=concurrency or 5, per_concur=per_connector_concurrency or 2,
                       archive_pref=archive, enabled=None, required=None,
                       disable=_disabled, langs=language)
    elif p == "smoke":
        base = ["searxng", "gdelt", "openalex"]
        enabled = [c for c in base if c not in (_disabled or [])]
        presets = dict(max_dorks=3, max_results=10, max_tasks=2, max_per=10,
                       enrich=False, dedup="canonical_url", min_conf=0.3,
                       concur=concurrency or 3, per_concur=per_connector_concurrency or 1,
                       archive_pref="live_first", enabled=enabled, required=list(enabled),
                       disable=None, langs=language)
    elif p == "archive_first":
        base_disabled = ["github", "reddit"]
        final_disabled = list(set((_disabled or []) + base_disabled))
        presets = dict(max_dorks=5, max_results=30, max_tasks=3, max_per=15,
                       enrich=False, dedup="url", min_conf=0.0,
                       concur=concurrency or 4, per_concur=per_connector_concurrency or 2,
                       archive_pref="archive_first", enabled=None, required=None,
                       disable=final_disabled, langs=language)
    elif p == "deleted_content":
        presets = dict(max_dorks=8, max_results=50, max_tasks=3, max_per=20,
                       enrich=True, dedup="canonical_url", min_conf=0.0,
                       concur=concurrency or 3, per_concur=per_connector_concurrency or 1,
                       archive_pref="archive_only", enabled=None, required=None,
                       disable=_disabled, langs=language)
    elif p == "multi_engine":
        presets = dict(max_dorks=12, max_results=80, max_tasks=4, max_per=20,
                       enrich=False, dedup="canonical_url", min_conf=0.0,
                       concur=concurrency or 5, per_concur=per_connector_concurrency or 2,
                       archive_pref="live_first", enabled=None, required=None,
                       disable=_disabled, langs=language)
    elif p == "foreign_index":
        base = ["searxng", "gdelt", "openalex", "github", "wikidata"]
        enabled = [c for c in base if c not in (_disabled or [])]
        presets = dict(max_dorks=10, max_results=60, max_tasks=3, max_per=15,
                       enrich=False, dedup="canonical_url", min_conf=0.0,
                       concur=concurrency or 4, per_concur=per_connector_concurrency or 2,
                       archive_pref="live_first", enabled=enabled, required=list(enabled),
                       disable=None, langs=["en", "ru", "zh", "ar", "fa", "tr"])
    elif p == "deep_archive":
        base = ["archive_cdx", "commoncrawl", "searxng", "openalex"]
        enabled = [c for c in base if c not in (_disabled or [])]
        presets = dict(max_dorks=10, max_results=80, max_tasks=4, max_per=25,
                       enrich=True, dedup="canonical_url", min_conf=0.0,
                       concur=concurrency or 3, per_concur=per_connector_concurrency or 1,
                       archive_pref="archive_first", enabled=enabled, required=list(enabled),
                       disable=None, langs=language)
    else:
        console.print(f"[red]Unknown profile: {profile}. Options: smoke, archive_first, deleted_content, multi_engine, foreign_index, deep_archive[/red]")
        raise typer.Exit(1)

    runner = ResearchRunner()
    config = ResearchRunConfig(
        max_dorks=presets["max_dorks"],
        max_results=presets["max_results"],
        max_tasks_per_connector=presets["max_tasks"],
        max_results_per_connector=presets["max_per"],
        enrich=presets["enrich"],
        dedup_mode=presets["dedup"],
        min_evidence_confidence=presets["min_conf"],
        disabled_connectors=presets["disable"],
        enabled_connectors=presets["enabled"],
        enabled_languages=presets["langs"],
        archive_preference=presets["archive_pref"],
        required_connectors=presets["required"],
        max_concurrency=presets["concur"],
        max_concurrency_per_connector=presets["per_concur"],
        connector_timeout_seconds=connector_timeout,
        searxng_strategy=PROFILE_SEARXNG.get(profile, {}).get("strategy", "default") if profile else "default",
        searxng_engines=PROFILE_SEARXNG.get(profile, {}).get("engines", ()) if profile else (),
        _profile_name=profile,
        dry_run=dry_run,
        fixture_mode=fixture_mode,
        fixture_dir=str(fixture_dir) if fixture_dir else None,
    )
    artifact = _run_async(runner.run(query, config))

    status_color = "[green]" if artifact.status == "completed" else "[yellow]"
    t = artifact.timing

    console.print(Panel.fit(
        f"[bold]Research Run: {artifact.run_id}[/bold]\n\n"
        f"Query: {artifact.query}\n"
        f"Expansions: {len(artifact.expansions)}  |  Dorks: {len(artifact.dorks)}\n"
        f"Routes executed: {artifact.routes}  |  Sources: {artifact.sources_fetched}\n"
        f"Claims: {artifact.claims_extracted}\n"
        f"Graph: {artifact.graph.nodes if artifact.graph else 0} nodes, "
        f"{artifact.graph.edges if artifact.graph else 0} edges\n"
        f"Status: {status_color}{artifact.status}[/]\n\n"
        f"[dim]Timing: expand {t.expand:.1f}s | dork {t.dork:.1f}s | "
        f"fetch {t.fetch:.1f}s | extract {t.extract:.1f}s | rank {t.rank:.1f}s[/dim]",
        title="Research Run",
    ))

    if artifact.errors:
        console.print("[yellow]Errors during run:[/yellow]")
        for e in artifact.errors:
            console.print(f"  [dim]{e}[/dim]")

    safe_data = artifact.model_dump_safe()
    archiver = RunArchiver()
    run_dir = archiver.archive_run(
        query=query,
        artifact_data=safe_data,
        profile=profile,
        timing=safe_data.get("timing"),
        errors=artifact.errors if artifact.errors else None,
    )

    if output:
        output.write_text(json.dumps(safe_data, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
        console.print(f"[green]Results written to {output}[/green]")

    console.print(f"[dim]Archived: {run_dir}[/dim]")

    if artifact.errors:
        raise typer.Exit(1)


@app.command()
def export_graph(
    evidence_file: Path = typer.Argument(..., help="JSON evidence collection file"),
    format: str = typer.Option("graphml", "--format", "-f", help="Output format: graphml, json, csv-nodes, csv-edges"),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Output file path"),
) -> None:
    """Build and export an evidence graph."""
    from .models.evidence import EvidenceCollection

    data = json.loads(evidence_file.read_text(encoding="utf-8"))
    collection = EvidenceCollection(**data)

    builder = EvidenceGraphBuilder()
    graph = builder.build(collection)

    exporter = EvidenceGraphExporter()
    out_path = output or Path(f"evidence_graph.{format.replace('csv-', 'csv_')}")

    if format == "graphml":
        exporter.to_graphml(graph, out_path)
    elif format == "json":
        exporter.to_json(graph, out_path)
    elif format == "csv-nodes":
        exporter.to_csv_nodes(graph, out_path)
    elif format == "csv-edges":
        exporter.to_csv_edges(graph, out_path)
    else:
        console.print(f"[red]Unknown format: {format}. Options: graphml, json, csv-nodes, csv-edges[/red]")
        raise typer.Exit(1)

    console.print(f"[green]Graph exported to {out_path} ({len(graph.nodes)} nodes, {len(graph.edges)} edges)[/green]")


@app.command()
def validate_artifact(
    artifact_file: Path = typer.Argument(..., help="Research artifact JSON file"),
) -> None:
    """Validate a research artifact for schema compliance and secrets."""
    import re

    data = json.loads(artifact_file.read_text(encoding="utf-8"))
    errors: list[str] = []

    # Pydantic schema validation
    try:
        artifact = ResearchArtifact(**data)
        artifact.model_dump_safe()
    except Exception as e:
        errors.append(f"Pydantic validation failed: {e}")

    if errors:
        for e in errors:
            console.print(f"[red]{e}[/red]")
        raise typer.Exit(1)

    # Structural checks
    if not artifact.run_id:
        errors.append("Missing run_id")
    if artifact.dry_run:
        pass  # dry-run artifacts have no sources/evidence
    else:
        if artifact.sources_fetched > 0:
            # Check lineage attached to sources via connector_results
            if not artifact.connector_results:
                errors.append("connector_results missing")

    if not artifact.lineages:
        errors.append("Missing lineages (empty lineage list)")
    else:
        for li in artifact.lineages:
            li_data = li if isinstance(li, dict) else li.model_dump()
            if not li_data.get("connector"):
                errors.append(f"lineage {li_data.get('id', '?')} missing connector")

    if artifact.graph is None:
        errors.append("Missing graph summary")

    if artifact.quality_controls is None:
        errors.append("Missing quality_controls")

    if artifact.timing is None:
        errors.append("Missing timing")

    # Secret detection via raw JSON text
    raw = artifact_file.read_text()
    secret_patterns = [
        r"sk-[a-zA-Z0-9_-]{10,}",
        r"gh[ps]_[a-zA-Z0-9]{10,}",
        r"Authorization: Bearer \S+",
    ]
    for pat in secret_patterns:
        if re.search(pat, raw):
            errors.append(f"Secret pattern detected in artifact: {pat}")

    if errors:
        console.print("[red]Artifact validation failed:[/red]")
        for e in errors:
            console.print(f"  [red]- {e}[/red]")
        raise typer.Exit(1)

    t = artifact.timing
    console.print("[green]Artifact validation passed[/green]")
    console.print(Panel.fit(
        f"Run: {artifact.run_id}\n"
        f"Status: {artifact.status}\n"
        f"Sources: {artifact.sources_fetched}  |  Claims: {artifact.claims_extracted}\n"
        f"Graph: {artifact.graph.nodes if artifact.graph else 0}n / {artifact.graph.edges if artifact.graph else 0}e\n"
        f"Timing: {t.total:.1f}s  |  Dry-run: {artifact.dry_run}",
        title="Artifact Summary",
    ))


@app.command()
def proxy_check(
    compare_direct: bool = typer.Option(False, "--compare-direct", help="Also show direct (non-proxied) IP"),
) -> None:
    """Check proxy connectivity and DNS behavior."""
    import httpx

    settings = get_settings()
    proxy_url = settings.proxy_url
    warnings: list[str] = []
    info: dict[str, object] = {}

    info["proxy_configured"] = bool(proxy_url)
    info["masked_proxy_url"] = mask_proxy_url(proxy_url) if proxy_url else "(none)"

    if proxy_url:
        if proxy_url.startswith("socks5://"):
            warnings.append(
                "SOCKS proxy configured as socks5://. Remote DNS behavior is library-dependent. "
                "Use proxy-check to verify routing. "
                "Prefer socks5h:// only if supported by your httpx/socksio stack."
            )
        elif proxy_url.startswith("socks5h://") or proxy_url.startswith("socks4://"):
            pass  # no special warning needed

        # Check socksio library
        socks_ok = False
        try:
            import socksio  # noqa: F401
            socks_ok = True
        except ImportError:
            pass
        try:
            import httpx_socks  # noqa: F401
            socks_ok = True
        except ImportError:
            pass
        info["socks_library_available"] = socks_ok
        if not socks_ok and ("socks" in proxy_url):
            warnings.append(
                "SOCKS proxy configured but socksio/httpx-socks not installed. "
                "Run: pip install 'osint-pipeline[proxy]'"
            )

        # Test proxied IP
        try:
            transport = httpx.AsyncHTTPTransport(proxy=proxy_url)
            async def _check():
                async with httpx.AsyncClient(transport=transport, timeout=10) as c:
                    r = await c.get("https://api.ipify.org?format=json")
                    return r.json().get("ip", "unknown")
            import asyncio
            proxied_ip = asyncio.run(_check())
            info["proxy_route_verified"] = True
            info["proxied_ip"] = proxied_ip
        except Exception as exc:
            info["proxy_route_verified"] = False
            safe_err = sanitize_error_message(str(exc))
            warnings.append(f"Proxy route verification failed: {safe_err}")

        if compare_direct:
            try:
                async def _direct():
                    async with httpx.AsyncClient(timeout=10) as c:
                        r = await c.get("https://api.ipify.org?format=json")
                        return r.json().get("ip", "unknown")
                import asyncio
                direct_ip = asyncio.run(_direct())
                info["direct_ip"] = direct_ip
            except Exception as exc:
                info["direct_ip"] = "unreachable"
                warnings.append(f"Direct route unreachable: {sanitize_error_message(str(exc))}")

    table = Table(title="Proxy Diagnostics")
    table.add_column("Check", style="cyan")
    table.add_column("Value", style="white")

    for k, v in info.items():
        pretty_key = k.replace("_", " ").title()
        val_str = str(v)
        if isinstance(v, bool):
            val_str = "[green]yes[/green]" if v else "[red]no[/red]"
        table.add_row(pretty_key, val_str)

    console.print(table)

    if warnings:
        for w in warnings:
            console.print(f"[yellow]Warning: {w}[/yellow]")

    if not info.get("proxy_route_verified", False) and proxy_url:
        raise typer.Exit(1)


if __name__ == "__main__":
    app()

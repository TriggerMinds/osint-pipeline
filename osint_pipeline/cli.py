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
from .connectors import SearXNGConnector, GDELTConnector, ArchiveCDXConnector, CommonCrawlConnector
from .extraction import EvidenceExtractor
from .ranking import EvidenceRanker
from .runtime.checks import RuntimeChecker
from .crawler import Crawl4AIAdapter

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

    from .runtime.checks import RuntimeChecker
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
        "searxng", "--source", "-s", help="Source: searxng, gdelt"
    ),
    language: str = typer.Option("en", "--language", "-l", help="Language code"),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Output JSON file"),
) -> None:
    """Execute a search against a configured source connector."""
    connectors = {
        "searxng": SearXNGConnector(),
        "gdelt": GDELTConnector(),
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

    console.print(table)

    if result.error:
        console.print(f"[red]Error: {result.error}[/red]")

    if output:
        output.write_text(
            json.dumps([s.metadata.model_dump() for s in result.sources], indent=2),
            encoding="utf-8",
        )
        console.print(f"[green]Written to {output}[/green]")


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
        console.print(f"[dim]Proxy: {settings.proxy_url}[/dim]")


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


if __name__ == "__main__":
    app()

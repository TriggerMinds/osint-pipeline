import pytest
import respx
from httpx import Response

from osint_pipeline.connectors import (
    OpenAlexConnector,
    GitHubSearchConnector,
    WikidataConnector,
    RedditConnector,
)
from osint_pipeline.models.source import SourceType, FetchStatus


# ── OpenAlex ──────────────────────────────────────────────────────────


class TestOpenAlexConnector:
    @pytest.fixture
    def connector(self):
        return OpenAlexConnector()

    @pytest.mark.asyncio
    async def test_search_returns_works(self, connector):
        with respx.mock:
            route = respx.get("https://api.openalex.org/works").respond(
                status_code=200,
                json={
                    "results": [
                        {
                            "id": "https://openalex.org/W123",
                            "title": "Test Paper",
                            "language": "en",
                        }
                    ]
                },
            )
            result = await connector.search("quantum computing")
            assert route.called
            assert len(result.sources) == 1
            s = result.sources[0]
            assert s.metadata.source_type == SourceType.OPENALEX
            assert s.metadata.title == "Test Paper"

    @pytest.mark.asyncio
    async def test_health(self, connector):
        with respx.mock:
            respx.get("https://api.openalex.org/works").respond(
                status_code=200, json={"results": []}
            )
            assert await connector.health() is True


# ── GitHub ────────────────────────────────────────────────────────────


class TestGitHubConnector:
    @pytest.fixture
    def connector(self):
        return GitHubSearchConnector()

    @pytest.mark.asyncio
    async def test_search_repos(self, connector):
        with respx.mock:
            route = respx.get("https://api.github.com/search/repos").respond(
                status_code=200,
                json={
                    "items": [
                        {
                            "html_url": "https://github.com/user/repo",
                            "name": "awesome-osint",
                            "description": "An OSINT tool",
                        }
                    ]
                },
            )
            result = await connector.search("osint")
            assert route.called
            assert len(result.sources) == 1
            assert result.sources[0].metadata.source_type == SourceType.GITHUB
            assert result.sources[0].metadata.title == "awesome-osint"

    @pytest.mark.asyncio
    async def test_rate_limit_returns_error(self, connector):
        with respx.mock:
            respx.get("https://api.github.com/search/repos").respond(status_code=403)
            result = await connector.search("test")
            assert result.error is not None
            assert "rate limit" in result.error

    @pytest.mark.asyncio
    async def test_health(self, connector):
        with respx.mock:
            respx.get("https://api.github.com/zen").respond(status_code=200, text="hello")
            assert await connector.health() is True


# ── Wikidata ──────────────────────────────────────────────────────────


class TestWikidataConnector:
    @pytest.fixture
    def connector(self):
        return WikidataConnector()

    @pytest.mark.asyncio
    async def test_search_returns_entities(self, connector):
        with respx.mock:
            route = respx.get(
                "https://query.wikidata.org/sparql"
            ).respond(
                status_code=200,
                json={
                    "results": {
                        "bindings": [
                            {
                                "item": {"value": "http://www.wikidata.org/entity/Q42"},
                                "itemLabel": {"value": "Douglas Adams"},
                                "itemDescription": {"value": "English author"},
                                "article": {"value": "https://en.wikipedia.org/wiki/Douglas_Adams"},
                            }
                        ]
                    }
                },
            )
            result = await connector.search("Douglas Adams")
            assert route.called
            assert len(result.sources) == 1
            s = result.sources[0]
            assert s.metadata.source_type == SourceType.WIKIDATA
            assert s.metadata.title == "Douglas Adams"
            assert "en.wikipedia.org" in s.metadata.url


# ── Reddit ────────────────────────────────────────────────────────────


class TestRedditConnector:
    @pytest.fixture
    def connector(self):
        return RedditConnector()

    @pytest.mark.asyncio
    async def test_search_returns_posts(self, connector):
        with respx.mock:
            route = respx.get("https://www.reddit.com/search.json").respond(
                status_code=200,
                json={
                    "data": {
                        "children": [
                            {
                                "data": {
                                    "title": "OSINT Tools",
                                    "url": "/r/osint/comments/abc/",
                                    "selftext": "List of tools",
                                }
                            }
                        ]
                    }
                },
            )
            result = await connector.search("osint tools")
            assert route.called
            assert len(result.sources) == 1
            s = result.sources[0]
            assert s.metadata.source_type == SourceType.REDDIT
            assert s.metadata.title == "OSINT Tools"
            assert "reddit.com" in s.metadata.url

    @pytest.mark.asyncio
    async def test_rate_limit_returns_error(self, connector):
        with respx.mock:
            respx.get("https://www.reddit.com/search.json").respond(status_code=429)
            result = await connector.search("test")
            assert result.error is not None
            assert "ConnectorRetriesExhaustedError" in result.error or "429" in result.error


# ── Search CLI dispatcher ─────────────────────────────────────────────


class TestSearchCLIDispatcher:
    """Verify the search command's connector dict includes all new names."""

    def test_search_command_imports(self):
        from osint_pipeline.cli import app
        assert len(app.registered_commands) > 0

    def _invoke_search(self, source: str):
        """Helper: mock the connector endpoint and invoke osint search."""
        import respx
        from typer.testing import CliRunner
        from osint_pipeline.cli import app
        runner = CliRunner()

        # Mock the relevant API endpoints so the search proceeds
        mocks = {
            "openalex": ("https://api.openalex.org/works", {"results": []}),
            "github": ("https://api.github.com/search/repos", {"items": []}),
            "wikidata": ("https://query.wikidata.org/sparql", {"results": {"bindings": []}}),
            "reddit": ("https://www.reddit.com/search.json", {"data": {"children": []}}),
        }

        url, body = mocks.get(source, (None, None))
        if url:
            with respx.mock:
                respx.get(url).respond(status_code=200, json=body)
                return runner.invoke(app, ["search", "test", "--source", source])
        return runner.invoke(app, ["search", "test", "--source", source])

    def test_search_openalex(self):
        r = self._invoke_search("openalex")
        assert r.exit_code == 0

    def test_search_github(self):
        r = self._invoke_search("github")
        assert r.exit_code == 0

    def test_search_wikidata(self):
        r = self._invoke_search("wikidata")
        assert r.exit_code == 0

    def test_search_reddit(self):
        r = self._invoke_search("reddit")
        assert r.exit_code == 0

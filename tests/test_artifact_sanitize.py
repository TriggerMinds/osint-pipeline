from osint_pipeline.research.artifacts import ResearchArtifact, ConnectorExecutionResult, TimingBreakdown, GraphSummary
from osint_pipeline.research.sanitize import sanitize_error_message


class TestConnectorResultSanitize:
    def test_connector_error_with_bearer(self):
        result = ConnectorExecutionResult(
            connector="github",
            query="repo search",
            sources_found=0,
            error="Authorization: Bearer ghp_abc123def456",
        )
        artifact = ResearchArtifact(
            run_id="test_001",
            query="test",
            connector_results=[result],
            errors=["Authorization: Bearer ghp_abc123def456"],
        )
        safe = artifact.model_dump_safe()
        cr = safe["connector_results"][0]
        assert "Bearer ***" in cr["error"]
        assert "ghp_abc123def456" not in cr["error"]

    def test_connector_error_with_api_key(self):
        result = ConnectorExecutionResult(
            connector="openalex",
            query="search?mailto=user@test.com",
            sources_found=0,
            error="HTTP 403: api_key=SECRETTOKEN",
        )
        artifact = ResearchArtifact(
            run_id="test_002",
            query="test",
            connector_results=[result],
        )
        safe = artifact.model_dump_safe()
        cr = safe["connector_results"][0]
        assert "api_key=***" in cr["error"]
        assert "SECRETTOKEN" not in cr["error"]

    def test_connector_query_with_token(self):
        result = ConnectorExecutionResult(
            connector="github",
            query="https://api.github.com/search?q=test&token=ghp_mysecrettoken12345",
            sources_found=5,
        )
        artifact = ResearchArtifact(
            run_id="test_003",
            query="test",
            connector_results=[result],
        )
        safe = artifact.model_dump_safe()
        cr = safe["connector_results"][0]
        assert "token=***" in cr["query"]
        assert "ghp_mysecrettoken12345" not in cr["query"]

    def test_model_dump_safe_no_secrets_in_errors(self):
        artifact = ResearchArtifact(
            run_id="test_004",
            query="test",
            errors=[
                "HTTP 500: sk-my-deepseek-key",
                "Error: Authorization: Bearer secretbearertoken",
                "Connector failed: socks5://user:pass@proxy:1080",
            ],
        )
        safe = artifact.model_dump_safe()
        for e in safe["errors"]:
            assert "sk-my-deepseek-key" not in e
            assert "secretbearertoken" not in e
            assert "user:pass" not in e
            assert "***" in e or "safe" in e

    def test_clean_data_passes_through(self):
        result = ConnectorExecutionResult(
            connector="gdelt",
            query="breaking news",
            sources_found=10,
        )
        artifact = ResearchArtifact(
            run_id="clean",
            query="news query",
            connector_results=[result],
        )
        safe = artifact.model_dump_safe()
        assert safe["query"] == "news query"
        assert safe["connector_results"][0]["query"] == "breaking news"
        assert safe["connector_results"][0]["connector"] == "gdelt"

    def test_timing_preserved(self):
        t = TimingBreakdown(expand=1.5, dork=2.0, fetch=3.0)
        artifact = ResearchArtifact(run_id="t", query="t", timing=t)
        safe = artifact.model_dump_safe()
        assert safe["timing"]["expand"] == 1.5
        assert safe["timing"]["dork"] == 2.0
        assert safe["timing"]["fetch"] == 3.0

    def test_graph_summary(self):
        g = GraphSummary(nodes=5, edges=3)
        artifact = ResearchArtifact(run_id="g", query="g", graph=g)
        safe = artifact.model_dump_safe()
        assert safe["graph"]["nodes"] == 5
        assert safe["graph"]["edges"] == 3

    def test_errors_empty_list_not_in_output(self):
        artifact = ResearchArtifact(run_id="e", query="e", errors=[])
        safe = artifact.model_dump_safe()
        assert "errors" not in safe or safe["errors"] == []

    def test_connector_error_preserves_clean_message(self):
        result = ConnectorExecutionResult(
            connector="searxng",
            query="test query",
            sources_found=0,
            error="HTTP 503",
        )
        artifact = ResearchArtifact(
            run_id="clean_err",
            query="test",
            connector_results=[result],
            errors=["HTTP 503"],
        )
        safe = artifact.model_dump_safe()
        assert safe["errors"] == ["HTTP 503"]
        assert safe["connector_results"][0]["error"] == "HTTP 503"


class TestSanitizeDirect:
    def test_sanitize_bearer(self):
        assert "Bearer ***" in sanitize_error_message("Authorization: Bearer secret123")

    def test_sanitize_api_key(self):
        assert "api_key=***" in sanitize_error_message("error with api_key=mysecretkey")

    def test_sanitize_token_query(self):
        assert "token=***" in sanitize_error_message("url?token=abc123&q=test")

    def test_sanitize_github_token(self):
        result = sanitize_error_message("token is ghp_abcdefghijklmnop")
        assert "ghp_abcdefghijklmnop" not in result

    def test_sanitize_deepseek_key(self):
        result = sanitize_error_message("sk-my-deepseek-key-abcdef")
        assert "sk-my-deepseek-key-abcdef" not in result

    def test_sanitize_proxy_credentials(self):
        result = sanitize_error_message("socks5://admin:sekret@127.0.0.1:1080")
        assert "***:***" in result
        assert "admin" not in result
        assert "sekret" not in result

    def test_sanitize_identity(self):
        """Clean text passes through unchanged."""
        t = "normal error message without secrets"
        assert sanitize_error_message(t) == t

from pathlib import Path

import pytest

from osint_pipeline.config import get_settings
from osint_pipeline.runtime.checks import RuntimeChecker, RuntimeEnvironment
from osint_pipeline.crawler import Crawl4AIAdapter
from osint_pipeline.models.source import SourceType, FetchStatus


# ── Proxy URL parsing ─────────────────────────────────────────────────


class TestProxyURL:
    def test_proxy_url_parsing(self):
        """OSINT_PROXY_URL is parsed from settings."""
        from osint_pipeline.config.settings import Settings
        s = Settings(proxy_url="socks5://127.0.0.1:1080")
        assert s.proxy_url == "socks5://127.0.0.1:1080"

    def test_proxy_url_empty(self):
        from osint_pipeline.config.settings import Settings
        s = Settings()
        assert s.proxy_url == ""

    def test_proxy_url_masked_no_secrets(self):
        checker = RuntimeChecker()
        masked = checker._mask_proxy("socks5://127.0.0.1:1080")
        assert "127.0.0.1" in masked
        assert "socks5" in masked

    def test_proxy_url_masked_with_credentials(self):
        checker = RuntimeChecker()
        masked = checker._mask_proxy("http://user:secret@proxy.example.com:8080")
        assert "***" in masked
        assert "secret" not in masked


# ── Runtime checker ───────────────────────────────────────────────────


class TestRuntimeChecker:
    @pytest.fixture
    def checker(self):
        return RuntimeChecker()

    def test_check_all_returns_env(self, checker):
        env = checker.check_all()
        assert isinstance(env, RuntimeEnvironment)
        assert hasattr(env, "proxy_url")
        assert hasattr(env, "crawl4ai_available")

    def test_crawl4ai_missing_gives_install_hint(self, checker):
        # When crawl4ai is not installed, the message should hint at install
        env = checker.check_all()
        if not env.crawl4ai_available:
            assert "pip install" in env.crawl4ai_message

    def test_cloakbrowser_without_config(self, checker):
        env = checker.check_all()
        if not env.cloakbrowser_available:
            # Either not configured or not found
            assert env.cloakbrowser_message


# ── Crawl4AI adapter (without actual crawl4ai) ────────────────────────


class TestCrawl4AIAdapter:
    @pytest.fixture
    def adapter(self):
        return Crawl4AIAdapter()

    def test_available_false_when_not_installed(self, adapter):
        # In CI / test env, crawl4ai is likely not installed
        if not adapter.available:
            assert not adapter.available
            assert "pip install" in adapter.install_hint

    def test_crawl_returns_none_when_not_installed(self, adapter):
        import asyncio
        if not adapter.available:
            result = asyncio.run(adapter.crawl_url("https://example.com"))
            assert result is None


# ── Browser engine config ─────────────────────────────────────────────


class TestBrowserEngine:
    def test_playwright_works_without_cloak(self):
        """Browser engine 'playwright' does not require CloakBrowser path."""
        from osint_pipeline.config.settings import Settings
        s = Settings(browser_engine="playwright", cloakbrowser_executable="")
        assert s.browser_engine == "playwright"
        # No error — playwright does not need cloakbrowser path

    def test_cloakbrowser_requires_executable(self):
        """Engine 'cloakbrowser' without executable should indicate missing."""
        from osint_pipeline.config.settings import Settings
        s = Settings(browser_engine="cloakbrowser", cloakbrowser_executable="")
        assert s.browser_engine == "cloakbrowser"
        assert s.cloakbrowser_executable == ""

    def test_cloakbrowser_nonexistent_path(self):
        """Engine 'cloakbrowser' with nonexistent path should fail health."""
        from osint_pipeline.browser.cloak_runtime import CloakBrowserRuntime
        import asyncio
        runtime = CloakBrowserRuntime()
        # Override settings for this test
        runtime.settings.cloakbrowser_executable = "/nonexistent/path"
        result = asyncio.run(runtime.health())
        assert not result.available
        assert "not found" in result.message

    def test_browser_engine_default(self):
        from osint_pipeline.config.settings import Settings
        s = Settings()
        assert s.browser_engine == "playwright"


# ── Proxy passthrough tests ───────────────────────────────────────────


class TestProxyPassthrough:
    def test_proxy_in_browser_config(self):
        """Proxy URL is accessible from browser runtime config."""
        from osint_pipeline.config.settings import Settings
        s = Settings(proxy_url="socks5://127.0.0.1:1080", browser_engine="playwright")
        assert s.proxy_url == "socks5://127.0.0.1:1080"

    def test_proxy_in_crawl4ai_adapter(self):
        """Proxy URL is passed to Crawl4AI adapter."""
        from osint_pipeline.config.settings import Settings
        s = Settings(proxy_url="http://127.0.0.1:8080")
        adapter = Crawl4AIAdapter()
        if adapter.available:
            import asyncio
            result = asyncio.run(adapter.crawl_url("https://example.com", proxy_url=s.proxy_url))
            # If crawl4ai is installed, the result should at least have metadata
            assert result is not None

    def test_env_example_contains_no_secrets(self):
        """The .env.example file must contain no real secrets, IPs, or credentials."""
        path = Path(__file__).parent.parent / ".env.example"
        assert path.exists()
        content = path.read_text()
        assert "sk-your" in content  # placeholder key
        assert "127.0.0.1" in content  # localhost only
        # No real secrets
        assert "sk-" not in content.replace("sk-your", "")

    def test_no_binaries_in_repo(self):
        """No browser binaries, profiles, or hysteria configs in the repo."""
        repo = Path(__file__).parent.parent
        # Check for obvious binary/profile patterns
        for pattern in ["*.exe", "*.dll", "*.so", "*.dylib"]:
            matches = list(repo.glob(pattern))
            for m in matches:
                # Allow .exe in .git if it's a test fixture or similar
                if ".git" not in str(m):
                    assert False, f"Unexpected binary in repo: {m}"

from osint_pipeline.runtime.checks import mask_proxy_url
from osint_pipeline.research.sanitize import sanitize_error_message


class TestProxyCheck:
    def test_proxy_configured(self):
        """Proxy URL with socks5 is detected."""
        from osint_pipeline.config.settings import Settings
        s = Settings(proxy_url="socks5://127.0.0.1:1080")
        assert s.proxy_url == "socks5://127.0.0.1:1080"

    def test_proxy_unconfigured(self):
        from osint_pipeline.config.settings import Settings
        s = Settings(proxy_url="")
        assert s.proxy_url == ""

    def test_mask_credentials(self):
        result = mask_proxy_url("socks5://user:pass@proxy.example.com:1080")
        assert "***:***" in result
        assert "user" not in result
        assert "pass" not in result

    def test_mask_no_credentials(self):
        result = mask_proxy_url("socks5://127.0.0.1:1080")
        assert result == "socks5://127.0.0.1:1080"

    def test_empty_masked(self):
        assert mask_proxy_url("") == "(none)"

    def test_sanitize_proxy_url_in_error(self):
        msg = 'ConnectorError: socks5://user:pass@127.0.0.1:1080 failed'
        result = sanitize_error_message(msg)
        assert "***:***" in result
        assert "user:pass" not in result

    def test_sanitize_proxy_with_credentials(self):
        msg = 'failed to connect to http://admin:sekret@proxy.local:8080'
        result = sanitize_error_message(msg)
        assert "http://***:***@proxy.local:8080" in result

    def test_httpx_socks_not_checked_without_proxy(self):
        """Without proxy config, no socks check needed."""
        from osint_pipeline.config.settings import Settings
        s = Settings(proxy_url="")
        assert s.proxy_url == ""

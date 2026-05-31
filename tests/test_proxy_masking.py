import os

from osint_pipeline.config.settings import reset_settings
from osint_pipeline.runtime.checks import mask_proxy_url
from osint_pipeline.cli import app
from typer.testing import CliRunner

runner = CliRunner()


class TestMaskProxy:
    def test_empty_returns_none(self):
        assert mask_proxy_url("") == "(none)"

    def test_no_credentials_passthrough(self):
        assert mask_proxy_url("socks5://127.0.0.1:1080") == "socks5://127.0.0.1:1080"

    def test_username_password_masked(self):
        result = mask_proxy_url("socks5://user:pass@127.0.0.1:1080")
        assert "***:***" in result
        assert "user" not in result
        assert "pass" not in result

    def test_http_with_credentials(self):
        result = mask_proxy_url("http://user:secret@proxy.example.com:8080")
        assert "***:***" in result
        assert "secret" not in result
        assert "user" not in result

    def test_ip_and_port_preserved(self):
        result = mask_proxy_url("http://admin:admin123@203.0.113.5:3128")
        assert "203.0.113.5" in result
        assert "3128" in result
        assert "admin" not in result
        assert "admin123" not in result


class TestInitCommand:
    def test_init_masks_proxy(self):
        """init command shows masked proxy, not raw credentials."""
        reset_settings()
        os.environ["OSINT_PROXY_URL"] = "socks5://user:sekret@127.0.0.1:1080"
        try:
            result = runner.invoke(app, ["init"])
            assert result.exit_code == 0
            output = result.stdout
            assert "sekret" not in output
            assert "***:***" in output
            assert "127.0.0.1" in output
        finally:
            del os.environ["OSINT_PROXY_URL"]

    def test_init_no_proxy(self):
        """init command shows not configured when no proxy."""
        reset_settings()
        result = runner.invoke(app, ["init"])
        assert result.exit_code == 0
        # Should show proxy without error
        assert "not" in result.stdout.lower() or "proxy" in result.stdout.lower()


class TestRuntimeCheckCommand:
    def test_runtime_check_masks_proxy(self):
        """runtime-check shows masked proxy, not raw credentials."""
        reset_settings()
        os.environ["OSINT_PROXY_URL"] = "socks5://admin:secret@127.0.0.1:1080"
        try:
            result = runner.invoke(app, ["runtime-check"])
            assert result.exit_code == 0
            output = result.stdout
            assert "secret" not in output
            assert "***:***" in output
        finally:
            del os.environ["OSINT_PROXY_URL"]


class TestBrowserCheckCommand:
    def test_browser_check_masks_proxy(self):
        """browser-check shows masked proxy, not raw credentials."""
        reset_settings()
        os.environ["OSINT_PROXY_URL"] = "http://user:p4ss@proxy.local:8888"
        try:
            result = runner.invoke(app, ["browser-check"])
            assert result.exit_code == 0
            output = result.stdout
            assert "p4ss" not in output
            assert "***:***" in output
        finally:
            del os.environ["OSINT_PROXY_URL"]

    def test_browser_check_no_proxy(self):
        """browser-check works without proxy."""
        reset_settings()
        result = runner.invoke(app, ["browser-check"])
        assert result.exit_code == 0

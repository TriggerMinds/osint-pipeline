from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from .config import get_settings
from .runtime.checks import mask_proxy_url


class RunArchiver:
    def __init__(self, base_dir: str | Path = "runs") -> None:
        self.base = Path(base_dir)
        self.base.mkdir(parents=True, exist_ok=True)

    def create_run_dir(self, query: str, profile: str | None = None) -> Path:
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H%M%S")
        safe_query = "".join(c if c.isalnum() or c in "-_" else "_" for c in query)[:40]
        label = profile or "run"
        dirname = f"{ts}_{safe_query}_{label}"
        run_dir = self.base / dirname
        run_dir.mkdir(parents=True, exist_ok=True)
        return run_dir

    def write_artifact(self, run_dir: Path, data: dict) -> Path:
        path = run_dir / "run.json"
        path.write_text(
            json.dumps(data, indent=2, ensure_ascii=False, default=str),
            encoding="utf-8",
        )
        return path

    def write_diagnostic(self, run_dir: Path, extra: dict | None = None) -> Path:
        settings = get_settings()
        lines: list[str] = [
            f"=== Run Diagnostic ===",
            f"Timestamp: {datetime.now(timezone.utc).isoformat()}",
            f"",
            f"--- Environment ---",
            f"Proxy: {mask_proxy_url(settings.proxy_url)}",
            f"DeepSeek: {'configured' if settings.deepseek_api_key else 'MISSING'}",
            f"Browser: {settings.browser_engine}",
            f"Crawl4AI: {'available' if self._check_import('crawl4ai') else 'not installed'}",
            f"Playwright: {'available' if self._check_import('playwright') else 'not installed'}",
            f"",
            f"--- Connectors ---",
            f"SearXNG: {settings.searxng_instances}",
            f"GDELT: {settings.gdelt_base_url}",
            f"IA CDX: {settings.archive_cdx_url}",
            f"Common Crawl: {settings.commoncrawl_base_url}",
            f"OpenAlex email: {'set' if settings.openalex_email else 'not set'}",
            f"GitHub token: {'set' if settings.github_token else 'not set'}",
            f"",
        ]
        if extra:
            for k, v in extra.items():
                lines.append(f"{k}: {v}")

        path = run_dir / "diagnostic.log"
        path.write_text("\n".join(lines), encoding="utf-8")
        return path

    def archive_run(
        self,
        query: str,
        artifact_data: dict,
        profile: str | None = None,
        timing: dict | None = None,
        errors: list[str] | None = None,
    ) -> Path:
        run_dir = self.create_run_dir(query, profile)
        self.write_artifact(run_dir, artifact_data)
        extra = {}
        if timing:
            extra["Timing"] = json.dumps(timing)
        if errors:
            extra["Errors"] = "\n".join(errors)
        extra["Output File"] = str(run_dir / "run.json")
        self.write_diagnostic(run_dir, extra)
        return run_dir

    @staticmethod
    def _check_import(name: str) -> bool:
        try:
            __import__(name)
            return True
        except ImportError:
            return False

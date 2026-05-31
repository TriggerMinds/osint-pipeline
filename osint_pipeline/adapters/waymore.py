from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from ..models.source import SourceMetadata, SourceResult, SourceType, FetchStatus


class WaymoreAdapter:
    def __init__(self, binary: str = "waymore") -> None:
        self.binary = binary
        self._available: Optional[bool] = None

    @property
    def available(self) -> bool:
        if self._available is None:
            try:
                subprocess.run(
                    [self.binary, "--help"],
                    capture_output=True, text=True, timeout=10,
                )
                self._available = True
            except (FileNotFoundError, subprocess.TimeoutExpired, Exception):
                self._available = False
        return self._available

    @property
    def install_hint(self) -> str:
        return (
            "waymore not found.\n"
            "  Install: https://github.com/xnl-h4ck3r/waymore\n"
            "  Or set the binary path explicitly."
        )

    async def search(self, domain: str, limit: int = 50) -> list[SourceResult]:
        if not self.available:
            raise RuntimeError(self.install_hint)

        now = datetime.now(timezone.utc).isoformat()
        results: list[SourceResult] = []

        try:
            proc = subprocess.run(
                [self.binary, "-i", domain, "-mode", "u", "-n", str(limit), "-o", "json"],
                capture_output=True, text=True, timeout=60,
            )
            if proc.returncode != 0:
                return []

            for line in proc.stdout.strip().split("\n"):
                try:
                    item = json.loads(line)
                except json.JSONDecodeError:
                    continue
                url = item.get("url", item.get("u", ""))
                results.append(
                    SourceResult(
                        metadata=SourceMetadata(
                            url=url,
                            source_type=SourceType.WAYMORE,
                            language="unknown",
                            discovered_by_query=domain,
                            discovered_at=now,
                            domain=self._extract_domain(url),
                            fetch_status=FetchStatus.SUCCESS,
                        ),
                    )
                )

        except subprocess.TimeoutExpired:
            pass

        return results

    @staticmethod
    def _extract_domain(url: str) -> str:
        from urllib.parse import urlparse
        try:
            return urlparse(url).netloc
        except Exception:
            return ""

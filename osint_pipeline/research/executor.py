from __future__ import annotations

import asyncio
import time
from typing import Any

from pydantic import BaseModel, Field

from ..models.source import SourceResult
from .sanitize import sanitize_error_message


class ConnectorExecutionConfig(BaseModel):
    max_concurrency: int = 5
    max_concurrency_per_connector: int = 2
    timeout_seconds: float = 30.0


class ConnectorTask(BaseModel):
    connector: str
    query: str
    language: str | None = None
    lineage_id: str = ""
    run_id: str = ""
    synthetic: bool = False
    engines: tuple[str, ...] = ()


class ConnectorTaskResult(BaseModel):
    connector: str
    query: str
    lineage_id: str
    sources: list[SourceResult] = Field(default_factory=list)
    error: str | None = None
    latency_ms: int = 0
    synthetic: bool = False


class AsyncConnectorExecutor:
    def __init__(self, config: ConnectorExecutionConfig | None = None) -> None:
        self.config = config or ConnectorExecutionConfig()

    async def execute_batch(
        self,
        tasks: list[ConnectorTask],
        connector_registry: dict[str, Any],
    ) -> list[ConnectorTaskResult]:
        if not tasks:
            return []

        global_sem = asyncio.Semaphore(self.config.max_concurrency)
        per_conn_sems: dict[str, asyncio.Semaphore] = {}

        async def _run_one(task: ConnectorTask) -> ConnectorTaskResult:
            conn = connector_registry.get(task.connector)
            if conn is None:
                return ConnectorTaskResult(
                    connector=task.connector,
                    query=sanitize_error_message(task.query),
                    lineage_id=task.lineage_id,
                    error=f"no connector for '{task.connector}'",
                    synthetic=task.synthetic,
                )

            if task.connector not in per_conn_sems:
                per_conn_sems[task.connector] = asyncio.Semaphore(
                    self.config.max_concurrency_per_connector
                )

            async with global_sem, per_conn_sems[task.connector]:
                t0 = time.time()
                try:
                    async with asyncio.timeout(self.config.timeout_seconds):
                        kwargs: dict = {"language": task.language or "en"}
                        if task.connector == "searxng" and task.engines:
                            kwargs["engines"] = task.engines
                        result = await conn.search(task.query, **kwargs)  # type: ignore
                except TimeoutError:
                    return ConnectorTaskResult(
                        connector=task.connector,
                        query=sanitize_error_message(task.query),
                        lineage_id=task.lineage_id,
                        error=f"ConnectorTimeoutError: request timed out after {self.config.timeout_seconds}s",
                        latency_ms=int((time.time() - t0) * 1000),
                        synthetic=task.synthetic,
                    )
                except Exception as exc:
                    msg = sanitize_error_message(f"{type(exc).__name__}: {exc}")
                    return ConnectorTaskResult(
                        connector=task.connector,
                        query=sanitize_error_message(task.query),
                        lineage_id=task.lineage_id,
                        error=msg,
                        latency_ms=int((time.time() - t0) * 1000),
                        synthetic=task.synthetic,
                    )

                latency = int((time.time() - t0) * 1000)
                error = sanitize_error_message(result.error) if result.error else None

                for src in result.sources:
                    src.metadata.run_id = task.run_id
                    src.metadata.query_lineage_id = task.lineage_id
                    src.metadata.discovered_by_query = task.query

                return ConnectorTaskResult(
                    connector=task.connector,
                    query=sanitize_error_message(task.query),
                    lineage_id=task.lineage_id,
                    sources=result.sources,
                    error=error,
                    latency_ms=latency,
                    synthetic=task.synthetic,
                )

        batch_results: list[ConnectorTaskResult] = []
        results = await asyncio.gather(
            *[_run_one(t) for t in tasks],
            return_exceptions=True,
        )
        for r in results:
            if isinstance(r, ConnectorTaskResult):
                batch_results.append(r)
            elif isinstance(r, Exception):
                batch_results.append(ConnectorTaskResult(
                    connector="unknown",
                    query="",
                    lineage_id="",
                    error=sanitize_error_message(f"unexpected error: {r}"),
                ))
        return batch_results

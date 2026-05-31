import asyncio
import pytest

from osint_pipeline.research.executor import (
    AsyncConnectorExecutor, ConnectorExecutionConfig,
    ConnectorTask, ConnectorTaskResult,
)
from osint_pipeline.connectors.base import ConnectorResult
from osint_pipeline.models.source import SourceResult, SourceMetadata, SourceType


class _MockConnector:
    def __init__(self, delay: float = 0, fail: bool = False, sources_count: int = 3):
        self.delay = delay
        self.fail = fail
        self.sources_count = sources_count

    async def search(self, query: str, **kwargs):
        if self.delay:
            await asyncio.sleep(self.delay)
        if self.fail:
            raise RuntimeError("connector failure")
        sources = [
            SourceResult(
                metadata=SourceMetadata(
                    url=f"https://example.com/{query}/{i}",
                    source_type=SourceType.SEARXNG,
                    discovered_by_query=query,
                ),
            )
            for i in range(self.sources_count)
        ]
        return ConnectorResult(sources=sources)


class TestAsyncConnectorExecutor:
    @pytest.mark.asyncio
    async def test_executes_tasks(self):
        registry = {"mock": _MockConnector()}
        tasks = [ConnectorTask(connector="mock", query="test", lineage_id="l1")]
        executor = AsyncConnectorExecutor()
        results = await executor.execute_batch(tasks, registry)
        assert len(results) == 1
        assert results[0].sources
        assert results[0].error is None

    @pytest.mark.asyncio
    async def test_error_does_not_stop_batch(self):
        registry = {
            "fail": _MockConnector(fail=True),
            "ok": _MockConnector(),
        }
        tasks = [
            ConnectorTask(connector="fail", query="q1", lineage_id="l1"),
            ConnectorTask(connector="ok", query="q2", lineage_id="l2"),
        ]
        executor = AsyncConnectorExecutor()
        results = await executor.execute_batch(tasks, registry)
        assert len(results) == 2
        fail_result = next(r for r in results if r.connector == "fail")
        ok_result = next(r for r in results if r.connector == "ok")
        assert fail_result.error is not None
        assert ok_result.error is None
        assert len(ok_result.sources) > 0

    @pytest.mark.asyncio
    async def test_global_concurrency_respected(self):
        registry = {"slow": _MockConnector(delay=0.2)}
        tasks = [ConnectorTask(connector="slow", query=f"q{i}", lineage_id=f"l{i}") for i in range(5)]
        config = ConnectorExecutionConfig(max_concurrency=2, max_concurrency_per_connector=5)
        executor = AsyncConnectorExecutor(config)
        t0 = asyncio.get_event_loop().time()
        await executor.execute_batch(tasks, registry)
        elapsed = asyncio.get_event_loop().time() - t0
        # With 2 concurrency and 5 tasks at 0.2s each: ~0.6s (3 rounds of 2)
        assert elapsed < 0.8, f"Expected ~0.6s, got {elapsed:.2f}s"

    @pytest.mark.asyncio
    async def test_timeout_gives_sanitized_error(self):
        registry = {"slow": _MockConnector(delay=5.0)}
        tasks = [ConnectorTask(connector="slow", query="q", lineage_id="l1")]
        config = ConnectorExecutionConfig(timeout_seconds=0.1)
        executor = AsyncConnectorExecutor(config)
        results = await executor.execute_batch(tasks, registry)
        assert len(results) == 1
        assert results[0].error is not None
        assert "timeout" in results[0].error.lower()

    @pytest.mark.asyncio
    async def test_lineage_preserved(self):
        registry = {"mock": _MockConnector()}
        tasks = [ConnectorTask(connector="mock", query="q", lineage_id="l_001", run_id="r_001")]
        executor = AsyncConnectorExecutor()
        results = await executor.execute_batch(tasks, registry)
        assert results[0].lineage_id == "l_001"
        for src in results[0].sources:
            assert src.metadata.run_id == "r_001"
            assert src.metadata.query_lineage_id == "l_001"
            assert src.metadata.discovered_by_query == "q"

    @pytest.mark.asyncio
    async def test_synthetic_flag_preserved(self):
        registry = {"mock": _MockConnector()}
        tasks = [ConnectorTask(connector="mock", query="q", lineage_id="l1", synthetic=True)]
        executor = AsyncConnectorExecutor()
        results = await executor.execute_batch(tasks, registry)
        assert results[0].synthetic is True

    @pytest.mark.asyncio
    async def test_empty_tasks(self):
        executor = AsyncConnectorExecutor()
        results = await executor.execute_batch([], {})
        assert results == []

    @pytest.mark.asyncio
    async def test_connector_not_in_registry(self):
        tasks = [ConnectorTask(connector="nonexistent", query="q", lineage_id="l1")]
        executor = AsyncConnectorExecutor()
        results = await executor.execute_batch(tasks, {})
        assert len(results) == 1
        assert results[0].error is not None
        assert "no connector" in results[0].error.lower()

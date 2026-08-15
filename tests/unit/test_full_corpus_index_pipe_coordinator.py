from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

try:
    from app.services.full_corpus_index_pipe_coordinator import (
        FullCorpusIndexPipeCoordinator,
    )
except ModuleNotFoundError:
    FullCorpusIndexPipeCoordinator = None


class SessionContext:
    async def __aenter__(self):
        return object()

    async def __aexit__(self, *_args):
        return None


@pytest.mark.asyncio
async def test_process_once_claims_and_executes_one_parent():
    assert FullCorpusIndexPipeCoordinator is not None
    repository = SimpleNamespace(
        claim_next_full_corpus_index_pipe_job=AsyncMock(
            return_value=SimpleNamespace(id=7)
        )
    )
    execute = AsyncMock()
    coordinator = FullCorpusIndexPipeCoordinator(
        session_factory=SessionContext,
        repository=repository,
        executor=execute,
    )

    assert await coordinator.process_once() is True
    execute.assert_awaited_once_with(7)


@pytest.mark.asyncio
async def test_process_once_reports_empty_queue_without_execution():
    assert FullCorpusIndexPipeCoordinator is not None
    repository = SimpleNamespace(
        claim_next_full_corpus_index_pipe_job=AsyncMock(return_value=None)
    )
    execute = AsyncMock()
    coordinator = FullCorpusIndexPipeCoordinator(
        session_factory=SessionContext,
        repository=repository,
        executor=execute,
    )

    assert await coordinator.process_once() is False
    execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_run_loop_retries_after_executor_cleanup_failure(monkeypatch):
    repository = SimpleNamespace(
        claim_next_full_corpus_index_pipe_job=AsyncMock(
            return_value=SimpleNamespace(id=7)
        )
    )
    coordinator = FullCorpusIndexPipeCoordinator(
        session_factory=SessionContext,
        repository=repository,
        executor=AsyncMock(),
    )
    attempts = 0

    async def execute(_job_id):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise RuntimeError("artifact delete failed")
        coordinator._stopping = True

    coordinator._executor = execute
    sleep = AsyncMock()
    monkeypatch.setattr(
        "app.services.full_corpus_index_pipe_coordinator.asyncio.sleep",
        sleep,
    )

    await coordinator._run_loop()

    assert attempts == 2
    sleep.assert_awaited_once_with(1)

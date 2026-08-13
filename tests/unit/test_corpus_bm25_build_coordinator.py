from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.services.corpus_bm25_build_coordinator import CorpusBm25BuildCoordinator


class SessionContext:
    async def __aenter__(self):
        return object()

    async def __aexit__(self, *_args):
        return None


@pytest.mark.asyncio
async def test_process_once_claims_and_executes_one_job():
    repository = SimpleNamespace(
        claim_next_corpus_bm25_build_job=AsyncMock(return_value=SimpleNamespace(id=7))
    )
    execute = AsyncMock()
    coordinator = CorpusBm25BuildCoordinator(
        session_factory=SessionContext,
        repository=repository,
        executor=execute,
    )

    assert await coordinator.process_once() is True
    execute.assert_awaited_once()

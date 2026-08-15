import asyncio
import logging
from collections.abc import Callable
from typing import Any

from app.db.db import AsyncSessionLocal
from app.repositories import full_corpus_index_pipe_jobs_repo
from app.services.full_corpus_index_pipe_job import run_full_corpus_index_pipe_job_srvc
from app.services.helpers import _persisted_id


logger = logging.getLogger(__name__)


class FullCorpusIndexPipeCoordinator:
    """Single application-owned worker for durable full-pipeline parents."""

    def __init__(
        self,
        *,
        session_factory: Callable[[], Any] = AsyncSessionLocal,
        repository=full_corpus_index_pipe_jobs_repo,
        executor=run_full_corpus_index_pipe_job_srvc,
    ):
        self._session_factory = session_factory
        self._repository = repository
        self._executor = executor
        self._wake_event = asyncio.Event()
        self._stopping = False
        self._worker: asyncio.Task[None] | None = None

    async def start(self) -> asyncio.Task[None]:
        if self._worker is None or self._worker.done():
            self._stopping = False
            self._worker = asyncio.create_task(
                self._run_loop(),
                name="full-corpus-index-pipe-coordinator",
            )
        return self._worker

    async def stop(self) -> None:
        if self._worker is None:
            return
        self._stopping = True
        self._wake_event.set()
        await self._worker
        self._worker = None

    def wake(self) -> None:
        self._wake_event.set()

    async def process_once(self) -> bool:
        async with self._session_factory() as session:
            job = await self._repository.claim_next_full_corpus_index_pipe_job(
                session
            )
            if job is None:
                return False
            job_id = _persisted_id(job.id, "Full corpus index pipe job")
        await self._executor(job_id)
        return True

    async def _run_loop(self) -> None:
        while not self._stopping:
            self._wake_event.clear()
            try:
                processed = await self.process_once()
            except Exception:
                # Rollback state is durable. Avoid killing the worker or
                # spinning tightly when external artifact cleanup is down.
                logger.exception("Full corpus index pipe execution failed")
                if not self._stopping:
                    await asyncio.sleep(1)
                continue
            if not processed and not self._stopping:
                await self._wake_event.wait()


coordinator = FullCorpusIndexPipeCoordinator()


async def startup_full_corpus_index_pipe_coordinator_srvc() -> asyncio.Task[None]:
    """
    Startup the full corpus index pipe coordinator service.

    Returns:
        An asyncio.Task representing the running coordinator.
    """
    return await coordinator.start()


async def shutdown_full_corpus_index_pipe_coordinator_srvc() -> None:
    """
    Shutdown the full corpus index pipe coordinator service.

    Returns:
        None.
    """
    await coordinator.stop()


def wake_full_corpus_index_pipe_coordinator() -> None:
    """
    Wake the full corpus index pipe coordinator service.

    Returns:
        None.
    """
    coordinator.wake()

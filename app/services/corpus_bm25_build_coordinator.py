import asyncio
from collections.abc import Callable
from typing import Any

from app.db.db import AsyncSessionLocal
from app.repositories import corpus_bm25_build_jobs_repo
from app.services.corpus_bm25_build_jobs_service import execute_corpus_bm25_build_job_srvc
from app.services.helpers import _persisted_id


class CorpusBm25BuildCoordinator:
    """
    Coordinator for managing BM25 build jobs for corpora.

    This class handles the lifecycle of BM25 build jobs, including claiming,
    executing, and coordinating the jobs asynchronously.
    """
    def __init__(self, *, session_factory: Callable[[], Any] = AsyncSessionLocal, repository=corpus_bm25_build_jobs_repo, executor=execute_corpus_bm25_build_job_srvc):
        self._session_factory = session_factory
        self._repository = repository
        self._executor = executor
        self._wake_event = asyncio.Event()
        self._stopping = False
        self._worker: asyncio.Task[None] | None = None

    async def start(self) -> asyncio.Task[None]:
        if self._worker is None or self._worker.done():
            self._stopping = False
            self._worker = asyncio.create_task(self._run_loop(), name="corpus-bm25-build-coordinator")
        return self._worker

    async def stop(self) -> None:
        if self._worker is None:
            return
        self._stopping = True
        self._wake_event.set()
        await self._worker
        self._worker = None

    def wake(self) -> None:
        """
        Wake the coordinator to process jobs.
        """
        self._wake_event.set()

    async def process_once(self) -> bool:
        """
        Process the next available BM25 build job once.

        Returns:
            bool: True if a job was processed, False otherwise.
        """
        async with self._session_factory() as session:
            job = await self._repository.claim_next_corpus_bm25_build_job(session)
            if job is None:
                return False
            await self._executor(_persisted_id(job.id, "BM25 build job"), session)
            return True

    async def _run_loop(self) -> None:
        """
        Run the coordinator loop to continuously process BM25 build jobs.

        This loop will keep running until the coordinator is stopped.
        """
        while not self._stopping:
            self._wake_event.clear()
            if not await self.process_once() and not self._stopping:
                await self._wake_event.wait()

# Instantiate the coordinator for use in the application
coordinator = CorpusBm25BuildCoordinator()


async def startup_corpus_bm25_build_coordinator_srvc() -> asyncio.Task[None]:
    """
    Start the corpus BM25 build coordinator service.

    Returns:
        asyncio.Task[None]: The task running the coordinator loop.
    Raises:
        Exception: If an error occurs during startup.
    """
    try:
        return await coordinator.start()
    except Exception as e:
        # Handle any exceptions that occur during startup
        print(f"Error starting corpus BM25 build coordinator: {e}")
        raise


async def shutdown_corpus_bm25_build_coordinator_srvc() -> None:
    """
    Shutdown the corpus BM25 build coordinator service.

    Returns:
        None
    Raises:
        Exception: If an error occurs during shutdown.
    """
    try:
        await coordinator.stop()
    except Exception as e:
        # Handle any exceptions that occur during shutdown
        print(f"Error shutting down corpus BM25 build coordinator: {e}")
        raise


def wake_corpus_bm25_build_coordinator() -> None:
    """
    Wake the corpus BM25 build coordinator service.

    Returns:
        None
    """
    coordinator.wake()

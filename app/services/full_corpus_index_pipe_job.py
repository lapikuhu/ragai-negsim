from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.airag.embeddings.embeddings import choose_embedding_model, get_embedding_model_info
from app.airag.vector_stores.vector_stores import (
    delete_vectors_from_vector_store,
    store_docs_to_vector_store,
)
from app.db.db import AsyncSessionLocal
from app.models.corpus_indices import CorpusIndex
from app.models.full_corpus_index_pipe_jobs import FullCorpusIndexPipeJob
from app.models.simulations import Simulation
from app.repositories import (
    chunking_profiles_repo,
    corpus_indices_repo,
    corpus_repo,
    document_chunks_repo,
    indexed_chunks_repo,
    full_corpus_index_pipe_jobs_repo,
    raw_documents_repo,
    vector_stores_repo,
)
from app.schemas.corpus_indices_schemas import CorpusIndexBuildComplete, CorpusIndexCreate
from app.schemas.indexed_chunks_schemas import IndexedChunkCreate
from app.schemas.full_corpus_index_pipe_jobs_schemas import (
    FullCorpusIndexPipeJobCreate,
    FullCorpusIndexPipeJobDetail,
    FullCorpusIndexPipeJobQueued,
    FullCorpusIndexPipeJobRead,
    FullCorpusIndexPipeJobWarningRead,
)
from app.services.chunking_profile_runtime import resolve_ingestion_profile_options
from app.services.corpus_index_build_service import to_vector_documents
from app.services.ingestion_service import ingest_raw_document_srvc
from app.services import simulations_service
from app.repositories.indexed_chunks_repo import bulk_create_indexed_chunks


NON_TERMINAL_SIMULATION_STATUSES = {"created", "active", "paused"}
INTERRUPTED_FAILURE_DETAIL = (
    "Indexing interrupted because the application was shut down or restarted."
)
CANCELLED_FAILURE_DETAIL = "Full corpus index pipe job cancelled by user"
EMBEDDING_BATCH_SIZE = 25
_FULL_CORPUS_INDEX_PIPE_TASKS: dict[int, asyncio.Task[FullCorpusIndexPipeJobDetail]] = {}


@dataclass(frozen=True)
class DocumentBuildResult:
    successful_documents: int
    chunks_created: int


@dataclass(frozen=True)
class ActivationResult:
    candidate_corpus_index_id: int
    replaced_corpus_index_id: int | None

# Helpers candidate
def _utc_now() -> datetime:
    return datetime.now(timezone.utc)

# Helpers candidate
def _short_error(exc: Exception, max_length: int = 500) -> str:
    message = str(exc).strip() or exc.__class__.__name__
    if len(message) <= max_length:
        return message
    return f"{message[: max_length - 3]}..."


def _vector_namespace(corpus_index_id: int, requested_namespace: str | None) -> str:
    """
    Determine the vector namespace for a given corpus index.

    Args:
        corpus_index_id: The ID of the corpus index.
        requested_namespace: The requested namespace, if any.
    Returns:
        The determined vector namespace.
    """
    if requested_namespace is not None and requested_namespace.strip():
        return requested_namespace.strip()
    return f"corpus-index-{corpus_index_id}"


def _candidate_index_name(job: FullCorpusIndexPipeJob) -> str:
    """
    Determine the candidate index name for a given full corpus index pipe job.

    Args:
        job: The full corpus index pipe job.
    Returns:
        The candidate index name.
    """
    return f"{job.requested_index_name} [candidate job {job.id}]"


def _warning_read(warning: Any) -> FullCorpusIndexPipeJobWarningRead:
    """
    Convert a warning object into an FullCorpusIndexPipeJobWarningRead schema.

    Args:
        warning: The warning object to convert.
    Returns:
        An FullCorpusIndexPipeJobWarningRead object containing the warning data.
    """
    return FullCorpusIndexPipeJobWarningRead(
        id=getattr(warning, "id"),
        raw_document_id=getattr(warning, "raw_document_id", None),
        document_name=getattr(warning, "document_name", None),
        stage=getattr(warning, "stage"),
        message=getattr(warning, "message"),
        created_at=getattr(warning, "created_at"),
    )


def _job_read(job: Any) -> FullCorpusIndexPipeJobRead:
    """
    Convert a job object into an FullCorpusIndexPipeJobRead schema.

    Args:
        job: The job object to convert.
    Returns:
        An FullCorpusIndexPipeJobRead object containing the job data.
    """
    return FullCorpusIndexPipeJobRead(
        id=getattr(job, "id"),
        corpus_id=getattr(job, "corpus_id"),
        chunking_profile_id=getattr(job, "chunking_profile_id"),
        vector_store_id=getattr(job, "vector_store_id"),
        embedding_model=getattr(job, "embedding_model"),
        requested_index_name=getattr(job, "requested_index_name"),
        requested_vector_namespace=getattr(job, "requested_vector_namespace", None),
        status=getattr(job, "status"),
        stage=getattr(job, "stage"),
        cancel_requested=getattr(job, "cancel_requested", False),
        current_raw_document_id=getattr(job, "current_raw_document_id", None),
        current_document_name=getattr(job, "current_document_name", None),
        total_documents=getattr(job, "total_documents", 0),
        processed_documents=getattr(job, "processed_documents", 0),
        chunks_created=getattr(job, "chunks_created", 0),
        chunks_indexed=getattr(job, "chunks_indexed", 0),
        queued_at=getattr(job, "queued_at"),
        started_at=getattr(job, "started_at", None),
        completed_at=getattr(job, "completed_at", None),
        candidate_corpus_index_id=getattr(job, "candidate_corpus_index_id", None),
        replaced_corpus_index_id=getattr(job, "replaced_corpus_index_id", None),
        failure_detail=getattr(job, "failure_detail", None),
    )


async def _read_job_detail(job: Any, session: AsyncSession) -> FullCorpusIndexPipeJobDetail:
    """
    Read detailed information about an full corpus index pipe job, including warnings.
    
    Args:
        job: The job object to read details from.
        session: The database session.
    Returns:
        An FullCorpusIndexPipeJobDetail object containing the job details and warnings.
    """
    warnings = await full_corpus_index_pipe_jobs_repo.list_full_corpus_index_pipe_job_warnings(getattr(job, "id"), session)
    return FullCorpusIndexPipeJobDetail(
        **_job_read(job).model_dump(),
        warnings=[_warning_read(warning) for warning in warnings],
    )


def _cancel_live_full_corpus_index_pipe_task(job_id: int) -> bool:
    """
    Cancel a live full corpus index pipeline task if it exists and is running.
        
    Args:
        job_id: The ID of the full corpus index pipe job to cancel.
    Returns:
        True if the task was cancelled, False otherwise.
    """
    task = _FULL_CORPUS_INDEX_PIPE_TASKS.get(job_id)
    if task is None or task.done():
        return False
    task.cancel()
    return True


def _unregister_full_corpus_index_pipe_task(job_id: int, 
                                            task: asyncio.Task[FullCorpusIndexPipeJobDetail]) -> None:
    """
    Unregister a full corpus index pipe task.

    Args:
        job_id: The ID of the full corpus index pipe job.
        task: The asyncio task associated with the job.
    Returns:
        None
    """
    if _FULL_CORPUS_INDEX_PIPE_TASKS.get(job_id) is task:
        _FULL_CORPUS_INDEX_PIPE_TASKS.pop(job_id, None)


def start_full_corpus_index_pipe_job_task(job_id: int) -> asyncio.Task[FullCorpusIndexPipeJobDetail]:
    """
    Start a full corpus index pipeline job task and register it in the global 
    task registry.
    
    Args:
        job_id: The ID of the full corpus index pipe job to start.
    Returns:
        The asyncio task handling the job.
    """
    task = asyncio.create_task(run_full_corpus_index_pipe_job_srvc(job_id))
    _FULL_CORPUS_INDEX_PIPE_TASKS[job_id] = task
    task.add_done_callback(lambda current_task, current_job_id=job_id: _unregister_full_corpus_index_pipe_task(current_job_id, current_task))
    return task


async def _raise_if_cancel_requested(job: FullCorpusIndexPipeJob, session: AsyncSession) -> None:
    """
    Raise an asyncio.CancelledError if the job has a cancellation requested.

    Args:
        job: The full corpus index pipe job to check for cancellation.
        session: The database session.
    Raises:
        asyncio.CancelledError: If the job has a cancellation requested.
    """
    await session.refresh(job)
    if job.cancel_requested:
        raise asyncio.CancelledError(CANCELLED_FAILURE_DETAIL)


async def _mark_job_cancelled(
    job: FullCorpusIndexPipeJob,
    candidate_index: CorpusIndex | None,
    session: AsyncSession,
    detail: str = CANCELLED_FAILURE_DETAIL,
) -> FullCorpusIndexPipeJobDetail:
    """
    Mark the full corpus index pipe job as cancelled.

    Args:
        job: The full corpus index pipe job to mark as cancelled.
        candidate_index: The candidate corpus index associated with the job, if any.
        session: The database session.
        detail: The cancellation detail message.
    Returns:
        The detailed information of the cancelled job.
    """
    if candidate_index is not None and candidate_index.status == "building":
        try:
            await corpus_indices_repo.mark_corpus_index_cancelled(candidate_index, detail, session)
        finally:
            simulations_service.clear_negotiation_graph_cache_for_corpus_index(
                candidate_index.id
            )
    cancelled_job = await full_corpus_index_pipe_jobs_repo.mark_full_corpus_index_pipe_job_cancelled(
        job,
        session,
        detail=detail,
    )
    return await _read_job_detail(cancelled_job, session)


async def _ensure_resources_exist(job_in: FullCorpusIndexPipeJobCreate, session: AsyncSession) -> None:
    """
    Ensure that the resources required for an full corpus index pipe job exist.

    Args:
        job_in: The full corpus index pipe job creation data.
        session: The database session.
    Returns:
        None
    Raises:
        ValueError: If any of the required resources do not exist.
    """
    if await corpus_repo.get_corpus_by_id(job_in.corpus_id, session) is None:
        raise ValueError("Corpus not found")
    profile = await chunking_profiles_repo.get_chunking_profile_by_id(
        job_in.chunking_profile_id,
        session,
    )
    if profile is None:
        raise ValueError("Chunking profile not found")
    vector_store = await vector_stores_repo.get_vector_store_by_id(job_in.vector_store_id, session)
    if vector_store is None:
        raise ValueError("Vector store not found")
    embedding_info = get_embedding_model_info(job_in.embedding_model)
    if vector_store.embedding_dimensions is None:
        raise ValueError("Vector store dimensions are not set")
    if vector_store.embedding_dimensions != embedding_info["dimensionality"]:
        raise ValueError(
            "Embedding model dimensions "
            f"({embedding_info['dimensionality']}) do not match vector store dimensions "
            f"({vector_store.embedding_dimensions})"
        )
    resolve_ingestion_profile_options(profile, header_depth=2, dynamic_header_depth=False)


async def _ensure_corpus_has_raw_documents(corpus_id: int, session: AsyncSession) -> None:
    """
    Ensure that the corpus contains raw documents.

    Args:
        corpus_id: The ID of the corpus to check.
        session: The database session.
    Raises:
        ValueError: If the corpus does not contain any raw documents.
    """
    raw_document_ids = await corpus_repo.get_corpus_raw_document_ids(corpus_id, session)
    if not raw_document_ids:
        raise ValueError("Corpus does not contain any raw documents")


async def _ensure_index_name_is_available_for_request(
    job_in: FullCorpusIndexPipeJobCreate,
    session: AsyncSession,
) -> None:
    """
    Ensure that the requested index name is available for the full corpus index 
    pipeline job.

    Args:
        job_in: The full corpus index pipe job creation data.
        session: The database session.
    Raises:
        ValueError: If the index name is already in use.
    """
    existing_index = await corpus_indices_repo.get_corpus_index_by_name(
        job_in.requested_index_name,
        session,
    )
    if existing_index is None:
        return

    raise ValueError("Corpus index name already exists")


async def _ensure_vector_namespace_is_available_for_request(
    job_in: FullCorpusIndexPipeJobCreate,
    session: AsyncSession,
) -> None:
    """
    Ensure that the requested vector namespace is available for the full 
    corpus index pipeline job.

        Args:
            job_in: The full corpus index pipe job creation data.
            session: The database session.
        Raises:
            ValueError: If the vector namespace is already in use for the 
            specified vector store.
    """
    vector_namespace = job_in.requested_vector_namespace
    if vector_namespace is None or not vector_namespace.strip():
        return
    # Get corpus index by namespace and vector store ID
    existing_index = await corpus_indices_repo.get_corpus_index_by_vector_namespace(
        vector_store_id=job_in.vector_store_id,
        vector_namespace=vector_namespace.strip(),
        session=session,
    )
    if existing_index is None:
        return

    raise ValueError("Vector namespace already exists for this vector store")


async def _has_non_terminal_simulations_for_index(index_id: int, session: AsyncSession) -> bool:
    """
    Check if there are any non-terminal simulations for a given index.

    Args:
        index_id: The ID of the corpus index to check.
        session: The database session.
    Returns:
        True if there are non-terminal simulations for the index, False 
        otherwise.
    """
    result = await session.exec(
        select(Simulation.id)
        .where(
            Simulation.corpus_index_id == index_id,
            Simulation.status.in_(NON_TERMINAL_SIMULATION_STATUSES),
        )
        .limit(1)
    )
    return result.first() is not None


async def queue_full_corpus_index_pipe_job_srvc(
    job_in: FullCorpusIndexPipeJobCreate,
    session: AsyncSession,
) -> FullCorpusIndexPipeJobQueued:
    """
    Queue an full corpus index pipeline job service function.

    Args:
        job_in: The full corpus index pipe job creation data.
        session: The database session.
    Returns:
        An FullCorpusIndexPipeJobQueued object containing the queued job 
        data.
    Raises:
        ValueError: If any of the required resources do not exist or if 
        the index name is already in use.
    """
    await _ensure_resources_exist(job_in, session)
    await _ensure_corpus_has_raw_documents(job_in.corpus_id, session)
    get_embedding_model_info(job_in.embedding_model)
    await _ensure_index_name_is_available_for_request(job_in, session)
    await _ensure_vector_namespace_is_available_for_request(job_in, session)

    raw_document_ids = await corpus_repo.get_corpus_raw_document_ids(job_in.corpus_id, session)
    job = await full_corpus_index_pipe_jobs_repo.create_full_corpus_index_pipe_job(job_in, session)
    job = await full_corpus_index_pipe_jobs_repo.update_full_corpus_index_pipe_job_progress(
        job,
        session,
        total_documents=len(raw_document_ids),
    )
    return FullCorpusIndexPipeJobQueued(**_job_read(job).model_dump())


async def list_full_corpus_index_pipe_jobs_srvc(
    session: AsyncSession,
    *,
    skip: int = 0,
    limit: int = 20,
    status: str | None = None,
    corpus_id: int | None = None,
) -> list[FullCorpusIndexPipeJobRead]:
    """
    List full corpus index pipe jobs with optional filtering by status and 
    corpus ID.

    Args:
        session: The database session.
        skip: The number of records to skip for pagination.
        limit: The maximum number of records to return.
        status: Optional status to filter the full corpus index pipe jobs.
        corpus_id: Optional corpus ID to filter the full corpus index 
            pipe jobs.
    Returns:
        A list of FullCorpusIndexPipeJobRead objects matching the filters.
    """
    jobs = await full_corpus_index_pipe_jobs_repo.list_full_corpus_index_pipe_jobs(
        session,
        skip=skip,
        limit=limit,
        status=status,
        corpus_id=corpus_id,
    )
    return [FullCorpusIndexPipeJobRead(**_job_read(job).model_dump()) for job in jobs]


async def get_active_full_corpus_index_pipe_job_srvc(session: AsyncSession) -> FullCorpusIndexPipeJobDetail | None:
    """
    Get the active full corpus index pipeline job, if any.

    Args:
        session: The database session.
    Returns:
        An FullCorpusIndexPipeJobDetail object for the active job, or None if no 
        active job exists.
    """
    job = await full_corpus_index_pipe_jobs_repo.get_active_full_corpus_index_pipe_job(session)
    if job is None:
        return None
    return await _read_job_detail(job, session)


async def get_full_corpus_index_pipe_job_detail_srvc(job_id: int, 
                                                     session: AsyncSession) -> FullCorpusIndexPipeJobDetail:
    """
    Get the details of a specific full corpus index pipeline job by its ID.

    Args:
        job_id: The ID of the full corpus index pipeline job.
        session: The database session.
    Returns:
        An FullCorpusIndexPipeJobDetail object for the specified job.
    Raises:
        ValueError: If the full corpus index pipeline job is not found.
    """
    job = await full_corpus_index_pipe_jobs_repo.get_full_corpus_index_pipe_job_by_id(job_id, session)
    if job is None:
        raise ValueError("Full corpus index pipe job not found")
    return await _read_job_detail(job, session)


async def cancel_full_corpus_index_pipe_job_srvc(job_id: int, 
                                                 session: AsyncSession) -> FullCorpusIndexPipeJobDetail:
    """
    Cancel a full corpus index pipeline job by its ID.

    Args:
        job_id: The ID of the full corpus index pipeline job to cancel.
        session: The database session.
    Returns:
        An FullCorpusIndexPipeJobDetail object for the cancelled job.
    Raises:
        ValueError: If the full corpus index pipeline job is not found or if
        the job is not in a cancellable state (queued or running).
    """
    job = await full_corpus_index_pipe_jobs_repo.get_full_corpus_index_pipe_job_by_id(job_id, session)
    if job is None:
        raise ValueError("Full corpus index pipe job not found")
    if job.status not in {"queued", "running"}:
        raise ValueError("Only queued or running full corpus index pipe jobs can be cancelled")

    job = await full_corpus_index_pipe_jobs_repo.request_full_corpus_index_pipe_job_cancel(job, session)

    if job.status == "running":
        return await _read_job_detail(job, session)

    _cancel_live_full_corpus_index_pipe_task(job_id)

    candidate_index = None
    if job.candidate_corpus_index_id is not None:
        candidate_index = await corpus_indices_repo.get_corpus_index_by_id(
            job.candidate_corpus_index_id,
            session,
        )
    return await _mark_job_cancelled(job, candidate_index, session)


async def _create_candidate_index(job: FullCorpusIndexPipeJob, session: AsyncSession) -> CorpusIndex:
    """
    Create a candidate corpus index for the given full corpus index pipe job.
        Args:
            job: The full corpus index pipe job for which to create the candidate index.
            session: The database session.
        Returns:
            A CorpusIndex object representing the candidate index.
        Raises:
            ValueError: If the candidate index ID is not generated.
    """
    _, embedding_metadata = choose_embedding_model(job.embedding_model)
    candidate_index = await corpus_indices_repo.create_corpus_index(
        CorpusIndexCreate(
            name=_candidate_index_name(job),
            corpus_id=job.corpus_id,
            vector_store_id=job.vector_store_id,
            chunking_profile_id=job.chunking_profile_id,
            status="building",
            embedding_model=job.embedding_model,
            embedding_dimensions=embedding_metadata["dimensionality"],
            vector_namespace=job.requested_vector_namespace,
        ),
        session,
    )
    if candidate_index.id is None:
        raise ValueError("Candidate corpus index id was not generated")
    vector_namespace = _vector_namespace(
        candidate_index.id,
        job.requested_vector_namespace,
    )
    candidate_index = await corpus_indices_repo.set_corpus_index_build_metadata(
        candidate_index,
        vector_namespace,
        session,
    )
    job.candidate_corpus_index_id = candidate_index.id
    session.add(job)
    await session.commit()
    await session.refresh(job)
    return candidate_index


async def _process_documents(
    job: FullCorpusIndexPipeJob,
    candidate_index: CorpusIndex,
    session: AsyncSession,
) -> DocumentBuildResult:
    """
    Process the documents for the given full corpus index pipe job and 
    candidate index.

    Args:
        job: The full corpus index pipeline job for which to process documents.
        candidate_index: The candidate corpus index.
        session: The database session.
    Returns:
        A DocumentBuildResult object containing the results of the 
        document processing.
    Raises:
        ValueError: If the chunking profile is not found or if any raw 
        document is not found during processing.
    """
    raw_document_ids = await corpus_repo.get_corpus_raw_document_ids(job.corpus_id, session)
    chunking_profile = await chunking_profiles_repo.get_chunking_profile_by_id(
        job.chunking_profile_id,
        session,
    )
    if chunking_profile is None:
        raise ValueError("Chunking profile not found")

    chunking_embeddings = None
    if chunking_profile.strategy in {"semantic", "hybrid"}:
        chunking_embeddings, _ = choose_embedding_model(job.embedding_model)

    successful_documents = 0
    chunks_created = 0
    for processed_index, raw_document_id in enumerate(raw_document_ids, start=1):
        await _raise_if_cancel_requested(job, session)
        raw_document = await raw_documents_repo.get_raw_document_by_id(raw_document_id, session)
        if raw_document is None:
            await full_corpus_index_pipe_jobs_repo.create_full_corpus_index_pipe_job_warning(
                full_corpus_index_pipe_job_id=job.id,
                raw_document_id=raw_document_id,
                stage="converting",
                message=f"Skipped raw document {raw_document_id}: linked document was not found",
                session=session,
            )
            continue

        async def progress_callback(stage: str) -> None:
            """
            Progress callback for the document processing stage.

            Args:
                stage (str): The current stage of document processing.
            Returns:
                None
            """
            await _raise_if_cancel_requested(job, session)
            await full_corpus_index_pipe_jobs_repo.update_full_corpus_index_pipe_job_progress(
                job,
                session,
                stage=stage,
                current_raw_document_id=raw_document_id,
                current_document_name=raw_document.name,
                processed_documents=processed_index - 1,
            )

        try:
            ingest_result = await ingest_raw_document_srvc(
                raw_document=raw_document,
                chunking_profile=chunking_profile,
                session=session,
                options=resolve_ingestion_profile_options(
                    chunking_profile,
                    header_depth=2,
                    dynamic_header_depth=False,
                ),
                full_corpus_index_pipe_job_id=job.id,
                embeddings=chunking_embeddings,
                progress_callback=progress_callback,
            )
        except Exception as exc:
            await full_corpus_index_pipe_jobs_repo.create_full_corpus_index_pipe_job_warning(
                full_corpus_index_pipe_job_id=job.id,
                raw_document_id=raw_document_id,
                document_name=raw_document.name,
                stage="converting",
                message=_short_error(exc),
                session=session,
            )
        else:
            successful_documents += 1
            chunks_created += ingest_result.chunks_created

        await _raise_if_cancel_requested(job, session)
        await full_corpus_index_pipe_jobs_repo.update_full_corpus_index_pipe_job_progress(
            job,
            session,
            stage="chunking",
            current_raw_document_id=raw_document_id,
            current_document_name=raw_document.name,
            processed_documents=processed_index,
            chunks_created=chunks_created,
        )
        await _raise_if_cancel_requested(job, session)

    await full_corpus_index_pipe_jobs_repo.update_full_corpus_index_pipe_job_progress(
        job,
        session,
        stage="embedding",
        current_raw_document_id=None,
        current_document_name=None,
        processed_documents=len(raw_document_ids),
        chunks_created=chunks_created,
    )
    return DocumentBuildResult(
        successful_documents=successful_documents,
        chunks_created=chunks_created,
    )


async def _embed_candidate(
    job: FullCorpusIndexPipeJob,
    candidate_index: CorpusIndex,
    session: AsyncSession,
) -> int:
    """
    Embed the candidate corpus index for the given full corpus index pipeline 
    job.

    Args:
        job: The full corpus index pipe job for which to embed the candidate index.
        candidate_index: The candidate corpus index.
        session: The database session.
    Returns:
        The number of chunks indexed.
    Raises:
        ValueError: If the candidate index ID is not generated or if 
        the vector store is not found.
    """
    candidate_index_id = candidate_index.id
    if candidate_index_id is None:
        raise ValueError("Candidate corpus index id was not generated")

    vector_store = await vector_stores_repo.get_vector_store_by_id(job.vector_store_id, session)
    if vector_store is None:
        raise ValueError("Vector store not found")

    chunks = await document_chunks_repo.list_document_chunks_for_job(job.id, session)
    if not chunks:
        raise ValueError("No documents produced chunks")

    embedding_model, embedding_metadata = choose_embedding_model(job.embedding_model)
    documents, vector_refs = to_vector_documents(
        chunks=chunks,
        corpus_id=job.corpus_id,
        corpus_index_id=candidate_index_id,
        chunking_profile_id=job.chunking_profile_id,
    )
    total_indexed = 0
    for offset in range(0, len(documents), EMBEDDING_BATCH_SIZE):
        await _raise_if_cancel_requested(job, session)
        document_batch = documents[offset : offset + EMBEDDING_BATCH_SIZE]
        vector_ref_batch = vector_refs[offset : offset + EMBEDDING_BATCH_SIZE]
        vector_ids = [vector_ref.external_vector_id for vector_ref in vector_ref_batch]
        stored_vector_ids = await store_docs_to_vector_store(
            docs=document_batch,
            embedding_model=embedding_model,
            backend=vector_store.backend,
            ids=vector_ids,
            embedding_dimensions=embedding_metadata["dimensionality"],
            collection_name=vector_store.collection_name,
            path=vector_store.path,
            table_name=vector_store.table_name,
        )
        indexed_chunks_in = [
            IndexedChunkCreate(
                corpus_index_id=candidate_index_id,
                document_chunk_id=vector_ref.document_chunk_id,
                external_vector_id=stored_vector_id,
            )
            for vector_ref, stored_vector_id in zip(vector_ref_batch, stored_vector_ids, strict=True)
        ]
        await bulk_create_indexed_chunks(indexed_chunks_in, session)
        total_indexed += len(indexed_chunks_in)
        await full_corpus_index_pipe_jobs_repo.update_full_corpus_index_pipe_job_progress(
            job,
            session,
            stage="embedding",
            chunks_indexed=total_indexed,
        )
    await corpus_indices_repo.mark_corpus_index_built(
        candidate_index,
        CorpusIndexBuildComplete(
            status="built",
            built_at=_utc_now(),
            embedding_dimensions=embedding_metadata["dimensionality"],
            vector_namespace=_vector_namespace(
                candidate_index_id,
                job.requested_vector_namespace,
            ),
        ),
        session,
    )
    await full_corpus_index_pipe_jobs_repo.update_full_corpus_index_pipe_job_progress(
        job,
        session,
        stage="embedding",
        chunks_indexed=total_indexed,
    )
    return total_indexed


async def _activate_candidate_index(
    job: FullCorpusIndexPipeJob,
    candidate_index: CorpusIndex,
    session: AsyncSession,
) -> ActivationResult:
    """
    Activate the candidate corpus index for the given full corpus index 
    pipeline job.

    Args:
        job: The full corpus index pipe job for which to activate the candidate index.
        candidate_index: The candidate corpus index.
        session: The database session.
    Returns:
        An ActivationResult object containing the IDs of the activated 
        and replaced corpus indices.
    """
    candidate_index, replaced_index = await corpus_indices_repo.activate_candidate_index(
        candidate_index=candidate_index,
        requested_name=job.requested_index_name,
        session=session,
    )
    return ActivationResult(
        candidate_corpus_index_id=candidate_index.id,
        replaced_corpus_index_id=replaced_index.id if replaced_index is not None else None,
    )


async def _cleanup_retired_index(
    replaced_corpus_index_id: int | None,
    session: AsyncSession,
) -> None:
    """
    Cleanup the retired corpus index by deleting its indexed chunks and vectors.

    Args:
        replaced_corpus_index_id: The ID of the replaced corpus index.
        session: The database session.
    Returns:
        None
    Raises:
        ValueError: If the vector store is not found.
    """
    if replaced_corpus_index_id is None:
        return

    try:
        replaced_index = await corpus_indices_repo.get_corpus_index_by_id(
            replaced_corpus_index_id,
            session,
        )
        if replaced_index is None:
            return

        vector_store = await vector_stores_repo.get_vector_store_by_id(
            replaced_index.vector_store_id,
            session,
        )
        if vector_store is None:
            raise ValueError("Vector store not found")

        indexed_chunks = await indexed_chunks_repo.get_indexed_chunks_by_corpus_index_id(
            replaced_corpus_index_id,
            session,
            skip=0,
            limit=100000,
        )
        vector_ids = [
            indexed_chunk.external_vector_id
            for indexed_chunk in indexed_chunks
            if indexed_chunk.external_vector_id is not None
        ]
        if vector_ids:
            await delete_vectors_from_vector_store(
                backend=vector_store.backend,
                vector_ids=vector_ids,
                collection_name=vector_store.collection_name,
                path=vector_store.path,
                table_name=vector_store.table_name,
            )
        await indexed_chunks_repo.delete_indexed_chunks_by_corpus_index_id_force(
            replaced_corpus_index_id,
            session,
        )
    finally:
        simulations_service.clear_negotiation_graph_cache_for_corpus_index(
            replaced_corpus_index_id
        )


async def _fail_job_and_candidate(
    job: FullCorpusIndexPipeJob,
    candidate_index: CorpusIndex | None,
    session: AsyncSession,
    detail: str,
) -> FullCorpusIndexPipeJobDetail:
    """
    Fail the full corpus index pipe job and the candidate corpus index, if it exists.

    Args:
        job: The full corpus index pipe job to fail.
        candidate_index: The candidate corpus index to fail, if it exists.
        session: The database session.
        detail: The detail of the failure.
    Returns:
        An FullCorpusIndexPipeJobDetail object containing the failed job details.
    Raises:
        ValueError: If the candidate index is not None and the candidate
        index status is not "building".
    """
    if candidate_index is not None and candidate_index.status == "building":
        try:
            await corpus_indices_repo.mark_corpus_index_failed(candidate_index, detail, session)
        finally:
            simulations_service.clear_negotiation_graph_cache_for_corpus_index(
                candidate_index.id
            )
    failed_job = await full_corpus_index_pipe_jobs_repo.mark_full_corpus_index_pipe_job_failed(job, detail, session)
    return await _read_job_detail(failed_job, session)


async def run_full_corpus_index_pipe_job_srvc(job_id: int) -> FullCorpusIndexPipeJobDetail:
    """
    Run the full corpus index pipe job with the given ID, processing its documents, 
    embedding them, and updating the job status accordingly.
    
    Args:
        job_id: The ID of the full corpus index pipe job to run.
    Returns:
        An FullCorpusIndexPipeJobDetail object containing the details of the
        completed or failed full corpus index pipe job.
    Raises:
        ValueError: If the full corpus index pipe job is not found or if any step of
        the indexing process fails.
    """
    async with AsyncSessionLocal() as session:
        job = await full_corpus_index_pipe_jobs_repo.get_full_corpus_index_pipe_job_by_id(job_id, session)
        if job is None:
            raise ValueError("Full corpus index pipe job not found")
        if job.status == "cancelled":
            return await _read_job_detail(job, session)

        candidate_index: CorpusIndex | None = None
        try:
            await _raise_if_cancel_requested(job, session)
            job = await full_corpus_index_pipe_jobs_repo.mark_full_corpus_index_pipe_job_running(job, session)
            await _raise_if_cancel_requested(job, session)
            candidate_index = await _create_candidate_index(job, session)
            await _raise_if_cancel_requested(job, session)
            build_result = await _process_documents(job, candidate_index, session)
            if build_result.successful_documents == 0:
                return await _fail_job_and_candidate(
                    job,
                    candidate_index,
                    session,
                    "No documents produced chunks",
                )

            await _embed_candidate(job, candidate_index, session)
            await _raise_if_cancel_requested(job, session)
            await full_corpus_index_pipe_jobs_repo.update_full_corpus_index_pipe_job_progress(job, session, stage="finalizing")
            await _raise_if_cancel_requested(job, session)
            activation = await _activate_candidate_index(job, candidate_index, session)

            status = "completed"
            try:
                await _cleanup_retired_index(activation.replaced_corpus_index_id, session)
            except Exception as cleanup_exc:
                await full_corpus_index_pipe_jobs_repo.create_full_corpus_index_pipe_job_warning(
                    full_corpus_index_pipe_job_id=job.id,
                    stage="finalizing",
                    message=f"Cleanup warning: {_short_error(cleanup_exc)}",
                    session=session,
                )
                status = "completed_with_warnings"

            if status == "completed":
                warnings = await full_corpus_index_pipe_jobs_repo.list_full_corpus_index_pipe_job_warnings(job.id, session)
                if warnings:
                    status = "completed_with_warnings"

            completed_job = await full_corpus_index_pipe_jobs_repo.mark_full_corpus_index_pipe_job_completed(
                job,
                session,
                status=status,
                candidate_corpus_index_id=activation.candidate_corpus_index_id,
                replaced_corpus_index_id=activation.replaced_corpus_index_id,
            )
            return await _read_job_detail(completed_job, session)
        except asyncio.CancelledError as exc:
            detail = str(exc).strip() or CANCELLED_FAILURE_DETAIL
            return await _mark_job_cancelled(job, candidate_index, session, detail)
        except Exception as exc:
            return await _fail_job_and_candidate(
                job,
                candidate_index,
                session,
                _short_error(exc),
            )


async def fail_interrupted_full_corpus_index_pipe_jobs_srvc() -> None:
    """
    Fail any full corpus index pipe jobs that were interrupted, marking 
    them as failed and cleaning up any associated candidate indices.
    
    Args:    
        None
    Returns: 
        None
    """
    async with AsyncSessionLocal() as session:
        try:
            interrupted_jobs = await full_corpus_index_pipe_jobs_repo.list_interrupted_full_corpus_index_pipe_jobs(session)
        except Exception:
            return
        for job in interrupted_jobs:
            candidate_index = None
            if job.candidate_corpus_index_id is not None:
                candidate_index = await corpus_indices_repo.get_corpus_index_by_id(
                    job.candidate_corpus_index_id,
                    session,
                )
            await _fail_job_and_candidate(
                job,
                candidate_index,
                session,
                INTERRUPTED_FAILURE_DETAIL,
            )

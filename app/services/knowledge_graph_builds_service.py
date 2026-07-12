import asyncio
import logging
from collections import defaultdict
from uuid import uuid4

from sqlmodel.ext.asyncio.session import AsyncSession

from app.airag.knowledge_graph.k_graph import (
    build_graph_text_nodes,
    build_property_graph_index,
    create_graph_embedding_model,
    create_graph_llm,
    create_kg_extractors,
)
from app.airag.knowledge_graph.connection import (
    describe_neo4j_error,
    resolve_neo4j_database,
    resolve_neo4j_uri,
)
from app.airag.knowledge_graph.scoped_store import ScopedNeo4jPropertyGraphStore
from app.core.config import settings
from app.db.db import AsyncSessionLocal
from app.repositories import (
    corpus_indices_repo,
    document_chunks_repo,
    knowledge_graph_build_jobs_repo,
    knowledge_graph_indices_repo,
)
from app.repositories.helpers import commit_and_refresh, utc_now
from app.schemas.knowledge_graph_build_jobs_schemas import (
    KnowledgeGraphBuildJobCreate,
    KnowledgeGraphBuildJobRead,
)


_GRAPH_BUILD_TASKS: dict[int, asyncio.Task[KnowledgeGraphBuildJobRead]] = {}
logger = logging.getLogger(__name__)
INTERRUPTED_FAILURE_DETAIL = (
    "Knowledge graph build interrupted because the application was shut down "
    "or restarted."
)


class KnowledgeGraphBuildCancelled(Exception):
    pass


def _require_persisted_graph(stats: dict[str, int]) -> None:
    if stats["node_count"] == 0:
        raise ValueError(
            "Neo4j persistence produced an empty graph "
            f"(nodes={stats['node_count']}, "
            f"relationships={stats['relationship_count']})"
        )


async def _raise_if_cancel_requested(job, session: AsyncSession) -> None:
    """
    Check if a knowledge graph build job has a cancel request.
    Args:
        job: The knowledge graph build job.
        session (AsyncSession): The database session.
    Raises:
        KnowledgeGraphBuildCancelled: If the build job has a cancel request.
    """
    await session.refresh(job)
    if job.cancel_requested:
        raise KnowledgeGraphBuildCancelled("Knowledge graph build cancelled")


def _job_read(job) -> KnowledgeGraphBuildJobRead:
    """
    Return a KnowledgeGraphBuildJobRead instance from a KnowledgeGraphBuildJob 
    model.
    Args:
        job: The KnowledgeGraphBuildJob model instance.
    Returns:
        A KnowledgeGraphBuildJobRead instance with the same data as the model.
    """
    values = job.model_dump() if hasattr(job, "model_dump") else vars(job)
    return KnowledgeGraphBuildJobRead(**values)

# Helper candidate
def _new_generation() -> str:
    """
    Generate a new unique generation identifier for a knowledge graph build.
    Returns:
        A unique string identifier for the new generation.
    """
    return uuid4().hex


def _document_label(chunk) -> str:
    """
    Return the label for a document chunk.

    Args:
        chunk: The document chunk.
    Returns:
        str: The label for the document chunk.
    """
    document = chunk.raw_document
    if document.document_title:
        return document.document_title
    return document.source_path.replace("\\", "/").rsplit("/", 1)[-1]


def _create_scoped_store(graph_id: int, generation: str):
    """
    Create a scoped Neo4j property graph store for a specific graph and 
    generation.
    Args:
        graph_id (int): The ID of the knowledge graph.
        generation (str): The generation identifier.
    Returns:
        ScopedNeo4jPropertyGraphStore: The scoped graph store instance.
    """
    return ScopedNeo4jPropertyGraphStore(
        graph_id=graph_id,
        generation=generation,
        username=settings.NEO4J_USERNAME,
        password=settings.NEO4J_PASSWORD,
        url=resolve_neo4j_uri(settings.NEO4J_URI),
        database=resolve_neo4j_database(settings.NEO4J_DATABASE),
    )


async def queue_knowledge_graph_build_srvc(
    graph_id: int,
    session: AsyncSession,
    *,
    rebuild: bool = False,
) -> KnowledgeGraphBuildJobRead:
    """
    Queue a knowledge graph build job for a specific knowledge graph index.
    Args:
        graph_id (int): The ID of the knowledge graph index to build.
        session (AsyncSession): The database session.
        rebuild (bool): If True, allows rebuilding an existing graph.
    Returns:
        KnowledgeGraphBuildJobRead: The queued knowledge graph build job.
    Raises:
        ValueError: If the knowledge graph is not found, if it is already 
        built and rebuild is False, or if the associated corpus index is 
        not built.
    """
    graph = await knowledge_graph_indices_repo.get_knowledge_graph_index_by_id(
        graph_id,
        session,
    )
    if graph is None:
        raise ValueError("Knowledge graph not found")
    if rebuild:
        await knowledge_graph_indices_repo.ensure_knowledge_graph_mutable(
            graph,
            session,
        )
    elif graph.status == "built":
        raise ValueError("Knowledge graph is already built; use rebuild")

    corpus_index = await corpus_indices_repo.get_corpus_index_by_id(
        graph.corpus_index_id,
        session,
    )
    if corpus_index is None:
        raise ValueError("Corpus index not found")
    if corpus_index.status != "built":
        raise ValueError("Knowledge graph requires a built corpus index")

    chunks = await document_chunks_repo.list_document_chunks_for_corpus_index(
        graph.corpus_index_id,
        session,
    )
    chunk_ids = [chunk.id for chunk in chunks if chunk.id is not None]
    if not chunk_ids:
        raise ValueError("Corpus index has no indexed chunks")

    job = await knowledge_graph_build_jobs_repo.create_knowledge_graph_build_job(
        KnowledgeGraphBuildJobCreate(
            knowledge_graph_index_id=graph.id,
            build_config_snapshot=dict(graph.build_config),
            chunk_ids_snapshot=chunk_ids,
            candidate_generation=_new_generation(),
            total_documents=len({chunk.raw_document_id for chunk in chunks}),
            total_chunks=len(chunk_ids),
        ),
        session,
    )
    return _job_read(job)


def start_knowledge_graph_build_task(
    job_id: int,
) -> asyncio.Task[KnowledgeGraphBuildJobRead]:
    """
    Start a knowledge graph build task for a specific job ID.
    Args:
        job_id (int): The ID of the knowledge graph build job.
    Returns:
        asyncio.Task[KnowledgeGraphBuildJobRead]: The asyncio task for the 
        build job.
    """
    existing = _GRAPH_BUILD_TASKS.get(job_id)
    if existing is not None and not existing.done():
        return existing
    task = asyncio.create_task(run_knowledge_graph_build_srvc(job_id))
    _GRAPH_BUILD_TASKS[job_id] = task
    task.add_done_callback(lambda _: _GRAPH_BUILD_TASKS.pop(job_id, None))
    return task


async def _load_build_records(job_id: int, session: AsyncSession):
    """
    Load the knowledge graph build job and its associated knowledge graph index.
    Args:
        job_id (int): The ID of the knowledge graph build job.
        session (AsyncSession): The database session.
    Returns:
        Tuple[KnowledgeGraphBuildJob, KnowledgeGraphIndex]: The build job 
        and its associated knowledge graph index.
    Raises:
        ValueError: If the build job or knowledge graph index is not found.
    """
    job = (
        await knowledge_graph_build_jobs_repo.get_knowledge_graph_build_job_by_id(
            job_id,
            session,
        )
    )
    if job is None:
        raise ValueError("Knowledge graph build job not found")
    graph = await knowledge_graph_indices_repo.get_knowledge_graph_index_by_id(
        job.knowledge_graph_index_id,
        session,
    )
    if graph is None:
        raise ValueError("Knowledge graph not found")
    return job, graph


async def run_knowledge_graph_build_srvc(
    job_id: int,
) -> KnowledgeGraphBuildJobRead:
    """
    Run a knowledge graph build job for a specific job ID.
    Args:
        job_id (int): The ID of the knowledge graph build job.
    Returns:
        KnowledgeGraphBuildJobRead: The completed knowledge graph build job.
    Raises:
        ValueError: If the build job or knowledge graph index is not found,
        or if the build job is not queued.
    """
    candidate_store = None
    persistence_stats: dict[str, int] | None = None
    async with AsyncSessionLocal() as session:
        job, graph = await _load_build_records(job_id, session)
        if job.status != "queued":
            raise ValueError("Knowledge graph build job is not queued")
        log_context = {
            "job_id": job.id,
            "graph_id": graph.id,
            "generation": job.candidate_generation,
        }
        logger.info(
            "Knowledge graph build starting | %s | chunks=%d | config=%s",
            log_context,
            len(job.chunk_ids_snapshot),
            {
                "llm_provider": job.build_config_snapshot.get("llm_provider"),
                "llm_model": job.build_config_snapshot.get("llm_model"),
                "embedding_provider": job.build_config_snapshot.get(
                    "embedding_provider"
                ),
                "embedding_model": job.build_config_snapshot.get(
                    "embedding_model"
                ),
                "extractors": job.build_config_snapshot.get("extractors"),
                "neo4j_database": resolve_neo4j_database(
                    settings.NEO4J_DATABASE
                ),
            },
        )
        try:
            await _raise_if_cancel_requested(job, session)
            await knowledge_graph_indices_repo.ensure_knowledge_graph_mutable(
                graph,
                session,
            )
            job = (
                await knowledge_graph_build_jobs_repo.mark_knowledge_graph_build_job_running(
                    job,
                    session,
                )
            )
            graph.status = "building"
            graph.latest_build_error = None
            graph.last_updated = utc_now()
            await commit_and_refresh(session, graph)
            await _raise_if_cancel_requested(job, session)

            chunks = await document_chunks_repo.list_document_chunks_for_corpus_index(
                graph.corpus_index_id,
                session,
            )
            chunks_by_id = {
                chunk.id: chunk for chunk in chunks if chunk.id is not None
            }
            if set(chunks_by_id) != set(job.chunk_ids_snapshot):
                raise ValueError(
                    "Corpus index chunks changed after the graph build was queued"
                )
            logger.info(
                "Knowledge graph chunks loaded | %s | loaded=%d",
                log_context,
                len(chunks_by_id),
            )

            chunks_by_document = defaultdict(list)
            for chunk_id in job.chunk_ids_snapshot:
                chunk = chunks_by_id[chunk_id]
                chunks_by_document[chunk.raw_document_id].append(chunk)
            logger.info(
                "Knowledge graph document batches prepared | %s | documents=%d | "
                "chunks=%d",
                log_context,
                len(chunks_by_document),
                len(job.chunk_ids_snapshot),
            )
            llm = create_graph_llm(job.build_config_snapshot)
            embedding_model = create_graph_embedding_model(
                job.build_config_snapshot
            )
            extractors = create_kg_extractors(
                job.build_config_snapshot,
                llm=llm,
            )
            candidate_store = _create_scoped_store(
                graph.id,
                job.candidate_generation,
            )
            logger.info(
                "Knowledge graph extraction and persistence started | %s | "
                "extractors=%s",
                log_context,
                [extractor.class_name() for extractor in extractors],
            )
            for raw_document_id, document_chunks in chunks_by_document.items():
                await _raise_if_cancel_requested(job, session)
                job = await knowledge_graph_build_jobs_repo.update_knowledge_graph_build_job(
                    job,
                    session,
                    stage="extracting",
                    current_raw_document_id=raw_document_id,
                    current_document_label=_document_label(document_chunks[0]),
                )
                nodes = build_graph_text_nodes(
                    document_chunks,
                    graph_id=graph.id,
                    generation=job.candidate_generation,
                    corpus_index_id=graph.corpus_index_id,
                )
                job = await knowledge_graph_build_jobs_repo.update_knowledge_graph_build_job(
                    job,
                    session,
                    stage="indexing",
                )
                await asyncio.to_thread(
                    build_property_graph_index,
                    nodes=nodes,
                    graph_store=candidate_store,
                    llm=llm,
                    embedding_model=embedding_model,
                    kg_extractors=extractors,
                )
                job = await knowledge_graph_build_jobs_repo.update_knowledge_graph_build_job(
                    job,
                    session,
                    processed_documents=job.processed_documents + 1,
                    processed_chunks=job.processed_chunks + len(nodes),
                    current_raw_document_id=None,
                    current_document_label=None,
                )
            job = (
                await knowledge_graph_build_jobs_repo.update_knowledge_graph_build_job(
                    job,
                    session,
                    stage="verifying",
                )
            )
            persistence_stats = await asyncio.to_thread(
                candidate_store.generation_stats
            )
            logger.info(
                "Knowledge graph Neo4j write verified | %s | stats=%s",
                log_context,
                persistence_stats,
            )
            _require_persisted_graph(persistence_stats)

            await _raise_if_cancel_requested(job, session)
            await session.refresh(graph)
            await knowledge_graph_indices_repo.ensure_knowledge_graph_mutable(
                graph,
                session,
            )
            old_generation = graph.active_generation
            graph.active_generation = job.candidate_generation
            graph.status = "built"
            graph.built_at = utc_now()
            graph.latest_build_error = None
            graph.last_updated = graph.built_at
            await commit_and_refresh(session, graph)
            # Try to clear the negotiation graph cache for the knowledge graph 
            # after a successful build.
            try:
                from app.services import simulations_service

                simulations_service.clear_negotiation_graph_cache_for_knowledge_graph(
                    graph.id
                )
            except Exception:
                logger.warning(
                    "Unable to clear negotiation graph cache after graph build | %s",
                    log_context,
                    exc_info=True,
                )
            job = (
                await knowledge_graph_build_jobs_repo.mark_knowledge_graph_build_job_completed(
                    job,
                    session,
                )
            )
            job = await knowledge_graph_build_jobs_repo.update_knowledge_graph_build_job(
                job,
                session,
                node_count=persistence_stats["node_count"],
                relationship_count=persistence_stats["relationship_count"],
            )

            if old_generation and old_generation != graph.active_generation:
                old_store = _create_scoped_store(graph.id, old_generation)
                await asyncio.to_thread(old_store.delete_generation)
                old_store.close()
            candidate_store.close()
            logger.info(
                "Knowledge graph build completed | %s | stats=%s",
                log_context,
                persistence_stats,
            )
            return _job_read(job)
        except KnowledgeGraphBuildCancelled:
            logger.info(
                "Knowledge graph build cancelled | %s | stats=%s",
                log_context,
                persistence_stats,
            )
            if candidate_store is not None:
                await asyncio.to_thread(candidate_store.delete_generation)
                candidate_store.close()
            graph.status = "built" if graph.active_generation else "cancelled"
            graph.latest_build_error = None
            graph.last_updated = utc_now()
            await commit_and_refresh(session, graph)
            job = (
                await knowledge_graph_build_jobs_repo.mark_knowledge_graph_build_job_cancelled(
                    job,
                    session,
                )
            )
            return _job_read(job)
        except Exception as exc:
            if candidate_store is not None and persistence_stats is None:
                try:
                    persistence_stats = await asyncio.to_thread(
                        candidate_store.generation_stats
                    )
                except Exception:
                    logger.exception(
                        "Unable to inspect failed Neo4j generation | %s",
                        log_context,
                    )
            logger.exception(
                "Knowledge graph build failed | %s | stage=%s | stats=%s",
                log_context,
                job.stage,
                persistence_stats,
            )
            if candidate_store is not None:
                await asyncio.to_thread(candidate_store.delete_generation)
                candidate_store.close()
            graph.status = "built" if graph.active_generation else "failed"
            detail = describe_neo4j_error(exc, settings.NEO4J_URI)
            graph.latest_build_error = detail
            graph.last_updated = utc_now()
            await commit_and_refresh(session, graph)
            job = (
                await knowledge_graph_build_jobs_repo.mark_knowledge_graph_build_job_failed(
                    job,
                    detail,
                    session,
                )
            )
            return _job_read(job)


async def get_knowledge_graph_build_job_srvc(
    job_id: int,
    session: AsyncSession,
) -> KnowledgeGraphBuildJobRead:
    """
    Retrieve a knowledge graph build job by its ID.

    Args:
        job_id (int): The ID of the knowledge graph build job.
        session (AsyncSession): The database session.

    Returns:
        KnowledgeGraphBuildJobRead: The knowledge graph build job.

    Raises:
        ValueError: If the knowledge graph build job is not found.
    """
    job = (
        await knowledge_graph_build_jobs_repo.get_knowledge_graph_build_job_by_id(
            job_id,
            session,
        )
    )
    if job is None:
        raise ValueError("Knowledge graph build job not found")
    return _job_read(job)


async def list_knowledge_graph_build_jobs_srvc(
    session: AsyncSession,
    *,
    skip: int = 0,
    limit: int = 20,
    graph_id: int | None = None,
    status: str | None = None,
) -> list[KnowledgeGraphBuildJobRead]:
    """
    List knowledge graph build jobs with optional filtering.

    Args:
        session (AsyncSession): The database session.
        skip (int): The number of records to skip.
        limit (int): The maximum number of records to return.
        graph_id (int | None): Optional graph ID to filter by.
        status (str | None): Optional status to filter by.

    Returns:
        list[KnowledgeGraphBuildJobRead]: A list of knowledge graph build jobs.
    """
    jobs = await knowledge_graph_build_jobs_repo.list_knowledge_graph_build_jobs(
        session,
        skip=skip,
        limit=limit,
        graph_id=graph_id,
        status=status,
    )
    return [_job_read(job) for job in jobs]


async def cancel_knowledge_graph_build_job_srvc(
    job_id: int,
    session: AsyncSession,
) -> KnowledgeGraphBuildJobRead:
    """
    Cancel a knowledge graph build job by its ID.

    Args:
        job_id (int): The ID of the knowledge graph build job.
        session (AsyncSession): The database session.

    Returns:
        KnowledgeGraphBuildJobRead: The cancelled knowledge graph build job.

    Raises:
        ValueError: If the knowledge graph build job is not found or not 
        active.
    """
    job = (
        await knowledge_graph_build_jobs_repo.get_knowledge_graph_build_job_by_id(
            job_id,
            session,
        )
    )
    if job is None:
        raise ValueError("Knowledge graph build job not found")
    if job.status not in {"queued", "running"}:
        raise ValueError("Knowledge graph build job is not active")
    if job.status == "queued":
        job = (
            await knowledge_graph_build_jobs_repo.mark_knowledge_graph_build_job_cancelled(
                job,
                session,
            )
        )
        return _job_read(job)
    job.cancel_requested = True
    job = await commit_and_refresh(session, job)
    return _job_read(job)


async def _cleanup_interrupted_candidate_generation(job) -> None:
    """
    Cleanup the candidate generation for an interrupted knowledge graph 
    build job.
    Args:
        job: The knowledge graph build job that was interrupted.
    Returns:
        None
    """
    store = None
    # Try to delete the candidate generation from the Neo4j store
    try:
        store = _create_scoped_store(
            job.knowledge_graph_index_id,
            job.candidate_generation,
        )
        await asyncio.to_thread(store.delete_generation)
    except Exception:
        logger.exception(
            "Unable to clean interrupted knowledge graph generation | "
            "job_id=%s | graph_id=%s | generation=%s",
            job.id,
            job.knowledge_graph_index_id,
            job.candidate_generation,
        )
    finally:
        if store is not None:
            try:
                store.close()
            except Exception:
                logger.exception(
                    "Unable to close interrupted knowledge graph store | "
                    "job_id=%s | graph_id=%s | generation=%s",
                    job.id,
                    job.knowledge_graph_index_id,
                    job.candidate_generation,
                )


async def fail_interrupted_knowledge_graph_builds_srvc() -> None:
    """
    Flag graph builds left active by an application shutdown or restart as failed.
    Called on startup in main.
    """
    async with AsyncSessionLocal() as session:
        try:
            interrupted_jobs = (
                await knowledge_graph_build_jobs_repo.list_interrupted_knowledge_graph_build_jobs(
                    session
                )
            )
        except Exception:
            logger.exception("Unable to list interrupted knowledge graph builds")
            return

        for job in interrupted_jobs:
            await _cleanup_interrupted_candidate_generation(job)
            graph = (
                await knowledge_graph_indices_repo.get_knowledge_graph_index_by_id(
                    job.knowledge_graph_index_id,
                    session,
                )
            )
            if graph is not None:
                graph.status = "built" if graph.active_generation else "failed"
                graph.latest_build_error = INTERRUPTED_FAILURE_DETAIL
                graph.last_updated = utc_now()
                await commit_and_refresh(session, graph)
            await knowledge_graph_build_jobs_repo.mark_knowledge_graph_build_job_failed(
                job,
                INTERRUPTED_FAILURE_DETAIL,
                session,
            )

import asyncio
from types import SimpleNamespace
from pathlib import Path

import pytest

from app.services import (
    corpus_bm25_indices_service,
    corpus_indices_service,
    full_corpus_index_pipe_job,
)
from app.schemas.corpus_indices_schemas import CorpusIndexReadWithIds


@pytest.mark.asyncio
async def test_dense_delete_clears_only_dense_cache_after_repository_delete(
    monkeypatch,
):
    index = SimpleNamespace(id=17)
    events = []

    async def delete_dense(target, session):
        assert target is index
        events.append("dense_deleted")

    monkeypatch.setattr(
        corpus_indices_service.corpus_indices_repo,
        "delete_corpus_index",
        delete_dense,
    )
    monkeypatch.setattr(
        corpus_indices_service.simulations_service,
        "clear_negotiation_graph_cache_for_corpus_index",
        lambda index_id: events.append(("dense_cache", index_id)) or 1,
    )

    await corpus_indices_service.delete_corpus_index_srvc(index, object())

    assert events == ["dense_deleted", ("dense_cache", 17)]


@pytest.mark.asyncio
@pytest.mark.parametrize("terminal_state", ["failed", "cancelled"])
async def test_candidate_terminal_paths_clear_only_dense_cache(
    monkeypatch,
    terminal_state,
):
    index = SimpleNamespace(id=17, status="building")
    job = SimpleNamespace(id=9)
    events = []
    bm25_artifact = bytearray(b"lexical artifact remains")

    async def mark_dense_terminal(target, detail, session):
        assert target is index
        target.status = terminal_state
        events.append((terminal_state, target.id))
        return target

    async def mark_job_terminal(*args, **kwargs):
        events.append(("job", terminal_state))
        return job

    async def read_job(current_job, session):
        return current_job

    monkeypatch.setattr(
        full_corpus_index_pipe_job.corpus_indices_repo,
        (
            "fail_corpus_index_build"
            if terminal_state == "failed"
            else "cancel_corpus_index_build"
        ),
        mark_dense_terminal,
    )
    monkeypatch.setattr(
        full_corpus_index_pipe_job.full_corpus_index_pipe_jobs_repo,
        f"mark_full_corpus_index_pipe_job_{terminal_state}",
        mark_job_terminal,
    )
    monkeypatch.setattr(full_corpus_index_pipe_job, "_read_job_detail", read_job)
    monkeypatch.setattr(
        full_corpus_index_pipe_job.simulations_service,
        "clear_negotiation_graph_cache_for_corpus_index",
        lambda index_id: events.append(("dense_cache", index_id)) or 1,
    )

    if terminal_state == "failed":
        await full_corpus_index_pipe_job._fail_job_and_candidate(
            job,
            index,
            object(),
            "broken",
        )
    else:
        await full_corpus_index_pipe_job._mark_job_cancelled(
            job,
            index,
            object(),
            "stopped",
        )

    assert bm25_artifact == b"lexical artifact remains"
    assert ("dense_cache", 17) in events


@pytest.mark.asyncio
async def test_dense_candidate_cache_eviction_survives_repeated_cancellation(
    monkeypatch,
):
    index = SimpleNamespace(id=17, status="building")
    job = SimpleNamespace(id=9)
    events = []

    async def cancelled_after_status_commit(target, detail, session):
        target.status = "cancelled"
        raise asyncio.CancelledError("cancelled after commit")

    monkeypatch.setattr(
        full_corpus_index_pipe_job.corpus_indices_repo,
        "cancel_corpus_index_build",
        cancelled_after_status_commit,
    )
    monkeypatch.setattr(
        full_corpus_index_pipe_job.simulations_service,
        "clear_negotiation_graph_cache_for_corpus_index",
        lambda index_id: events.append(("dense_cache", index_id)) or 1,
    )

    with pytest.raises(asyncio.CancelledError, match="cancelled after commit"):
        await full_corpus_index_pipe_job._mark_job_cancelled(
            job,
            index,
            object(),
        )

    assert events == [("dense_cache", 17)]


@pytest.mark.asyncio
async def test_retired_dense_cleanup_removes_vectors_refs_and_dense_cache_only(
    monkeypatch,
):
    dense_index = SimpleNamespace(id=17, vector_store_id=3)
    vector_store = SimpleNamespace(
        backend="fake",
        collection_name="dense",
        path=None,
        table_name=None,
    )
    indexed_chunks = [SimpleNamespace(external_vector_id="v-1")]
    events = []
    bm25_artifact = bytearray(b"lexical artifact remains")

    async def get_dense(index_id, session):
        assert index_id == 17
        return dense_index

    async def get_vector_store(vector_store_id, session):
        assert vector_store_id == 3
        return vector_store

    async def get_indexed_chunks(*args, **kwargs):
        return indexed_chunks

    async def delete_vectors(**kwargs):
        events.append(("vectors", kwargs["vector_ids"]))

    async def delete_refs(index_id, session):
        events.append(("refs", index_id))

    monkeypatch.setattr(
        full_corpus_index_pipe_job.corpus_indices_repo,
        "get_corpus_index_by_id",
        get_dense,
    )
    monkeypatch.setattr(
        full_corpus_index_pipe_job.vector_stores_repo,
        "get_vector_store_by_id",
        get_vector_store,
    )
    monkeypatch.setattr(
        full_corpus_index_pipe_job.indexed_chunks_repo,
        "get_indexed_chunks_by_corpus_index_id",
        get_indexed_chunks,
    )
    monkeypatch.setattr(
        full_corpus_index_pipe_job,
        "delete_vectors_from_vector_store",
        delete_vectors,
    )
    monkeypatch.setattr(
        full_corpus_index_pipe_job.indexed_chunks_repo,
        "delete_indexed_chunks_by_corpus_index_id_force",
        delete_refs,
    )
    monkeypatch.setattr(
        full_corpus_index_pipe_job.simulations_service,
        "clear_negotiation_graph_cache_for_corpus_index",
        lambda index_id: events.append(("dense_cache", index_id)) or 1,
    )

    await full_corpus_index_pipe_job._cleanup_retired_index(17, object())

    assert events == [
        ("vectors", ["v-1"]),
        ("refs", 17),
        ("dense_cache", 17),
    ]
    assert bm25_artifact == b"lexical artifact remains"


@pytest.mark.asyncio
async def test_interrupted_job_recovery_rolls_back_the_parent_owned_pair(
    monkeypatch,
):
    job = SimpleNamespace(
        id=9,
        status="running",
        stage="embedding",
        cancel_requested=False,
        failure_detail=None,
        candidate_corpus_index_id=17,
    )
    dense_index = SimpleNamespace(id=17, status="building")
    events = []
    bm25_artifact = bytearray(b"lexical artifact remains")

    class Session:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, traceback):
            return False

    async def list_interrupted(session):
        return [job]

    async def get_dense(index_id, session):
        return dense_index

    async def rollback(job_arg, index_arg, **kwargs):
        events.append(
            (
                job_arg.id,
                index_arg.id,
                kwargs["terminal_status"],
                kwargs["detail"],
            )
        )

    monkeypatch.setattr(full_corpus_index_pipe_job, "AsyncSessionLocal", Session)
    monkeypatch.setattr(
        full_corpus_index_pipe_job.full_corpus_index_pipe_jobs_repo,
        "list_interrupted_full_corpus_index_pipe_jobs",
        list_interrupted,
    )
    monkeypatch.setattr(
        full_corpus_index_pipe_job.corpus_indices_repo,
        "get_corpus_index_by_id",
        get_dense,
    )
    monkeypatch.setattr(full_corpus_index_pipe_job, "_rollback_parent_artifacts", rollback)

    await full_corpus_index_pipe_job.fail_interrupted_full_corpus_index_pipe_jobs_srvc()

    assert events == [
        (
            9,
            17,
            "failed",
            full_corpus_index_pipe_job.INTERRUPTED_FAILURE_DETAIL,
        )
    ]
    assert bm25_artifact == b"lexical artifact remains"


def test_dense_status_schema_does_not_claim_bm25_availability():
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc)
    result = CorpusIndexReadWithIds(
        id=17,
        name="dense index",
        corpus_id=2,
        vector_store_id=3,
        chunking_profile_id=4,
        corpus_chunk_set_id=21,
        corpus_chunk_set_revision=3,
        corpus_chunk_set_checksum="a" * 64,
        status="built",
        embedding_model="dense-model",
        created_at=now,
        last_updated=now,
        indexed_document_chunk_ids=[7],
    )

    assert not any("bm25" in field.lower() for field in result.model_dump())
    assert result.corpus_chunk_set_id == 21
    assert result.corpus_chunk_set_revision == 3
    assert result.corpus_chunk_set_checksum == "a" * 64


def test_openwiki_documents_hybrid_artifact_operations_contract():
    repository_root = Path(__file__).resolve().parents[2]
    guide = (
        repository_root / "openwiki" / "domains" / "knowledge-retrieval.md"
    ).read_text(encoding="utf-8")

    required_guidance = (
        "separate persisted artifacts",
        "Hybrid compatibility contract",
        "no standalone BM25 runtime cache",
        "memory is not bounded",
        "process restart",
        "GET /corpus-bm25-indices/",
        "BM25-only configurations omit the retrieval embedding model",
        "build_bm25",
        "requested_bm25_index_name",
        "persisted named sets",
    )
    for guidance in required_guidance:
        assert guidance in guide


@pytest.mark.asyncio
@pytest.mark.parametrize("terminal_state", ["failed", "cancelled"])
async def test_bm25_terminal_build_cleanup_evicts_only_bm25_cache(
    monkeypatch,
    terminal_state,
):
    metadata = SimpleNamespace(
        id=29,
        compressed_artifact_checksum="a" * 64,
        document_chunk_ids_checksum="b" * 64,
    )
    events = []
    dense_vectors = ["v-1"]

    async def compensate(index_id, detail, session):
        assert index_id == 29
        events.append(("artifact", terminal_state))
        return metadata

    monkeypatch.setattr(
        corpus_bm25_indices_service.corpus_bm25_indices_repo,
        f"{terminal_state[:-3] if terminal_state == 'cancelled' else 'fail'}_corpus_bm25_index_build",
        compensate,
    )
    monkeypatch.setattr(
        corpus_bm25_indices_service.simulations_service,
        "clear_negotiation_graph_cache_for_bm25_index",
        lambda index_id, **kwargs: events.append(
            ("bm25_cache", index_id, kwargs)
        )
        or 1,
    )

    if terminal_state == "failed":
        await corpus_bm25_indices_service._mark_build_failed(
            29,
            "broken",
            object(),
        )
    else:
        await corpus_bm25_indices_service._mark_build_cancelled(
            29,
            "stopped",
            object(),
        )

    assert dense_vectors == ["v-1"]
    assert events == [
        ("artifact", terminal_state),
        (
            "bm25_cache",
            29,
            {
                "artifact_checksum": "a" * 64,
                "document_chunk_ids_checksum": "b" * 64,
            },
        ),
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize("operation", ["retire", "delete"])
async def test_bm25_retire_and_delete_clear_artifact_cache_identity(
    monkeypatch,
    operation,
):
    metadata = SimpleNamespace(
        id=29,
        compressed_artifact_checksum="a" * 64,
        document_chunk_ids_checksum="b" * 64,
    )
    events = []

    async def retire(index_id, session):
        events.append(("retire", index_id))
        return metadata

    async def delete(index_id, session):
        events.append(("delete", index_id))

    monkeypatch.setattr(
        corpus_bm25_indices_service.corpus_bm25_indices_repo,
        "mark_corpus_bm25_index_retired",
        retire,
    )
    monkeypatch.setattr(
        corpus_bm25_indices_service.corpus_bm25_indices_repo,
        "delete_corpus_bm25_index",
        delete,
    )
    monkeypatch.setattr(
        corpus_bm25_indices_service.simulations_service,
        "clear_negotiation_graph_cache_for_bm25_index",
        lambda index_id, **kwargs: events.append(("bm25_cache", index_id, kwargs))
        or 1,
    )

    if operation == "retire":
        result = await corpus_bm25_indices_service.retire_corpus_bm25_index_srvc(
            metadata,
            object(),
        )
        assert result is metadata
    else:
        await corpus_bm25_indices_service.delete_corpus_bm25_index_srvc(
            metadata,
            object(),
        )

    assert events == [
        (operation, 29),
        (
            "bm25_cache",
            29,
            {
                "artifact_checksum": "a" * 64,
                "document_chunk_ids_checksum": "b" * 64,
            },
        ),
    ]

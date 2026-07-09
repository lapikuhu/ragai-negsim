import asyncio
from types import SimpleNamespace
from datetime import datetime, timezone

import pytest

from app.schemas.indexing_jobs_schemas import IndexingJobCreate
from app.services import indexing_jobs_service


def _job(**overrides):
    values = {
        "id": 9,
        "corpus_id": 1,
        "chunking_profile_id": 2,
        "vector_store_id": 3,
        "embedding_model": "mini-l6-v2",
        "requested_index_name": "policy-index",
        "requested_vector_namespace": None,
        "status": "queued",
        "stage": "validating",
        "current_raw_document_id": None,
        "current_document_name": None,
        "total_documents": 0,
        "processed_documents": 0,
        "chunks_created": 0,
        "chunks_indexed": 0,
        "queued_at": datetime.now(timezone.utc),
        "started_at": None,
        "completed_at": None,
        "candidate_corpus_index_id": None,
        "replaced_corpus_index_id": None,
        "failure_detail": None,
        "cancel_requested": False,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


@pytest.mark.asyncio
async def test_queue_job_allows_same_configuration_with_different_name(monkeypatch):
    async def fake_get_corpus_by_id(corpus_id, session):
        return SimpleNamespace(id=corpus_id)

    async def fake_get_profile(profile_id, session):
        return SimpleNamespace(id=profile_id, strategy="recursive", config={"chunk_size": 100, "chunk_overlap": 10})

    async def fake_get_store(store_id, session):
        return SimpleNamespace(id=store_id, embedding_dimensions=384)

    async def fake_get_corpus_raw_document_ids(corpus_id, session):
        return [7]

    async def fake_get_corpus_index_by_name(name, session):
        return None

    async def fake_get_corpus_index_by_vector_namespace(**kwargs):
        return None

    async def fake_get_replaceable_built_index(**kwargs):
        raise AssertionError("same-configuration indices should not be treated as replacements")

    async def fake_has_non_terminal(index_id, session):
        raise AssertionError("simulation guards should not run for parallel index creation")

    async def fake_has_knowledge_graphs(index_id, session):
        raise AssertionError("knowledge graph guards should not run for parallel index creation")

    async def fake_create_indexing_job(job_in, session):
        return _job(
            corpus_id=job_in.corpus_id,
            chunking_profile_id=job_in.chunking_profile_id,
            vector_store_id=job_in.vector_store_id,
            embedding_model=job_in.embedding_model,
            requested_index_name=job_in.requested_index_name,
            requested_vector_namespace=job_in.requested_vector_namespace,
        )

    async def fake_update_progress(job, session, **kwargs):
        for key, value in kwargs.items():
            setattr(job, key, value)
        return job

    monkeypatch.setattr(indexing_jobs_service.corpus_repo, "get_corpus_by_id", fake_get_corpus_by_id)
    monkeypatch.setattr(indexing_jobs_service.chunking_profiles_repo, "get_chunking_profile_by_id", fake_get_profile)
    monkeypatch.setattr(indexing_jobs_service.vector_stores_repo, "get_vector_store_by_id", fake_get_store)
    monkeypatch.setattr(indexing_jobs_service.corpus_repo, "get_corpus_raw_document_ids", fake_get_corpus_raw_document_ids)
    monkeypatch.setattr(indexing_jobs_service.corpus_indices_repo, "get_corpus_index_by_name", fake_get_corpus_index_by_name)
    monkeypatch.setattr(indexing_jobs_service.corpus_indices_repo, "get_corpus_index_by_vector_namespace", fake_get_corpus_index_by_vector_namespace)
    monkeypatch.setattr(indexing_jobs_service.corpus_indices_repo, "get_replaceable_built_index", fake_get_replaceable_built_index)
    monkeypatch.setattr(indexing_jobs_service, "_has_non_terminal_simulations_for_index", fake_has_non_terminal)
    monkeypatch.setattr(indexing_jobs_service.corpus_indices_repo, "has_knowledge_graphs", fake_has_knowledge_graphs)
    monkeypatch.setattr(indexing_jobs_service.indexing_jobs_repo, "create_indexing_job", fake_create_indexing_job)
    monkeypatch.setattr(indexing_jobs_service.indexing_jobs_repo, "update_indexing_job_progress", fake_update_progress)

    queued = await indexing_jobs_service.queue_indexing_job_srvc(
        IndexingJobCreate(
            corpus_id=1,
            chunking_profile_id=2,
            vector_store_id=3,
            embedding_model="mini-l6-v2",
            requested_index_name="policy-index-v2",
        ),
        object(),
    )

    assert queued.id == 9
    assert queued.requested_index_name == "policy-index-v2"
    assert queued.total_documents == 1


@pytest.mark.asyncio
async def test_queue_job_rejects_duplicate_index_name(monkeypatch):
    async def fake_get_corpus_by_id(corpus_id, session):
        return SimpleNamespace(id=corpus_id)

    async def fake_get_profile(profile_id, session):
        return SimpleNamespace(id=profile_id, strategy="recursive", config={"chunk_size": 100, "chunk_overlap": 10})

    async def fake_get_store(store_id, session):
        return SimpleNamespace(id=store_id, embedding_dimensions=384)

    async def fake_get_corpus_raw_document_ids(corpus_id, session):
        return [7]

    async def fake_get_corpus_index_by_name(name, session):
        return SimpleNamespace(id=77)

    async def fake_create_indexing_job(job_in, session):
        raise AssertionError("duplicate index names should fail before job creation")

    monkeypatch.setattr(indexing_jobs_service.corpus_repo, "get_corpus_by_id", fake_get_corpus_by_id)
    monkeypatch.setattr(indexing_jobs_service.chunking_profiles_repo, "get_chunking_profile_by_id", fake_get_profile)
    monkeypatch.setattr(indexing_jobs_service.vector_stores_repo, "get_vector_store_by_id", fake_get_store)
    monkeypatch.setattr(indexing_jobs_service.corpus_repo, "get_corpus_raw_document_ids", fake_get_corpus_raw_document_ids)
    monkeypatch.setattr(indexing_jobs_service.corpus_indices_repo, "get_corpus_index_by_name", fake_get_corpus_index_by_name)
    monkeypatch.setattr(indexing_jobs_service.indexing_jobs_repo, "create_indexing_job", fake_create_indexing_job)

    with pytest.raises(ValueError, match="Corpus index name already exists"):
        await indexing_jobs_service.queue_indexing_job_srvc(
            IndexingJobCreate(
                corpus_id=1,
                chunking_profile_id=2,
                vector_store_id=3,
                embedding_model="mini-l6-v2",
                requested_index_name="policy-index",
            ),
            object(),
        )


@pytest.mark.asyncio
async def test_queue_job_rejects_duplicate_vector_namespace(monkeypatch):
    async def fake_get_corpus_by_id(corpus_id, session):
        return SimpleNamespace(id=corpus_id)

    async def fake_get_profile(profile_id, session):
        return SimpleNamespace(id=profile_id, strategy="recursive", config={"chunk_size": 100, "chunk_overlap": 10})

    async def fake_get_store(store_id, session):
        return SimpleNamespace(id=store_id, embedding_dimensions=384)

    async def fake_get_corpus_raw_document_ids(corpus_id, session):
        return [7]

    async def fake_get_corpus_index_by_name(name, session):
        return None

    async def fake_get_corpus_index_by_vector_namespace(**kwargs):
        return SimpleNamespace(id=77, vector_store_id=kwargs["vector_store_id"])

    async def fake_create_indexing_job(job_in, session):
        raise AssertionError("duplicate vector namespaces should fail before job creation")

    monkeypatch.setattr(indexing_jobs_service.corpus_repo, "get_corpus_by_id", fake_get_corpus_by_id)
    monkeypatch.setattr(indexing_jobs_service.chunking_profiles_repo, "get_chunking_profile_by_id", fake_get_profile)
    monkeypatch.setattr(indexing_jobs_service.vector_stores_repo, "get_vector_store_by_id", fake_get_store)
    monkeypatch.setattr(indexing_jobs_service.corpus_repo, "get_corpus_raw_document_ids", fake_get_corpus_raw_document_ids)
    monkeypatch.setattr(indexing_jobs_service.corpus_indices_repo, "get_corpus_index_by_name", fake_get_corpus_index_by_name)
    monkeypatch.setattr(indexing_jobs_service.corpus_indices_repo, "get_corpus_index_by_vector_namespace", fake_get_corpus_index_by_vector_namespace)
    monkeypatch.setattr(indexing_jobs_service.indexing_jobs_repo, "create_indexing_job", fake_create_indexing_job)

    with pytest.raises(ValueError, match="Vector namespace already exists for this vector store"):
        await indexing_jobs_service.queue_indexing_job_srvc(
            IndexingJobCreate(
                corpus_id=1,
                chunking_profile_id=2,
                vector_store_id=3,
                embedding_model="mini-l6-v2",
                requested_index_name="policy-index-v2",
                requested_vector_namespace="shared-namespace",
            ),
            object(),
        )


@pytest.mark.asyncio
async def test_activate_candidate_index_does_not_infer_replacement(monkeypatch):
    job = _job(requested_index_name="policy-index-v2")
    candidate_index = SimpleNamespace(id=88, status="built")

    async def fake_get_replaceable_built_index(**kwargs):
        raise AssertionError("activation should not look up same-configuration replacement targets")

    async def fake_activate_candidate_index(**kwargs):
        assert "replaced_index" not in kwargs
        kwargs["candidate_index"].name = kwargs["requested_name"]
        return kwargs["candidate_index"], None

    monkeypatch.setattr(indexing_jobs_service.corpus_indices_repo, "get_replaceable_built_index", fake_get_replaceable_built_index)
    monkeypatch.setattr(indexing_jobs_service.corpus_indices_repo, "activate_candidate_index", fake_activate_candidate_index)

    result = await indexing_jobs_service._activate_candidate_index(job, candidate_index, object())

    assert result.candidate_corpus_index_id == 88
    assert result.replaced_corpus_index_id is None
    assert candidate_index.name == "policy-index-v2"


@pytest.mark.asyncio
async def test_queue_job_rejects_when_vector_store_dimensions_are_unset(monkeypatch):
    async def fake_get_corpus_by_id(corpus_id, session):
        return SimpleNamespace(id=corpus_id)

    async def fake_get_profile(profile_id, session):
        return SimpleNamespace(id=profile_id, strategy="recursive", config={"chunk_size": 100, "chunk_overlap": 10})

    async def fake_get_store(store_id, session):
        return SimpleNamespace(id=store_id, embedding_dimensions=None)

    monkeypatch.setattr(indexing_jobs_service.corpus_repo, "get_corpus_by_id", fake_get_corpus_by_id)
    monkeypatch.setattr(indexing_jobs_service.chunking_profiles_repo, "get_chunking_profile_by_id", fake_get_profile)
    monkeypatch.setattr(indexing_jobs_service.vector_stores_repo, "get_vector_store_by_id", fake_get_store)

    with pytest.raises(ValueError, match="Vector store dimensions are not set"):
        await indexing_jobs_service.queue_indexing_job_srvc(
            IndexingJobCreate(
                corpus_id=1,
                chunking_profile_id=2,
                vector_store_id=3,
                embedding_model="mini-l6-v2",
                requested_index_name="policy-index",
            ),
            object(),
        )


@pytest.mark.asyncio
async def test_queue_job_rejects_when_vector_store_dimensions_mismatch(monkeypatch):
    async def fake_get_corpus_by_id(corpus_id, session):
        return SimpleNamespace(id=corpus_id)

    async def fake_get_profile(profile_id, session):
        return SimpleNamespace(id=profile_id, strategy="recursive", config={"chunk_size": 100, "chunk_overlap": 10})

    async def fake_get_store(store_id, session):
        return SimpleNamespace(id=store_id, embedding_dimensions=1536)

    monkeypatch.setattr(indexing_jobs_service.corpus_repo, "get_corpus_by_id", fake_get_corpus_by_id)
    monkeypatch.setattr(indexing_jobs_service.chunking_profiles_repo, "get_chunking_profile_by_id", fake_get_profile)
    monkeypatch.setattr(indexing_jobs_service.vector_stores_repo, "get_vector_store_by_id", fake_get_store)

    with pytest.raises(ValueError, match=r"Embedding model dimensions \(384\) do not match vector store dimensions \(1536\)"):
        await indexing_jobs_service.queue_indexing_job_srvc(
            IndexingJobCreate(
                corpus_id=1,
                chunking_profile_id=2,
                vector_store_id=3,
                embedding_model="mini-l6-v2",
                requested_index_name="policy-index",
            ),
            object(),
        )


@pytest.mark.asyncio
async def test_run_job_completes_with_warnings_when_one_pdf_is_skipped(monkeypatch, recording_async_session_factory):
    captured_warnings = []

    async def fake_get_job_by_id(job_id, session):
        return _job(id=job_id)

    async def fake_mark_running(job, session):
        job.status = "running"
        return job

    async def fake_create_candidate(job, session):
        return SimpleNamespace(id=88, status="building")

    async def fake_process_documents(job, candidate_index, session):
        captured_warnings.append(
            SimpleNamespace(
                id=1,
                raw_document_id=None,
                document_name="bad.pdf",
                stage="converting",
                message="Skipped bad.pdf",
                created_at=datetime.now(timezone.utc),
            )
        )
        return SimpleNamespace(successful_documents=1, chunks_created=12, chunks_indexed=12)

    async def fake_embed_candidate(job, candidate_index, session):
        return None

    async def fake_activate(job, candidate_index, session):
        return SimpleNamespace(candidate_corpus_index_id=88, replaced_corpus_index_id=None)

    async def fake_complete(job, session, **kwargs):
        job.status = kwargs["status"]
        job.candidate_corpus_index_id = kwargs["candidate_corpus_index_id"]
        return job

    async def fake_list_warnings(indexing_job_id, session):
        return captured_warnings

    monkeypatch.setattr(indexing_jobs_service.indexing_jobs_repo, "get_indexing_job_by_id", fake_get_job_by_id)
    monkeypatch.setattr(indexing_jobs_service.indexing_jobs_repo, "mark_indexing_job_running", fake_mark_running)
    monkeypatch.setattr(indexing_jobs_service, "_create_candidate_index", fake_create_candidate)
    monkeypatch.setattr(indexing_jobs_service, "_process_documents", fake_process_documents)
    monkeypatch.setattr(indexing_jobs_service, "_embed_candidate", fake_embed_candidate)
    monkeypatch.setattr(indexing_jobs_service, "_activate_candidate_index", fake_activate)
    monkeypatch.setattr(indexing_jobs_service.indexing_jobs_repo, "mark_indexing_job_completed", fake_complete)
    monkeypatch.setattr(indexing_jobs_service.indexing_jobs_repo, "list_indexing_job_warnings", fake_list_warnings)

    monkeypatch.setattr(indexing_jobs_service, "AsyncSessionLocal", recording_async_session_factory)

    result = await indexing_jobs_service.run_indexing_job_srvc(job_id=9)

    assert result.status == "completed_with_warnings"
    assert result.candidate_corpus_index_id == 88
    assert len(result.warnings) == 1


@pytest.mark.asyncio
async def test_cancel_queued_indexing_job_requests_cancel_and_marks_job_cancelled(monkeypatch):
    job = _job(status="queued", stage="validating", candidate_corpus_index_id=88)
    candidate_index = SimpleNamespace(id=88, status="building")
    captured = []

    async def fake_get_job_by_id(job_id, session):
        return job

    async def fake_request_cancel(current_job, session):
        current_job.cancel_requested = True
        return current_job

    async def fake_get_candidate_index_by_id(index_id, session):
        return candidate_index

    async def fake_mark_cancelled(current_job, session, detail=None):
        current_job.status = "cancelled"
        current_job.stage = "finished"
        current_job.failure_detail = detail
        return current_job

    async def fake_mark_index_cancelled(index, reason, session):
        captured.append((index.id, reason))
        index.status = "cancelled"
        return index

    async def fake_read_job_detail(current_job, session):
        return current_job

    monkeypatch.setattr(indexing_jobs_service.indexing_jobs_repo, "get_indexing_job_by_id", fake_get_job_by_id)
    monkeypatch.setattr(indexing_jobs_service.indexing_jobs_repo, "request_indexing_job_cancel", fake_request_cancel)
    monkeypatch.setattr(indexing_jobs_service.corpus_indices_repo, "get_corpus_index_by_id", fake_get_candidate_index_by_id)
    monkeypatch.setattr(indexing_jobs_service.indexing_jobs_repo, "mark_indexing_job_cancelled", fake_mark_cancelled)
    monkeypatch.setattr(indexing_jobs_service.corpus_indices_repo, "mark_corpus_index_cancelled", fake_mark_index_cancelled)
    monkeypatch.setattr(indexing_jobs_service, "_read_job_detail", fake_read_job_detail)
    monkeypatch.setattr(indexing_jobs_service, "_cancel_live_indexing_task", lambda job_id: False)

    result = await indexing_jobs_service.cancel_indexing_job_srvc(9, object())

    assert result.status == "cancelled"
    assert result.cancel_requested is True
    assert captured == [(88, "Indexing job cancelled by user")]


@pytest.mark.asyncio
async def test_run_job_marks_cancelled_when_task_is_cancelled(monkeypatch, recording_async_session_factory):
    job = _job(id=9, status="queued")
    candidate_index = SimpleNamespace(id=88, status="building")

    async def fake_get_job_by_id(job_id, session):
        return job

    async def fake_mark_running(current_job, session):
        current_job.status = "running"
        return current_job

    async def fake_create_candidate(current_job, session):
        return candidate_index

    async def fake_process_documents(current_job, current_candidate, session):
        raise asyncio.CancelledError()

    async def fake_fail(*args, **kwargs):
        raise AssertionError("failure path should not be used for cancellation")

    async def fake_cancel_job(current_job, session, detail=None):
        current_job.status = "cancelled"
        current_job.stage = "finished"
        current_job.failure_detail = detail
        return current_job

    async def fake_cancel_index(index, reason, session):
        index.status = "cancelled"
        return index

    async def fake_read_job_detail(current_job, session):
        return current_job

    monkeypatch.setattr(indexing_jobs_service.indexing_jobs_repo, "get_indexing_job_by_id", fake_get_job_by_id)
    monkeypatch.setattr(indexing_jobs_service.indexing_jobs_repo, "mark_indexing_job_running", fake_mark_running)
    monkeypatch.setattr(indexing_jobs_service, "_create_candidate_index", fake_create_candidate)
    monkeypatch.setattr(indexing_jobs_service, "_process_documents", fake_process_documents)
    monkeypatch.setattr(indexing_jobs_service, "_fail_job_and_candidate", fake_fail)
    monkeypatch.setattr(indexing_jobs_service.indexing_jobs_repo, "mark_indexing_job_cancelled", fake_cancel_job)
    monkeypatch.setattr(indexing_jobs_service.corpus_indices_repo, "mark_corpus_index_cancelled", fake_cancel_index)
    monkeypatch.setattr(indexing_jobs_service, "_read_job_detail", fake_read_job_detail)
    monkeypatch.setattr(indexing_jobs_service, "AsyncSessionLocal", recording_async_session_factory)

    result = await indexing_jobs_service.run_indexing_job_srvc(job_id=9)

    assert result.status == "cancelled"


@pytest.mark.asyncio
async def test_cancel_running_job_returns_cancellation_requested_state(monkeypatch):
    job = _job(status="running", stage="cleaning", current_raw_document_id=12, current_document_name="policy.pdf")

    async def fake_get_job_by_id(job_id, session):
        return job

    async def fake_request_cancel(current_job, session):
        current_job.cancel_requested = True
        return current_job

    async def fake_read_job_detail(current_job, session):
        return current_job

    async def fake_mark_cancelled(*args, **kwargs):
        raise AssertionError("running jobs should not be marked cancelled immediately")

    cancel_calls = []

    monkeypatch.setattr(indexing_jobs_service.indexing_jobs_repo, "get_indexing_job_by_id", fake_get_job_by_id)
    monkeypatch.setattr(indexing_jobs_service.indexing_jobs_repo, "request_indexing_job_cancel", fake_request_cancel)
    monkeypatch.setattr(indexing_jobs_service.indexing_jobs_repo, "mark_indexing_job_cancelled", fake_mark_cancelled)
    monkeypatch.setattr(indexing_jobs_service, "_read_job_detail", fake_read_job_detail)
    monkeypatch.setattr(indexing_jobs_service, "_cancel_live_indexing_task", lambda job_id: cancel_calls.append(job_id) or True)

    result = await indexing_jobs_service.cancel_indexing_job_srvc(9, object())

    assert result.status == "running"
    assert result.cancel_requested is True
    assert result.stage == "cleaning"
    assert result.current_document_name == "policy.pdf"
    assert cancel_calls == []

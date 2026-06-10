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
    }
    values.update(overrides)
    return SimpleNamespace(**values)


@pytest.mark.asyncio
async def test_queue_job_rejects_when_non_terminal_simulation_uses_replaceable_index(monkeypatch):
    async def fake_get_corpus_by_id(corpus_id, session):
        return SimpleNamespace(id=corpus_id)

    async def fake_get_profile(profile_id, session):
        return SimpleNamespace(id=profile_id, strategy="recursive", config={"chunk_size": 100, "chunk_overlap": 10})

    async def fake_get_store(store_id, session):
        return SimpleNamespace(id=store_id, embedding_dimensions=384)

    async def fake_get_corpus_raw_document_ids(corpus_id, session):
        return [7]

    async def fake_get_replaceable_built_index(**kwargs):
        return SimpleNamespace(id=77)

    async def fake_get_corpus_index_by_name(name, session):
        return None

    async def fake_has_non_terminal(index_id, session):
        return True

    monkeypatch.setattr(indexing_jobs_service.corpus_repo, "get_corpus_by_id", fake_get_corpus_by_id)
    monkeypatch.setattr(indexing_jobs_service.chunking_profiles_repo, "get_chunking_profile_by_id", fake_get_profile)
    monkeypatch.setattr(indexing_jobs_service.vector_stores_repo, "get_vector_store_by_id", fake_get_store)
    monkeypatch.setattr(indexing_jobs_service.corpus_repo, "get_corpus_raw_document_ids", fake_get_corpus_raw_document_ids)
    monkeypatch.setattr(indexing_jobs_service.corpus_indices_repo, "get_corpus_index_by_name", fake_get_corpus_index_by_name)
    monkeypatch.setattr(indexing_jobs_service.corpus_indices_repo, "get_replaceable_built_index", fake_get_replaceable_built_index)
    monkeypatch.setattr(indexing_jobs_service, "_has_non_terminal_simulations_for_index", fake_has_non_terminal)

    with pytest.raises(ValueError, match="Cannot replace corpus index while simulations are still using it"):
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
async def test_run_job_completes_with_warnings_when_one_pdf_is_skipped(monkeypatch):
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

    class FakeSession:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        def add(self, instance):
            return None

        async def commit(self):
            return None

        async def refresh(self, instance):
            return None

        async def rollback(self):
            return None

    monkeypatch.setattr(indexing_jobs_service, "AsyncSessionLocal", lambda: FakeSession())

    result = await indexing_jobs_service.run_indexing_job_srvc(job_id=9)

    assert result.status == "completed_with_warnings"
    assert result.candidate_corpus_index_id == 88
    assert len(result.warnings) == 1

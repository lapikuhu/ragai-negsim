from types import SimpleNamespace

import pytest

from app.models import chunking_profiles  # noqa: F401
from app.models import counterpart_personas  # noqa: F401
from app.models import corpus  # noqa: F401
from app.models import corpus_indices  # noqa: F401
from app.models.document_chunks import DocumentChunk
from app.models import full_corpus_index_pipe_job_warnings  # noqa: F401
from app.models.full_corpus_index_pipe_jobs import FullCorpusIndexPipeJob
from app.models import indexed_chunks  # noqa: F401
from app.models import prompts  # noqa: F401
from app.models import raw_documents  # noqa: F401
from app.models import scenarios  # noqa: F401
from app.models import sessions  # noqa: F401
from app.models import simulations  # noqa: F401
from app.models import user_roles  # noqa: F401
from app.models import users  # noqa: F401
from app.models import vector_stores  # noqa: F401
from app.repositories import corpus_indices_repo, document_chunks_repo, full_corpus_index_pipe_jobs_repo
from app.schemas.full_corpus_index_pipe_jobs_schemas import FullCorpusIndexPipeJobCreate


def test_full_corpus_index_pipe_job_schema_tracks_candidate_and_replaced_index_ids():
    job = FullCorpusIndexPipeJob(
        corpus_id=1,
        chunking_profile_id=2,
        vector_store_id=3,
        embedding_model="mini-l6-v2",
        requested_index_name="policy-index",
        status="queued",
        stage="validating",
    )

    assert job.candidate_corpus_index_id is None
    assert job.replaced_corpus_index_id is None
    assert job.cancel_requested is False
    assert job.total_documents == 0
    assert job.processed_documents == 0


def test_document_chunk_allows_nullable_full_corpus_index_pipe_job_id():
    chunk = DocumentChunk(
        raw_document_id=1,
        chunking_profile_id=2,
        chunk_index=0,
        content="hello",
        full_corpus_index_pipe_job_id=None,
    )

    assert chunk.full_corpus_index_pipe_job_id is None


@pytest.mark.asyncio
async def test_create_active_job_conflicts_when_another_job_is_running(monkeypatch):
    async def fake_get_active_full_corpus_index_pipe_job(session):
        return SimpleNamespace(id=7, status="running")

    monkeypatch.setattr(full_corpus_index_pipe_jobs_repo, "get_active_full_corpus_index_pipe_job", fake_get_active_full_corpus_index_pipe_job)

    with pytest.raises(ValueError, match="Another full corpus index pipe job is already active"):
        await full_corpus_index_pipe_jobs_repo.create_full_corpus_index_pipe_job(
            FullCorpusIndexPipeJobCreate(
                corpus_id=1,
                chunking_profile_id=2,
                vector_store_id=3,
                embedding_model="mini-l6-v2",
                requested_index_name="policy-index",
            ),
            object(),
        )


@pytest.mark.asyncio
async def test_find_replaceable_index_matches_configuration_tuple():
    target = SimpleNamespace(id=9, name="existing-index")

    class FakeResult:
        def first(self):
            return target

    class FakeSession:
        async def exec(self, statement):
            return FakeResult()

    index = await corpus_indices_repo.get_replaceable_built_index(
        corpus_id=1,
        chunking_profile_id=2,
        vector_store_id=3,
        embedding_model="mini-l6-v2",
        session=FakeSession(),
    )

    assert index is target


@pytest.mark.asyncio
async def test_list_document_chunks_for_job_filters_by_full_corpus_index_pipe_job():
    chunks = [SimpleNamespace(id=1), SimpleNamespace(id=2)]

    class FakeResult:
        def all(self):
            return chunks

    class FakeSession:
        async def exec(self, statement):
            return FakeResult()

    result = await document_chunks_repo.list_document_chunks_for_job(44, FakeSession())

    assert result == chunks


@pytest.mark.asyncio
async def test_update_full_corpus_index_pipe_job_progress_can_clear_current_document_fields(monkeypatch):
    job = SimpleNamespace(
        stage="chunking",
        current_raw_document_id=7,
        current_document_name="sample.pdf",
        total_documents=2,
        processed_documents=1,
        chunks_created=4,
        chunks_indexed=0,
    )

    async def fake_commit_and_refresh(session, updated_job):
        return updated_job

    monkeypatch.setattr(full_corpus_index_pipe_jobs_repo, "commit_and_refresh", fake_commit_and_refresh)

    result = await full_corpus_index_pipe_jobs_repo.update_full_corpus_index_pipe_job_progress(
        job,
        object(),
        stage="embedding",
        current_raw_document_id=None,
        current_document_name=None,
    )

    assert result.current_raw_document_id is None
    assert result.current_document_name is None
    assert result.stage == "embedding"

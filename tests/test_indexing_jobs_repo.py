from types import SimpleNamespace

import pytest

from app.models import chunking_profiles  # noqa: F401
from app.models import counterpart_personas  # noqa: F401
from app.models import corpus  # noqa: F401
from app.models import corpus_indices  # noqa: F401
from app.models.document_chunks import DocumentChunk
from app.models import indexing_job_warnings  # noqa: F401
from app.models.indexing_jobs import IndexingJob
from app.models import indexed_chunks  # noqa: F401
from app.models import prompts  # noqa: F401
from app.models import raw_documents  # noqa: F401
from app.models import scenarios  # noqa: F401
from app.models import sessions  # noqa: F401
from app.models import simulations  # noqa: F401
from app.models import user_roles  # noqa: F401
from app.models import users  # noqa: F401
from app.models import vector_stores  # noqa: F401
from app.repositories import corpus_indices_repo, document_chunks_repo, indexing_jobs_repo
from app.schemas.indexing_jobs_schemas import IndexingJobCreate


def test_indexing_job_schema_tracks_candidate_and_replaced_index_ids():
    job = IndexingJob(
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
    assert job.total_documents == 0
    assert job.processed_documents == 0


def test_document_chunk_allows_nullable_indexing_job_id():
    chunk = DocumentChunk(
        raw_document_id=1,
        chunking_profile_id=2,
        chunk_index=0,
        content="hello",
        indexing_job_id=None,
    )

    assert chunk.indexing_job_id is None


@pytest.mark.asyncio
async def test_create_active_job_conflicts_when_another_job_is_running(monkeypatch):
    async def fake_get_active_indexing_job(session):
        return SimpleNamespace(id=7, status="running")

    monkeypatch.setattr(indexing_jobs_repo, "get_active_indexing_job", fake_get_active_indexing_job)

    with pytest.raises(ValueError, match="Another indexing job is already active"):
        await indexing_jobs_repo.create_indexing_job(
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
async def test_list_document_chunks_for_job_filters_by_indexing_job():
    chunks = [SimpleNamespace(id=1), SimpleNamespace(id=2)]

    class FakeResult:
        def all(self):
            return chunks

    class FakeSession:
        async def exec(self, statement):
            return FakeResult()

    result = await document_chunks_repo.list_document_chunks_for_job(44, FakeSession())

    assert result == chunks

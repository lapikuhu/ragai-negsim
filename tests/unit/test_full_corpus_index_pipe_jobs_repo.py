from types import SimpleNamespace

import pytest
from pydantic import ValidationError

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
from app.schemas import full_corpus_index_pipe_jobs_schemas
from app.schemas.full_corpus_index_pipe_jobs_schemas import FullCorpusIndexPipeJobCreate


def test_full_corpus_index_pipe_create_defaults_to_bm25_pair_building():
    request = FullCorpusIndexPipeJobCreate(
        corpus_id=1,
        chunking_profile_id=2,
        vector_store_id=3,
        embedding_model="mini-l6-v2",
        requested_index_name="policy dense",
        requested_chunk_set_name="August policy set",
        requested_bm25_index_name="policy lexical",
    )

    assert request.model_dump().get("build_bm25") is True
    assert request.model_dump().get("requested_bm25_index_name") == "policy lexical"


def test_full_corpus_index_pipe_create_requires_bm25_name_when_enabled():
    with pytest.raises(ValidationError, match="BM25 index name is required"):
        FullCorpusIndexPipeJobCreate(
            corpus_id=1,
            chunking_profile_id=2,
            vector_store_id=3,
            embedding_model="mini-l6-v2",
            requested_index_name="policy dense",
            requested_chunk_set_name="August policy set",
        )


def test_full_corpus_index_pipe_create_clears_bm25_name_when_disabled():
    request = FullCorpusIndexPipeJobCreate(
        corpus_id=1,
        chunking_profile_id=2,
        vector_store_id=3,
        embedding_model="mini-l6-v2",
        requested_index_name="policy dense",
        requested_chunk_set_name="August policy set",
        build_bm25=False,
        requested_bm25_index_name="ignored lexical name",
    )

    assert request.requested_bm25_index_name is None


def test_full_corpus_index_pipe_persistence_contract_requires_requester():
    persist_type = getattr(
        full_corpus_index_pipe_jobs_schemas,
        "FullCorpusIndexPipeJobPersist",
        None,
    )

    assert persist_type is not None
    persisted = persist_type(
        corpus_id=1,
        chunking_profile_id=2,
        vector_store_id=3,
        embedding_model="mini-l6-v2",
        requested_index_name="policy dense",
        requested_chunk_set_name="August policy set",
        requested_bm25_index_name="policy lexical",
        requested_by_user_id=9,
    )
    assert persisted.requested_by_user_id == 9
    assert persisted.requested_chunk_set_name == "August policy set"


def test_full_corpus_index_pipe_job_schema_tracks_candidate_and_replaced_index_ids():
    job = FullCorpusIndexPipeJob(
        corpus_id=1,
        chunking_profile_id=2,
        vector_store_id=3,
        embedding_model="mini-l6-v2",
        requested_index_name="policy-index",
        requested_chunk_set_name="August policy set",
        status="queued",
        stage="validating",
    )

    assert job.candidate_corpus_index_id is None
    assert job.replaced_corpus_index_id is None
    assert job.cancel_requested is False
    assert job.total_documents == 0
    assert job.processed_documents == 0
    assert job.build_bm25 is True
    assert job.requested_bm25_index_name is None
    assert job.requested_by_user_id is None
    assert job.bm25_build_job_id is None
    assert job.requested_chunk_set_name == "August policy set"
    assert job.corpus_chunk_set_id is None


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
                requested_chunk_set_name="August policy set",
                build_bm25=False,
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


@pytest.mark.asyncio
async def test_set_full_corpus_index_pipe_job_bm25_child_links_job_and_stage(monkeypatch):
    job = SimpleNamespace(bm25_build_job_id=None, stage="chunking")

    async def fake_commit_and_refresh(session, updated_job):
        return updated_job

    monkeypatch.setattr(
        full_corpus_index_pipe_jobs_repo,
        "commit_and_refresh",
        fake_commit_and_refresh,
    )

    setter = getattr(
        full_corpus_index_pipe_jobs_repo,
        "set_full_corpus_index_pipe_job_bm25_child",
        None,
    )
    assert setter is not None
    result = await setter(job, 71, object())

    assert result.bm25_build_job_id == 71
    assert result.stage == "building_bm25"


@pytest.mark.asyncio
async def test_set_full_corpus_index_pipe_job_chunk_set_persists_identity(monkeypatch):
    job = SimpleNamespace(corpus_chunk_set_id=None, stage="creating_chunk_set")

    async def fake_commit_and_refresh(session, updated_job):
        return updated_job

    monkeypatch.setattr(
        full_corpus_index_pipe_jobs_repo,
        "commit_and_refresh",
        fake_commit_and_refresh,
    )

    result = await full_corpus_index_pipe_jobs_repo.set_full_corpus_index_pipe_job_chunk_set(
        job,
        21,
        object(),
    )

    assert result.corpus_chunk_set_id == 21


@pytest.mark.asyncio
async def test_claim_next_full_pipe_prefers_interrupted_rollback(monkeypatch):
    rollback_job = _full_pipe_model(status="running", stage="rolling_back")

    class FakeResult:
        def first(self):
            return rollback_job

    class RecordingSession:
        statements = []

        async def exec(self, statement):
            self.statements.append(statement)
            return FakeResult()

    claim = getattr(
        full_corpus_index_pipe_jobs_repo,
        "claim_next_full_corpus_index_pipe_job",
        None,
    )
    assert claim is not None

    result = await claim(RecordingSession())

    assert result is rollback_job


@pytest.mark.asyncio
async def test_claim_next_full_pipe_marks_oldest_queued_parent_running(monkeypatch):
    queued_job = _full_pipe_model(status="queued", stage="validating")

    class FakeResult:
        def __init__(self, row):
            self.row = row

        def first(self):
            return self.row

    class RecordingSession:
        calls = 0

        async def exec(self, statement):
            self.calls += 1
            return FakeResult(None if self.calls == 1 else queued_job)

    async def persist(_session, instance):
        return instance

    monkeypatch.setattr(
        full_corpus_index_pipe_jobs_repo,
        "commit_and_refresh",
        persist,
    )
    claim = getattr(
        full_corpus_index_pipe_jobs_repo,
        "claim_next_full_corpus_index_pipe_job",
        None,
    )
    assert claim is not None

    result = await claim(RecordingSession())

    assert result.status == "running"
    assert result.started_at is not None


def _full_pipe_model(**overrides):
    values = {
        "corpus_id": 1,
        "chunking_profile_id": 2,
        "vector_store_id": 3,
        "embedding_model": "mini-l6-v2",
        "requested_index_name": "policy dense",
        "requested_chunk_set_name": "August policy set",
        "build_bm25": False,
        "status": "queued",
        "stage": "validating",
    }
    values.update(overrides)
    return FullCorpusIndexPipeJob(**values)


@pytest.mark.asyncio
async def test_mark_full_pipe_rolling_back_keeps_parent_non_terminal(monkeypatch):
    job = _full_pipe_model(status="running", stage="embedding")

    async def persist(_session, instance):
        return instance

    monkeypatch.setattr(
        full_corpus_index_pipe_jobs_repo,
        "commit_and_refresh",
        persist,
    )
    transition = getattr(
        full_corpus_index_pipe_jobs_repo,
        "mark_full_corpus_index_pipe_job_rolling_back",
        None,
    )

    assert transition is not None
    result = await transition(job, "dense failed", object())

    assert result.status == "running"
    assert result.stage == "rolling_back"
    assert result.failure_detail == "dense failed"

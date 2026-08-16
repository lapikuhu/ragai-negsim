from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.models.corpus_bm25_build_jobs import CorpusBm25BuildJob
from app.schemas.corpus_bm25_build_jobs_schemas import CorpusBm25BuildJobQueueRequest
from app.services import corpus_bm25_build_jobs_service as service


CORPUS_CHUNK_SET_ID = 21
CORPUS_CHUNK_SET_REVISION = 3
CORPUS_CHUNK_SET_CHECKSUM = "c" * 64


def _snapshot(
    document_chunk_ids: list[int] | None = None,
    *,
    revision: int = CORPUS_CHUNK_SET_REVISION,
    checksum: str = CORPUS_CHUNK_SET_CHECKSUM,
):
    return SimpleNamespace(
        chunk_set=SimpleNamespace(
            id=CORPUS_CHUNK_SET_ID,
            corpus_id=11,
            chunking_profile_id=3,
            revision=revision,
            document_chunk_ids_checksum=checksum,
        ),
        document_chunk_ids=[7, 12] if document_chunk_ids is None else document_chunk_ids,
    )


def _allow_name_reservations(monkeypatch):
    monkeypatch.setattr(
        service.corpus_bm25_build_jobs_repo,
        "has_active_corpus_bm25_build_job_name",
        AsyncMock(return_value=False),
    )
    monkeypatch.setattr(
        service.full_corpus_index_pipe_jobs_repo,
        "has_active_full_pipe_bm25_name_reservation",
        AsyncMock(return_value=False),
    )


@pytest.mark.asyncio
async def test_bm25_name_check_returns_trimmed_available_name(monkeypatch):
    _allow_name_reservations(monkeypatch)
    monkeypatch.setattr(
        service.corpus_bm25_indices_repo,
        "get_corpus_bm25_index_metadata_by_name",
        AsyncMock(return_value=None),
        raising=False,
    )
    validator = getattr(
        service,
        "ensure_corpus_bm25_index_name_available_srvc",
        None,
    )

    assert validator is not None
    assert await validator("  policy lexical  ", object()) == "policy lexical"


@pytest.mark.asyncio
async def test_bm25_name_check_rejects_existing_artifact(monkeypatch):
    monkeypatch.setattr(
        service.corpus_bm25_indices_repo,
        "get_corpus_bm25_index_metadata_by_name",
        AsyncMock(return_value=SimpleNamespace(id=8)),
        raising=False,
    )
    validator = getattr(
        service,
        "ensure_corpus_bm25_index_name_available_srvc",
        None,
    )

    assert validator is not None
    with pytest.raises(service.CorpusBm25BuildJobConflictError, match="already exists"):
        await validator("policy lexical", object())


@pytest.mark.asyncio
async def test_bm25_name_check_allows_owning_full_pipe_reservation(monkeypatch):
    async def no_other_full_pipe_reservation(
        requested_name,
        _session,
        *,
        exclude_job_id,
    ):
        assert requested_name == "policy lexical"
        assert exclude_job_id == 9
        return False

    monkeypatch.setattr(
        service.corpus_bm25_indices_repo,
        "get_corpus_bm25_index_metadata_by_name",
        AsyncMock(return_value=None),
        raising=False,
    )
    monkeypatch.setattr(
        service.corpus_bm25_build_jobs_repo,
        "has_active_corpus_bm25_build_job_name",
        AsyncMock(return_value=False),
    )
    monkeypatch.setattr(
        service.full_corpus_index_pipe_jobs_repo,
        "has_active_full_pipe_bm25_name_reservation",
        no_other_full_pipe_reservation,
    )

    assert await service.ensure_corpus_bm25_index_name_available_srvc(
        "policy lexical",
        object(),
        reserved_by_full_pipe_job_id=9,
    ) == "policy lexical"


@pytest.mark.asyncio
async def test_bm25_name_check_rejects_another_full_pipe_reservation(monkeypatch):
    async def another_full_pipe_reservation(
        requested_name,
        _session,
        *,
        exclude_job_id,
    ):
        assert requested_name == "policy lexical"
        assert exclude_job_id == 9
        return True

    monkeypatch.setattr(
        service.corpus_bm25_indices_repo,
        "get_corpus_bm25_index_metadata_by_name",
        AsyncMock(return_value=None),
        raising=False,
    )
    monkeypatch.setattr(
        service.corpus_bm25_build_jobs_repo,
        "has_active_corpus_bm25_build_job_name",
        AsyncMock(return_value=False),
    )
    monkeypatch.setattr(
        service.full_corpus_index_pipe_jobs_repo,
        "has_active_full_pipe_bm25_name_reservation",
        another_full_pipe_reservation,
    )

    with pytest.raises(service.CorpusBm25BuildJobConflictError, match="already exists"):
        await service.ensure_corpus_bm25_index_name_available_srvc(
            "policy lexical",
            object(),
            reserved_by_full_pipe_job_id=9,
        )


@pytest.mark.asyncio
async def test_requester_id_queue_forwards_full_pipe_reservation_owner(monkeypatch):
    session = object()

    class ValidationObserved(Exception):
        pass

    async def validate_name(
        name,
        received_session,
        *,
        reserved_by_full_pipe_job_id,
    ):
        assert name == "policy lexical"
        assert received_session is session
        assert reserved_by_full_pipe_job_id == 9
        raise ValidationObserved

    monkeypatch.setattr(
        service.name_reservations_repo,
        "lock_name_reservation",
        AsyncMock(),
    )
    monkeypatch.setattr(
        service,
        "ensure_corpus_bm25_index_name_available_srvc",
        validate_name,
    )

    with pytest.raises(ValidationObserved):
        await service.queue_corpus_bm25_build_job_for_requester_id_srvc(
            CorpusBm25BuildJobQueueRequest(
                requested_artifact_name=" policy lexical ",
                corpus_chunk_set_id=CORPUS_CHUNK_SET_ID,
            ),
            23,
            session,
            reserved_by_full_pipe_job_id=9,
        )


@pytest.mark.asyncio
async def test_requester_id_queue_boundary_preserves_attribution(monkeypatch):
    chunks = [SimpleNamespace(id=7, raw_document_id=1)]
    _allow_name_reservations(monkeypatch)
    monkeypatch.setattr(
        service,
        "ensure_corpus_bm25_index_name_available_srvc",
        AsyncMock(return_value="policy lexical"),
        raising=False,
    )
    monkeypatch.setattr(
        service,
        "get_corpus_chunk_set_snapshot_srvc",
        AsyncMock(return_value=_snapshot([7])),
    )
    monkeypatch.setattr(
        service.document_chunks_repo,
        "get_corpus_chunk_set_document_chunks_by_ids",
        AsyncMock(return_value=chunks),
    )
    created = AsyncMock(
        side_effect=lambda value, _session: SimpleNamespace(
            id=9,
            cancel_requested=False,
            queued_at=datetime.now(timezone.utc),
            started_at=None,
            completed_at=None,
            result_bm25_index_id=None,
            failure_detail=None,
            **value.model_dump(),
        )
    )
    monkeypatch.setattr(
        service.corpus_bm25_build_jobs_repo,
        "create_corpus_bm25_build_job",
        created,
    )
    queue_for_requester = getattr(
        service,
        "queue_corpus_bm25_build_job_for_requester_id_srvc",
        None,
    )

    assert queue_for_requester is not None
    result = await queue_for_requester(
        CorpusBm25BuildJobQueueRequest(
            requested_artifact_name=" policy lexical ",
            corpus_chunk_set_id=CORPUS_CHUNK_SET_ID,
        ),
        23,
        object(),
    )

    assert result.requested_by_user_id == 23
    assert result.requested_artifact_name == "policy lexical"
    assert result.corpus_chunk_set_id == CORPUS_CHUNK_SET_ID
    assert result.corpus_chunk_set_revision == CORPUS_CHUNK_SET_REVISION
    assert result.corpus_chunk_set_checksum == CORPUS_CHUNK_SET_CHECKSUM


@pytest.mark.asyncio
async def test_queue_snapshots_sorted_chunk_ids(monkeypatch):
    chunks = [
        SimpleNamespace(id=12, raw_document_id=2),
        SimpleNamespace(id=7, raw_document_id=1),
    ]
    _allow_name_reservations(monkeypatch)
    monkeypatch.setattr(
        service,
        "ensure_corpus_bm25_index_name_available_srvc",
        AsyncMock(return_value="policy bm25"),
    )
    monkeypatch.setattr(
        service,
        "get_corpus_chunk_set_snapshot_srvc",
        AsyncMock(return_value=_snapshot()),
    )
    monkeypatch.setattr(
        service.document_chunks_repo,
        "get_corpus_chunk_set_document_chunks_by_ids",
        AsyncMock(return_value=chunks),
    )
    created = AsyncMock(side_effect=lambda value, _session: SimpleNamespace(
        id=9,
        cancel_requested=False,
        queued_at=datetime.now(timezone.utc),
        started_at=None,
        completed_at=None,
        result_bm25_index_id=None,
        failure_detail=None,
        **value.model_dump(),
    ))
    monkeypatch.setattr(service.corpus_bm25_build_jobs_repo, "create_corpus_bm25_build_job", created)

    result = await service.queue_corpus_bm25_build_job_srvc(
        CorpusBm25BuildJobQueueRequest(
            requested_artifact_name="policy bm25",
            corpus_chunk_set_id=CORPUS_CHUNK_SET_ID,
        ),
        SimpleNamespace(id=5),
        object(),
    )

    saved = created.await_args.args[0]
    assert saved.document_chunk_ids == [7, 12]
    assert saved.document_chunk_ids_checksum == CORPUS_CHUNK_SET_CHECKSUM
    assert saved.corpus_chunk_set_id == CORPUS_CHUNK_SET_ID
    assert saved.corpus_chunk_set_revision == CORPUS_CHUNK_SET_REVISION
    assert saved.corpus_chunk_set_checksum == CORPUS_CHUNK_SET_CHECKSUM
    assert result.status == "queued"


@pytest.mark.asyncio
async def test_queue_rejects_missing_chunk_set(monkeypatch):
    monkeypatch.setattr(
        service,
        "ensure_corpus_bm25_index_name_available_srvc",
        AsyncMock(return_value="policy bm25"),
    )
    monkeypatch.setattr(
        service,
        "get_corpus_chunk_set_snapshot_srvc",
        AsyncMock(side_effect=ValueError("Corpus chunk set not found")),
    )
    create = AsyncMock()
    monkeypatch.setattr(
        service.corpus_bm25_build_jobs_repo,
        "create_corpus_bm25_build_job",
        create,
    )

    with pytest.raises(
        service.CorpusBm25BuildJobNotFoundError,
        match="Corpus chunk set not found",
    ):
        await service.queue_corpus_bm25_build_job_srvc(
            CorpusBm25BuildJobQueueRequest(
                requested_artifact_name="policy bm25",
                corpus_chunk_set_id=CORPUS_CHUNK_SET_ID,
            ),
            SimpleNamespace(id=5),
            object(),
        )

    create.assert_not_awaited()


@pytest.mark.asyncio
async def test_queue_rejects_empty_chunk_set(monkeypatch):
    monkeypatch.setattr(
        service,
        "ensure_corpus_bm25_index_name_available_srvc",
        AsyncMock(return_value="policy bm25"),
    )
    monkeypatch.setattr(
        service,
        "get_corpus_chunk_set_snapshot_srvc",
        AsyncMock(return_value=_snapshot([])),
    )
    create = AsyncMock()
    monkeypatch.setattr(
        service.corpus_bm25_build_jobs_repo,
        "create_corpus_bm25_build_job",
        create,
    )

    with pytest.raises(
        service.CorpusBm25BuildJobConflictError,
        match="chunk set is empty",
    ):
        await service.queue_corpus_bm25_build_job_srvc(
            CorpusBm25BuildJobQueueRequest(
                requested_artifact_name="policy bm25",
                corpus_chunk_set_id=CORPUS_CHUNK_SET_ID,
            ),
            SimpleNamespace(id=5),
            object(),
        )

    create.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "current_snapshot",
    [
        _snapshot(revision=4),
        _snapshot(checksum="d" * 64),
        _snapshot([7]),
    ],
    ids=["revision", "checksum", "members"],
)
async def test_execution_rejects_stale_snapshot_without_building(
    monkeypatch,
    current_snapshot,
):
    job = SimpleNamespace(
        id=9,
        requested_artifact_name="policy bm25",
        corpus_id=11,
        chunking_profile_id=3,
        corpus_chunk_set_id=CORPUS_CHUNK_SET_ID,
        corpus_chunk_set_revision=CORPUS_CHUNK_SET_REVISION,
        corpus_chunk_set_checksum=CORPUS_CHUNK_SET_CHECKSUM,
        document_chunk_ids=[7, 12],
        cancel_requested=False,
        status="running",
    )
    monkeypatch.setattr(service.corpus_bm25_build_jobs_repo, "get_corpus_bm25_build_job_by_id", AsyncMock(return_value=job))
    monkeypatch.setattr(
        service,
        "get_corpus_chunk_set_snapshot_srvc",
        AsyncMock(return_value=current_snapshot),
    )
    failed = AsyncMock(side_effect=lambda value, detail, _session: SimpleNamespace(
        **{**value.__dict__, "status": "failed", "stage": "finished", "failure_detail": detail},
        requested_by_user_id=5,
        document_chunk_ids_checksum=CORPUS_CHUNK_SET_CHECKSUM,
        distinct_document_count=1,
        chunk_count=2,
        queued_at=datetime.now(timezone.utc),
        started_at=None,
        completed_at=datetime.now(timezone.utc),
        result_bm25_index_id=None,
    ))
    monkeypatch.setattr(service.corpus_bm25_build_jobs_repo, "mark_corpus_bm25_build_job_failed", failed)
    build = AsyncMock()
    monkeypatch.setattr(service, "build_corpus_bm25_index_from_snapshot_srvc", build)

    result = await service.execute_corpus_bm25_build_job_srvc(9, object())

    assert result.status == "failed"
    assert "changed since the job was queued" in result.failure_detail
    build.assert_not_awaited()


@pytest.mark.asyncio
async def test_parent_rollback_unlinks_deletes_and_marks_completed_child_failed(monkeypatch):
    job = CorpusBm25BuildJob(
        id=9,
        requested_artifact_name="policy lexical",
        corpus_id=11,
        chunking_profile_id=3,
        corpus_chunk_set_id=CORPUS_CHUNK_SET_ID,
        corpus_chunk_set_revision=CORPUS_CHUNK_SET_REVISION,
        corpus_chunk_set_checksum=CORPUS_CHUNK_SET_CHECKSUM,
        requested_by_user_id=5,
        document_chunk_ids=[7],
        document_chunk_ids_checksum=CORPUS_CHUNK_SET_CHECKSUM,
        distinct_document_count=1,
        chunk_count=1,
        status="completed",
        stage="finished",
        result_bm25_index_id=42,
    )
    metadata = SimpleNamespace(
        id=42,
        created_by_full_corpus_index_pipe_job_id=81,
    )
    calls = []
    monkeypatch.setattr(
        service.corpus_bm25_build_jobs_repo,
        "get_corpus_bm25_build_job_by_id",
        AsyncMock(return_value=job),
    )
    monkeypatch.setattr(
        service.corpus_bm25_indices_repo,
        "get_corpus_bm25_index_metadata_by_id",
        AsyncMock(return_value=metadata),
    )

    async def clear_result(current, _session):
        calls.append("clear")
        current.result_bm25_index_id = None
        return current

    async def delete_artifact(current, _session):
        calls.append(f"delete-{current.id}")

    async def rolled_back(current, detail, _session):
        calls.append("failed")
        current.status = "failed"
        current.failure_detail = detail
        return current

    monkeypatch.setattr(
        service.corpus_bm25_build_jobs_repo,
        "clear_corpus_bm25_build_job_result",
        clear_result,
        raising=False,
    )
    monkeypatch.setattr(
        service.corpus_bm25_build_jobs_repo,
        "mark_corpus_bm25_build_job_rolled_back",
        rolled_back,
        raising=False,
    )
    monkeypatch.setattr(
        service,
        "delete_corpus_bm25_index_srvc",
        delete_artifact,
        raising=False,
    )
    rollback = getattr(service, "rollback_parent_owned_corpus_bm25_job_srvc", None)

    assert rollback is not None
    result = await rollback(
        job_id=9,
        full_pipe_job_id=81,
        detail="Rolled back because dense index build failed: boom",
        session=object(),
    )

    assert calls == ["clear", "delete-42", "failed"]
    assert result.status == "failed"
    assert result.result_bm25_index_id is None


@pytest.mark.asyncio
async def test_parent_rollback_cancels_a_queued_child_before_parent_terminalizes(monkeypatch):
    job = CorpusBm25BuildJob(
        id=9,
        requested_artifact_name="policy lexical",
        corpus_id=11,
        chunking_profile_id=3,
        corpus_chunk_set_id=CORPUS_CHUNK_SET_ID,
        corpus_chunk_set_revision=CORPUS_CHUNK_SET_REVISION,
        corpus_chunk_set_checksum=CORPUS_CHUNK_SET_CHECKSUM,
        requested_by_user_id=5,
        document_chunk_ids=[7],
        document_chunk_ids_checksum=CORPUS_CHUNK_SET_CHECKSUM,
        distinct_document_count=1,
        chunk_count=1,
        status="queued",
        stage="queued",
    )

    async def cancel(current, _session):
        current.status = "cancelled"
        current.stage = "finished"
        return current

    async def append_detail(current, detail, _session):
        current.failure_detail = detail
        return current

    monkeypatch.setattr(
        service.corpus_bm25_build_jobs_repo,
        "get_corpus_bm25_build_job_by_id",
        AsyncMock(return_value=job),
    )
    monkeypatch.setattr(
        service.corpus_bm25_build_jobs_repo,
        "request_corpus_bm25_build_job_cancel",
        AsyncMock(side_effect=cancel),
    )
    monkeypatch.setattr(
        service.corpus_bm25_build_jobs_repo,
        "append_corpus_bm25_build_job_rollback_detail",
        AsyncMock(side_effect=append_detail),
    )
    monkeypatch.setattr(
        service.corpus_bm25_indices_repo,
        "get_corpus_bm25_index_metadata_by_full_pipe_job_id",
        AsyncMock(return_value=None),
    )

    result = await service.rollback_parent_owned_corpus_bm25_job_srvc(
        job_id=9,
        full_pipe_job_id=81,
        detail="Parent pipeline interrupted",
        session=object(),
    )

    assert result.status == "cancelled"
    assert result.failure_detail == "Parent pipeline interrupted"

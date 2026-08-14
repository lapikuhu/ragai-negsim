from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.repositories.corpus_bm25_indices_repo import document_chunk_ids_checksum
from app.schemas.corpus_bm25_build_jobs_schemas import CorpusBm25BuildJobQueueRequest
from app.services import corpus_bm25_build_jobs_service as service


@pytest.mark.asyncio
async def test_queue_snapshots_sorted_chunk_ids(monkeypatch):
    chunks = [
        SimpleNamespace(id=12, raw_document_id=2),
        SimpleNamespace(id=7, raw_document_id=1),
    ]
    monkeypatch.setattr(service, "_ensure_resources", AsyncMock())
    monkeypatch.setattr(
        service.document_chunks_repo,
        "list_corpus_document_chunks_for_profile",
        AsyncMock(return_value=chunks),
    )
    created = AsyncMock(side_effect=lambda value, _session: SimpleNamespace(
        id=9,
        cancel_requested=False,
        queued_at=service.datetime.now(service.timezone.utc),
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
            corpus_id=11,
            chunking_profile_id=3,
        ),
        SimpleNamespace(id=5),
        object(),
    )

    saved = created.await_args.args[0]
    assert saved.document_chunk_ids == [7, 12]
    assert saved.document_chunk_ids_checksum == document_chunk_ids_checksum([7, 12])
    assert result.status == "queued"


@pytest.mark.asyncio
async def test_execution_rejects_stale_snapshot_without_building(monkeypatch):
    job = SimpleNamespace(
        id=9,
        requested_artifact_name="policy bm25",
        corpus_id=11,
        chunking_profile_id=3,
        document_chunk_ids=[7, 12],
        cancel_requested=False,
        status="running",
    )
    monkeypatch.setattr(service.corpus_bm25_build_jobs_repo, "get_corpus_bm25_build_job_by_id", AsyncMock(return_value=job))
    monkeypatch.setattr(
        service.document_chunks_repo,
        "list_corpus_document_chunks_for_profile",
        AsyncMock(return_value=[SimpleNamespace(id=7)]),
    )
    failed = AsyncMock(side_effect=lambda value, detail, _session: SimpleNamespace(
        **{**value.__dict__, "status": "failed", "stage": "finished", "failure_detail": detail},
        requested_by_user_id=5,
        document_chunk_ids_checksum="a" * 64,
        distinct_document_count=1,
        chunk_count=2,
        queued_at=service.datetime.now(service.timezone.utc),
        started_at=None,
        completed_at=service.datetime.now(service.timezone.utc),
        result_bm25_index_id=None,
    ))
    monkeypatch.setattr(service.corpus_bm25_build_jobs_repo, "mark_corpus_bm25_build_job_failed", failed)
    build = AsyncMock()
    monkeypatch.setattr(service, "build_corpus_bm25_index_from_snapshot_srvc", build)

    result = await service.execute_corpus_bm25_build_job_srvc(9, object())

    assert result.status == "failed"
    assert "changed since the job was queued" in result.failure_detail
    build.assert_not_awaited()

from datetime import datetime, timezone

from app.models.corpus_bm25_build_jobs import CorpusBm25BuildJob
from app.schemas.corpus_bm25_build_jobs_schemas import (
    CorpusBm25BuildJobCreate,
    CorpusBm25BuildJobRead,
)
from app.repositories import corpus_bm25_build_jobs_repo as repository
import pytest


def test_bm25_build_job_create_preserves_private_snapshot():
    queued = CorpusBm25BuildJobCreate(
        requested_artifact_name="policy bm25",
        corpus_id=11,
        chunking_profile_id=3,
        requested_by_user_id=5,
        document_chunk_ids=[7, 12],
        document_chunk_ids_checksum="a" * 64,
        distinct_document_count=1,
        chunk_count=2,
        status="queued",
        stage="queued",
    )

    assert queued.document_chunk_ids == [7, 12]
    assert queued.status == "queued"


def test_bm25_build_job_read_omits_private_chunk_ids():
    assert "document_chunk_ids" not in CorpusBm25BuildJobRead.model_fields
    assert "document_chunk_ids_checksum" in CorpusBm25BuildJobRead.model_fields


def test_bm25_build_job_model_restricts_status_and_stage():
    constraint_sql = " ".join(
        str(item.sqltext)
        for item in CorpusBm25BuildJob.__table__.constraints
        if hasattr(item, "sqltext")
    )

    assert "queued" in constraint_sql
    assert "validating_snapshot" in constraint_sql
    assert "persisting_artifact" in constraint_sql


def test_bm25_build_job_read_exposes_result_and_timestamps():
    queued_at = datetime(2026, 8, 13, tzinfo=timezone.utc)
    read = CorpusBm25BuildJobRead(
        id=9,
        requested_artifact_name="policy bm25",
        corpus_id=11,
        chunking_profile_id=3,
        requested_by_user_id=5,
        document_chunk_ids_checksum="a" * 64,
        distinct_document_count=1,
        chunk_count=2,
        status="completed",
        stage="finished",
        cancel_requested=False,
        queued_at=queued_at,
        started_at=queued_at,
        completed_at=queued_at,
        result_bm25_index_id=42,
        failure_detail=None,
    )

    assert read.result_bm25_index_id == 42
    assert read.completed_at == queued_at


@pytest.mark.asyncio
async def test_queued_job_cancellation_is_immediate(monkeypatch):
    job = CorpusBm25BuildJob(
        id=9,
        requested_artifact_name="policy bm25",
        corpus_id=11,
        chunking_profile_id=3,
        requested_by_user_id=5,
        document_chunk_ids=[7],
        document_chunk_ids_checksum="a" * 64,
        distinct_document_count=1,
        chunk_count=1,
    )

    async def persist(_session, instance):
        return instance

    monkeypatch.setattr(repository, "commit_and_refresh", persist)
    result = await repository.request_corpus_bm25_build_job_cancel(job, object())

    assert result.status == "cancelled"
    assert result.stage == "finished"
    assert result.completed_at is not None


@pytest.mark.asyncio
async def test_terminal_job_cannot_be_cancelled():
    job = CorpusBm25BuildJob(
        id=9,
        requested_artifact_name="policy bm25",
        corpus_id=11,
        chunking_profile_id=3,
        requested_by_user_id=5,
        document_chunk_ids=[7],
        document_chunk_ids_checksum="a" * 64,
        distinct_document_count=1,
        chunk_count=1,
        status="completed",
        stage="finished",
    )

    with pytest.raises(ValueError, match="terminal"):
        await repository.request_corpus_bm25_build_job_cancel(job, object())

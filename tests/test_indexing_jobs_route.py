from types import SimpleNamespace

import pytest
from fastapi import Response

from app.schemas.indexing_jobs_schemas import IndexingJobCreate
from app.web.routes import indexing_jobs_route


@pytest.mark.asyncio
async def test_post_indexing_jobs_returns_202_and_starts_managed_task(monkeypatch):
    async def fake_queue(job_in, session):
        return SimpleNamespace(id=77, status="queued")

    def fake_start(job_id):
        return f"task-{job_id}"

    monkeypatch.setattr(indexing_jobs_route.indexing_jobs_service, "queue_indexing_job_srvc", fake_queue)
    monkeypatch.setattr(indexing_jobs_route.indexing_jobs_service, "start_indexing_job_task", fake_start)

    result = await indexing_jobs_route.create_indexing_job(
        job_in=IndexingJobCreate(
            corpus_id=1,
            chunking_profile_id=2,
            vector_store_id=3,
            embedding_model="mini-l6-v2",
            requested_index_name="policy-index",
        ),
        session=object(),
        _admin=SimpleNamespace(id=1),
    )

    assert result.status == "queued"
    assert result.id == 77


@pytest.mark.asyncio
async def test_get_active_indexing_job_returns_204_when_none_running(monkeypatch):
    async def fake_get_active(session):
        return None

    monkeypatch.setattr(indexing_jobs_route.indexing_jobs_service, "get_active_indexing_job_srvc", fake_get_active)

    response = await indexing_jobs_route.get_active_indexing_job(object(), SimpleNamespace(id=1))

    assert isinstance(response, Response)
    assert response.status_code == 204


@pytest.mark.asyncio
async def test_cancel_indexing_job_returns_updated_job(monkeypatch):
    async def fake_cancel(job_id, session):
        return SimpleNamespace(id=job_id, status="cancelled", stage="finished")

    monkeypatch.setattr(indexing_jobs_route.indexing_jobs_service, "cancel_indexing_job_srvc", fake_cancel)

    response = await indexing_jobs_route.cancel_indexing_job(
        job_id=44,
        session=object(),
        _admin=SimpleNamespace(id=1),
    )

    assert response.id == 44
    assert response.status == "cancelled"

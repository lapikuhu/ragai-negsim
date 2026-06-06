from types import SimpleNamespace

import pytest
from fastapi import BackgroundTasks, Response

from app.schemas.indexing_jobs_schemas import IndexingJobCreate
from app.web.routes import indexing_jobs_route


@pytest.mark.asyncio
async def test_post_indexing_jobs_returns_202_and_schedules_background_task(monkeypatch):
    scheduled = []

    class CapturingBackgroundTasks(BackgroundTasks):
        def add_task(self, func, *args, **kwargs):
            scheduled.append((func, args, kwargs))

    async def fake_queue(job_in, session):
        return SimpleNamespace(id=77, status="queued")

    async def fake_runner(job_id):
        return None

    monkeypatch.setattr(indexing_jobs_route.indexing_jobs_service, "queue_indexing_job_srvc", fake_queue)
    monkeypatch.setattr(indexing_jobs_route.indexing_jobs_service, "run_indexing_job_srvc", fake_runner)

    result = await indexing_jobs_route.create_indexing_job(
        job_in=IndexingJobCreate(
            corpus_id=1,
            chunking_profile_id=2,
            vector_store_id=3,
            embedding_model="mini-l6-v2",
            requested_index_name="policy-index",
        ),
        session=object(),
        background_tasks=CapturingBackgroundTasks(),
        _admin=SimpleNamespace(id=1),
    )

    assert result.status == "queued"
    assert scheduled == [(fake_runner, (77,), {})]


@pytest.mark.asyncio
async def test_get_active_indexing_job_returns_204_when_none_running(monkeypatch):
    async def fake_get_active(session):
        return None

    monkeypatch.setattr(indexing_jobs_route.indexing_jobs_service, "get_active_indexing_job_srvc", fake_get_active)

    response = await indexing_jobs_route.get_active_indexing_job(object(), SimpleNamespace(id=1))

    assert isinstance(response, Response)
    assert response.status_code == 204

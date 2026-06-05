from types import SimpleNamespace

import pytest
from fastapi import BackgroundTasks

from schemas.embeddings_schemas import (
    CorpusEmbeddingBuildQueued,
    CorpusEmbeddingBuildRequest,
)
from web.routes import corpus_route


@pytest.mark.asyncio
async def test_queue_embed_corpus_job_schedules_background_task(monkeypatch):
    scheduled = []

    class CapturingBackgroundTasks(BackgroundTasks):
        def add_task(self, func, *args, **kwargs):
            scheduled.append((func, args, kwargs))

    async def fake_queue(**kwargs):
        assert isinstance(kwargs["build_in"], CorpusEmbeddingBuildRequest)
        return CorpusEmbeddingBuildQueued(
            corpus_id=11,
            corpus_index_id=77,
            vector_store_id=5,
            chunking_profile_id=3,
            embedding_model="mini-l6-v2",
            embedding_dimensions=384,
            vector_namespace="corpus-index-77",
            status="building",
        )

    async def fake_runner(corpus_index_id):
        return None

    monkeypatch.setattr(corpus_route, "queue_corpus_embedding_build_srvc", fake_queue)
    monkeypatch.setattr(corpus_route, "run_queued_corpus_embedding_build_srvc", fake_runner)

    result = await corpus_route.queue_embed_corpus_job(
        corpus=SimpleNamespace(id=11),
        chunking_profile=SimpleNamespace(id=3),
        vector_store=SimpleNamespace(id=5),
        build_in=CorpusEmbeddingBuildRequest(
            name="my index",
            embedding_model="mini-l6-v2",
        ),
        session=object(),
        background_tasks=CapturingBackgroundTasks(),
        _admin=SimpleNamespace(id=1),
    )

    assert result.status == "building"
    assert scheduled == [(fake_runner, (77,), {})]

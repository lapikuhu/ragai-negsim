from types import SimpleNamespace

from app.core import dependencies
from app.schemas.embeddings_schemas import (
    CorpusEmbeddingBuildQueued,
    CorpusEmbeddingBuildRequest,
)
from app.web.routes import corpus_route


def test_queue_embed_corpus_job_schedules_background_task(
    monkeypatch,
    api_client,
    test_app,
    override_current_user,
    override_session,
    allow_roles,
):
    scheduled = []

    async def fake_queue(**kwargs):
        assert isinstance(kwargs["build_in"], CorpusEmbeddingBuildRequest)
        assert kwargs["corpus"].id == 11
        assert kwargs["chunking_profile"].id == 3
        assert kwargs["vector_store"].id == 5
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
        scheduled.append(corpus_index_id)

    override_current_user(username="admin", roles=["admin"])
    override_session()
    allow_roles("admin")
    test_app.dependency_overrides[dependencies.get_corpus_or_404] = (
        lambda: SimpleNamespace(id=11, created_by_user_id=1)
    )
    test_app.dependency_overrides[dependencies.get_chunking_profile_or_404] = (
        lambda: SimpleNamespace(id=3)
    )
    test_app.dependency_overrides[dependencies.get_vector_store_record_or_404] = (
        lambda: SimpleNamespace(id=5)
    )
    monkeypatch.setattr(corpus_route, "queue_corpus_embedding_build_srvc", fake_queue)
    monkeypatch.setattr(corpus_route, "run_queued_corpus_embedding_build_srvc", fake_runner)

    response = api_client.post(
        "/corpora/11/chunking-profiles/3/vector-stores/5/embed-jobs",
        json={"name": "my index", "embedding_model": "mini-l6-v2"},
    )

    assert response.status_code == 202
    assert response.json()["status"] == "building"
    assert scheduled == [77]

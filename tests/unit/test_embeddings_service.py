from types import SimpleNamespace

import pytest

from app.airag.embeddings.embeddings import list_supported_embedding_models
from app.schemas.embeddings_schemas import CorpusEmbeddingBuildRequest
from app.services import embeddings_service


def _forbid_bm25_creation(monkeypatch):
    from app.repositories import corpus_bm25_indices_repo

    async def fail_if_dense_build_creates_bm25(*_args, **_kwargs):
        raise AssertionError("Dense embedding builds must not create BM25 artifacts")

    monkeypatch.setattr(
        corpus_bm25_indices_repo,
        "create_corpus_bm25_index",
        fail_if_dense_build_creates_bm25,
    )


def _corpus(corpus_id=11):
    return SimpleNamespace(id=corpus_id, name="corpus", created_by_user_id=1)


def _chunking_profile(profile_id=3):
    return SimpleNamespace(id=profile_id, name="default", strategy="recursive", config={})


def _vector_store(vector_store_id=5, backend="chroma"):
    return SimpleNamespace(
        id=vector_store_id,
        name="store",
        backend=backend,
        collection_name="collection",
        table_name="vectors",
        path="./tmp_vectors",
    )


def _chunk(chunk_id, raw_document_id=7, content="chunk text"):
    return SimpleNamespace(
        id=chunk_id,
        raw_document_id=raw_document_id,
        chunking_profile_id=3,
        chunk_index=0,
        content=content,
        chunk_metadata={"source": "source.pdf"},
    )


def _build_request(**overrides):
    values = {
        "name": "my index",
        "embedding_model": "mini-l6-v2",
        "vector_namespace": None,
        "corpus_chunk_set_id": 21,
    }
    values.update(overrides)
    return CorpusEmbeddingBuildRequest(**values)


def _install_chunk_set(monkeypatch, chunks):
    ids = [chunk.id for chunk in chunks]
    snapshot = SimpleNamespace(
        chunk_set=SimpleNamespace(
            id=21,
            corpus_id=11,
            chunking_profile_id=3,
            revision=3,
            document_chunk_ids_checksum="c" * 64,
        ),
        document_chunk_ids=ids,
    )

    async def get_snapshot(chunk_set_id, session):
        assert chunk_set_id == 21
        return snapshot

    async def get_chunks(chunk_set_id, document_chunk_ids, session):
        assert chunk_set_id == 21
        assert document_chunk_ids == ids
        return chunks

    monkeypatch.setattr(embeddings_service, "get_corpus_chunk_set_snapshot_srvc", get_snapshot)
    monkeypatch.setattr(embeddings_service, "get_corpus_chunk_set_document_chunks_by_ids", get_chunks)


def test_embedding_catalog_uses_registry():
    models = list_supported_embedding_models()

    assert {model["name"] for model in models} >= {
        "mini-l6-v2",
        "bge-base",
        "text-embedding-3-small",
    }
    assert all(model["dimensionality"] > 0 for model in models)


@pytest.mark.asyncio
async def test_delete_vectors_from_pgvector_uses_external_vector_ids(monkeypatch):
    captured = []

    class FakeStore:
        async def adelete(self, ids):
            captured.extend(ids)

    async def fake_get_vector_store(**kwargs):
        return FakeStore()

    async def fake_enable_pgvector():
        return None

    monkeypatch.setattr(embeddings_service, "get_vector_store", fake_get_vector_store, raising=False)

    from app.airag.vector_stores import vector_stores as vector_stores_module

    monkeypatch.setattr(vector_stores_module, "enable_pgvector", fake_enable_pgvector)
    monkeypatch.setattr(vector_stores_module, "create_pg_engine", lambda engine: object())
    monkeypatch.setattr(vector_stores_module, "get_vector_store", fake_get_vector_store)

    await vector_stores_module.delete_vectors_from_vector_store(
        backend="pgvector",
        vector_ids=["corpus-index-7-chunk-10"],
        table_name="rag_chunks",
    )

    assert captured == ["corpus-index-7-chunk-10"]


def test_queued_embedding_build_response_contains_poll_links():
    from app.schemas.embeddings_schemas import CorpusEmbeddingBuildQueued

    queued = CorpusEmbeddingBuildQueued(
        corpus_id=11,
        corpus_index_id=77,
        vector_store_id=5,
        chunking_profile_id=3,
        corpus_chunk_set_id=21,
        embedding_model="mini-l6-v2",
        embedding_dimensions=384,
        vector_namespace="corpus-index-77",
        status="building",
    )

    assert queued.poll_url == "/corpus-indices/77"
    assert queued.indexed_chunks_url == "/corpus-indices/77/indexed-chunks"


@pytest.mark.asyncio
async def test_build_corpus_embeddings_creates_index_and_vector_refs(monkeypatch):
    _forbid_bm25_creation(monkeypatch)
    captured_docs = []
    captured_indexed_chunks = []
    captured_metadata = []
    created_index = None

    chunks = [_chunk(101, content="first"), _chunk(102, content="second")]
    _install_chunk_set(monkeypatch, chunks)

    async def fake_create_index(index_in, session):
        nonlocal created_index
        assert index_in.embedding_dimensions == 384
        created_index = SimpleNamespace(
            id=77,
            status=index_in.status,
            built_at=None,
            vector_namespace=index_in.vector_namespace,
            embedding_model=index_in.embedding_model,
            corpus_chunk_set_id=index_in.corpus_chunk_set_id,
            corpus_chunk_set_revision=index_in.corpus_chunk_set_revision,
            corpus_chunk_set_checksum=index_in.corpus_chunk_set_checksum,
            build_error="old failure",
        )
        return created_index

    async def fake_set_build_metadata(index, vector_namespace, session):
        captured_metadata.append((index.id, vector_namespace))
        index.vector_namespace = vector_namespace
        index.build_error = None
        return index

    async def fake_get_index(index_id, session):
        assert index_id == 77
        return created_index

    async def fake_mark_built(index, build_in, session):
        index.status = build_in.status
        index.built_at = build_in.built_at
        index.vector_namespace = build_in.vector_namespace
        index.build_error = None
        return index

    async def fake_store_docs(**kwargs):
        captured_docs.extend(kwargs["docs"])
        return kwargs["ids"]

    async def fake_bulk_create(indexed_chunks_in, session):
        captured_indexed_chunks.extend(indexed_chunks_in)
        return []

    monkeypatch.setattr(
        embeddings_service.corpus_indices_repo,
        "create_corpus_index",
        fake_create_index,
    )
    monkeypatch.setattr(
        embeddings_service.corpus_indices_repo,
        "set_corpus_index_build_metadata",
        fake_set_build_metadata,
    )
    monkeypatch.setattr(
        embeddings_service.corpus_indices_repo,
        "get_corpus_index_by_id",
        fake_get_index,
    )
    monkeypatch.setattr(
        embeddings_service.corpus_indices_repo,
        "mark_corpus_index_built",
        fake_mark_built,
    )
    monkeypatch.setattr(embeddings_service, "bulk_create_indexed_chunks", fake_bulk_create)

    from app.airag.embeddings import embeddings as embeddings_module
    from app.airag.vector_stores import vector_stores as vector_stores_module

    monkeypatch.setattr(
        embeddings_module,
        "choose_embedding_model",
        lambda model_name: (object(), {"dimensionality": 384}),
    )
    monkeypatch.setattr(vector_stores_module, "store_docs_to_vector_store", fake_store_docs)

    result = await embeddings_service.build_corpus_embeddings_srvc(
        corpus=_corpus(),
        chunking_profile=_chunking_profile(),
        vector_store=_vector_store(),
        build_in=_build_request(),
        session=object(),
    )

    assert result.status == "built"
    assert result.corpus_index_id == 77
    assert result.vector_namespace == "corpus-index-77"
    assert result.chunks_indexed == 2
    assert captured_metadata == [(77, "corpus-index-77")]
    assert [doc.page_content for doc in captured_docs] == ["first", "second"]
    assert captured_docs[0].metadata["corpus_id"] == 11
    assert captured_docs[0].metadata["document_chunk_id"] == 101
    assert captured_indexed_chunks[0].external_vector_id == "corpus-index-77-chunk-101"
    assert not any("bm25" in field.lower() for field in result.model_dump())


@pytest.mark.asyncio
async def test_build_corpus_embeddings_requires_chunks(monkeypatch):
    _install_chunk_set(monkeypatch, [])

    from app.airag.embeddings import embeddings as embeddings_module

    monkeypatch.setattr(
        embeddings_module,
        "choose_embedding_model",
        lambda model_name: (object(), {"dimensionality": 384}),
    )

    with pytest.raises(ValueError, match="empty"):
        await embeddings_service.build_corpus_embeddings_srvc(
            corpus=_corpus(),
            chunking_profile=_chunking_profile(),
            vector_store=_vector_store(),
            build_in=_build_request(),
            session=object(),
        )


@pytest.mark.asyncio
async def test_build_corpus_embeddings_marks_index_failed_on_vector_error(monkeypatch):
    marked_failed = []
    created_index = None

    _install_chunk_set(monkeypatch, [_chunk(101)])

    async def fake_create_index(index_in, session):
        nonlocal created_index
        created_index = SimpleNamespace(
            id=77,
            status=index_in.status,
            built_at=None,
            vector_namespace=index_in.vector_namespace,
            embedding_model=index_in.embedding_model,
            corpus_chunk_set_id=index_in.corpus_chunk_set_id,
            corpus_chunk_set_revision=index_in.corpus_chunk_set_revision,
            corpus_chunk_set_checksum=index_in.corpus_chunk_set_checksum,
            build_error=None,
        )
        return created_index

    async def fake_set_build_metadata(index, vector_namespace, session):
        index.vector_namespace = vector_namespace
        index.build_error = None
        return index

    async def fake_get_index(index_id, session):
        return created_index

    async def fake_mark_failed(index, build_error, session):
        marked_failed.append((index.id, build_error))
        index.status = "failed"
        index.build_error = build_error
        return index

    async def fake_store_docs(**kwargs):
        raise RuntimeError("vector store unavailable")

    monkeypatch.setattr(
        embeddings_service.corpus_indices_repo,
        "create_corpus_index",
        fake_create_index,
    )
    monkeypatch.setattr(
        embeddings_service.corpus_indices_repo,
        "set_corpus_index_build_metadata",
        fake_set_build_metadata,
    )
    monkeypatch.setattr(
        embeddings_service.corpus_indices_repo,
        "get_corpus_index_by_id",
        fake_get_index,
    )
    monkeypatch.setattr(embeddings_service.corpus_indices_repo, "mark_corpus_index_failed", fake_mark_failed)

    from app.airag.embeddings import embeddings as embeddings_module
    from app.airag.vector_stores import vector_stores as vector_stores_module

    monkeypatch.setattr(
        embeddings_module,
        "choose_embedding_model",
        lambda model_name: (object(), {"dimensionality": 384}),
    )
    monkeypatch.setattr(vector_stores_module, "store_docs_to_vector_store", fake_store_docs)

    with pytest.raises(RuntimeError, match="vector store unavailable"):
        await embeddings_service.build_corpus_embeddings_srvc(
            corpus=_corpus(),
            chunking_profile=_chunking_profile(),
            vector_store=_vector_store(),
            build_in=_build_request(),
            session=SimpleNamespace(rollback=lambda: None),
        )

    assert marked_failed == [(77, "vector store unavailable")]


@pytest.mark.asyncio
async def test_queue_corpus_embedding_build_creates_building_index(monkeypatch):
    captured_indices = []
    captured_metadata = []

    _install_chunk_set(monkeypatch, [_chunk(101), _chunk(102)])

    async def fake_create_index(index_in, session):
        captured_indices.append(index_in)
        return SimpleNamespace(
            id=77,
            status=index_in.status,
            built_at=None,
            vector_namespace=index_in.vector_namespace,
            build_error=None,
            corpus_chunk_set_id=index_in.corpus_chunk_set_id,
            corpus_chunk_set_revision=index_in.corpus_chunk_set_revision,
            corpus_chunk_set_checksum=index_in.corpus_chunk_set_checksum,
        )

    async def fake_set_build_metadata(index, vector_namespace, session):
        captured_metadata.append((index.id, vector_namespace))
        index.vector_namespace = vector_namespace
        index.build_error = None
        return index

    monkeypatch.setattr(embeddings_service.corpus_indices_repo, "create_corpus_index", fake_create_index)
    monkeypatch.setattr(embeddings_service.corpus_indices_repo, "set_corpus_index_build_metadata", fake_set_build_metadata)

    from app.airag.embeddings import embeddings as embeddings_module

    monkeypatch.setattr(
        embeddings_module,
        "choose_embedding_model",
        lambda model_name: (object(), {"dimensionality": 384}),
    )

    result = await embeddings_service.queue_corpus_embedding_build_srvc(
        corpus=_corpus(),
        chunking_profile=_chunking_profile(),
        vector_store=_vector_store(),
        build_in=_build_request(),
        session=object(),
    )

    assert result.status == "building"
    assert result.corpus_index_id == 77
    assert result.vector_namespace == "corpus-index-77"
    assert result.poll_url == "/corpus-indices/77"
    assert captured_indices[0].status == "building"
    assert captured_indices[0].embedding_dimensions == 384
    assert captured_metadata == [(77, "corpus-index-77")]


@pytest.mark.asyncio
async def test_queue_corpus_embedding_build_requires_chunks(monkeypatch):
    _install_chunk_set(monkeypatch, [])

    from app.airag.embeddings import embeddings as embeddings_module

    monkeypatch.setattr(
        embeddings_module,
        "choose_embedding_model",
        lambda model_name: (object(), {"dimensionality": 384}),
    )

    with pytest.raises(ValueError, match="empty"):
        await embeddings_service.queue_corpus_embedding_build_srvc(
            corpus=_corpus(),
            chunking_profile=_chunking_profile(),
            vector_store=_vector_store(),
            build_in=_build_request(),
            session=object(),
        )


@pytest.mark.asyncio
async def test_run_queued_corpus_embedding_build_loads_fresh_records_and_builds(monkeypatch, recording_async_session_factory):
    created_sessions = []
    index = SimpleNamespace(
        id=77,
        corpus_id=11,
        vector_store_id=5,
        chunking_profile_id=3,
        corpus_chunk_set_id=21,
        corpus_chunk_set_revision=3,
        corpus_chunk_set_checksum="c" * 64,
        status="building",
        embedding_model="mini-l6-v2",
        embedding_dimensions=384,
        vector_namespace="corpus-index-77",
        built_at=None,
        build_error=None,
    )

    def create_session():
        session = recording_async_session_factory()
        created_sessions.append(session)
        return session

    async def fake_get_index(index_id, session):
        assert index_id == 77
        assert session in created_sessions
        return index

    async def fake_get_corpus(corpus_id, session):
        return _corpus(corpus_id)

    async def fake_get_profile(profile_id, session):
        return _chunking_profile(profile_id)

    async def fake_get_store(vector_store_id, session):
        return _vector_store(vector_store_id)

    async def fake_build_existing(**kwargs):
        assert kwargs["index"] is index
        assert kwargs["session"] in created_sessions
        return "built-result"

    monkeypatch.setattr(embeddings_service, "AsyncSessionLocal", create_session)
    monkeypatch.setattr(embeddings_service.corpus_indices_repo, "get_corpus_index_by_id", fake_get_index)
    monkeypatch.setattr(embeddings_service.corpus_repo, "get_corpus_by_id", fake_get_corpus)
    monkeypatch.setattr(embeddings_service.chunking_profiles_repo, "get_chunking_profile_by_id", fake_get_profile)
    monkeypatch.setattr(embeddings_service.vector_stores_repo, "get_vector_store_by_id", fake_get_store)
    monkeypatch.setattr(embeddings_service, "_build_existing_corpus_index", fake_build_existing)

    result = await embeddings_service.run_queued_corpus_embedding_build_srvc(77)

    assert result == "built-result"
    assert len(created_sessions) == 1
    assert created_sessions[0].entered_sessions == [created_sessions[0]]
    assert created_sessions[0].exited_sessions == [created_sessions[0]]


@pytest.mark.asyncio
async def test_run_queued_corpus_embedding_build_marks_failed_on_error(monkeypatch, recording_async_session_factory):
    marked_failed = []
    index = SimpleNamespace(
        id=77,
        corpus_id=11,
        vector_store_id=5,
        chunking_profile_id=3,
        corpus_chunk_set_id=21,
        corpus_chunk_set_revision=3,
        corpus_chunk_set_checksum="c" * 64,
        status="building",
        embedding_model="mini-l6-v2",
        embedding_dimensions=384,
        vector_namespace="corpus-index-77",
        built_at=None,
        build_error=None,
    )

    async def fake_get_index(index_id, session):
        return index

    async def fake_get_corpus(corpus_id, session):
        return _corpus(corpus_id)

    async def fake_get_profile(profile_id, session):
        return _chunking_profile(profile_id)

    async def fake_get_store(vector_store_id, session):
        return _vector_store(vector_store_id)

    async def fake_build_existing(**kwargs):
        raise RuntimeError("vector store unavailable")

    async def fake_mark_failed(index_obj, build_error, session):
        marked_failed.append((index_obj, build_error))
        index_obj.status = "failed"
        index_obj.build_error = build_error
        return index_obj

    monkeypatch.setattr(embeddings_service, "AsyncSessionLocal", recording_async_session_factory)
    monkeypatch.setattr(embeddings_service.corpus_indices_repo, "get_corpus_index_by_id", fake_get_index)
    monkeypatch.setattr(embeddings_service.corpus_repo, "get_corpus_by_id", fake_get_corpus)
    monkeypatch.setattr(embeddings_service.chunking_profiles_repo, "get_chunking_profile_by_id", fake_get_profile)
    monkeypatch.setattr(embeddings_service.vector_stores_repo, "get_vector_store_by_id", fake_get_store)
    monkeypatch.setattr(embeddings_service, "_build_existing_corpus_index", fake_build_existing)
    monkeypatch.setattr(embeddings_service.corpus_indices_repo, "mark_corpus_index_failed", fake_mark_failed)

    with pytest.raises(RuntimeError, match="vector store unavailable"):
        await embeddings_service.run_queued_corpus_embedding_build_srvc(77)

    assert marked_failed == [(index, "vector store unavailable")]
    assert index.status == "failed"

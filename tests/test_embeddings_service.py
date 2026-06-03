from types import SimpleNamespace

import pytest

from airag.embeddings.embeddings import list_supported_embedding_models
from schemas.embeddings_schemas import CorpusEmbeddingBuildRequest
from services import embeddings_service


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
    }
    values.update(overrides)
    return CorpusEmbeddingBuildRequest(**values)


def test_embedding_catalog_uses_registry():
    models = list_supported_embedding_models()

    assert {model["name"] for model in models} >= {
        "mini-l6-v2",
        "bge-base",
        "text-embedding-3-small",
    }
    assert all(model["dimensionality"] > 0 for model in models)


@pytest.mark.asyncio
async def test_build_corpus_embeddings_creates_index_and_vector_refs(monkeypatch):
    captured_docs = []
    captured_indexed_chunks = []
    status_updates = []

    async def fake_list_chunks(corpus_id, chunking_profile_id, session):
        assert corpus_id == 11
        assert chunking_profile_id == 3
        return [_chunk(101, content="first"), _chunk(102, content="second")]

    async def fake_create_index(index_in, session):
        assert index_in.embedding_dimensions == 384
        return SimpleNamespace(
            id=77,
            status=index_in.status,
            built_at=None,
            vector_namespace=index_in.vector_namespace,
        )

    async def fake_update_status(index, status_in, session):
        status_updates.append(status_in.status)
        index.status = status_in.status
        return index

    async def fake_mark_built(index, build_in, session):
        index.status = build_in.status
        index.built_at = build_in.built_at
        index.vector_namespace = build_in.vector_namespace
        return index

    async def fake_store_docs(**kwargs):
        captured_docs.extend(kwargs["docs"])
        return kwargs["ids"]

    async def fake_bulk_create(indexed_chunks_in, session):
        captured_indexed_chunks.extend(indexed_chunks_in)
        return []

    monkeypatch.setattr(
        embeddings_service,
        "list_corpus_document_chunks_for_profile",
        fake_list_chunks,
    )
    monkeypatch.setattr(
        embeddings_service.corpus_indices_repo,
        "create_corpus_index",
        fake_create_index,
    )
    monkeypatch.setattr(
        embeddings_service.corpus_indices_repo,
        "update_corpus_index_status",
        fake_update_status,
    )
    monkeypatch.setattr(
        embeddings_service.corpus_indices_repo,
        "mark_corpus_index_built",
        fake_mark_built,
    )
    monkeypatch.setattr(embeddings_service, "bulk_create_indexed_chunks", fake_bulk_create)

    from airag.embeddings import embeddings as embeddings_module
    from airag.vector_stores import vector_stores as vector_stores_module

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
    assert status_updates == ["building"]
    assert [doc.page_content for doc in captured_docs] == ["first", "second"]
    assert captured_docs[0].metadata["corpus_id"] == 11
    assert captured_docs[0].metadata["document_chunk_id"] == 101
    assert captured_indexed_chunks[0].external_vector_id == "corpus-index-77-chunk-101"


@pytest.mark.asyncio
async def test_build_corpus_embeddings_requires_chunks(monkeypatch):
    async def fake_list_chunks(corpus_id, chunking_profile_id, session):
        return []

    monkeypatch.setattr(
        embeddings_service,
        "list_corpus_document_chunks_for_profile",
        fake_list_chunks,
    )

    from airag.embeddings import embeddings as embeddings_module

    monkeypatch.setattr(
        embeddings_module,
        "choose_embedding_model",
        lambda model_name: (object(), {"dimensionality": 384}),
    )

    with pytest.raises(ValueError, match="Chunk the corpus first"):
        await embeddings_service.build_corpus_embeddings_srvc(
            corpus=_corpus(),
            chunking_profile=_chunking_profile(),
            vector_store=_vector_store(),
            build_in=_build_request(),
            session=object(),
        )


@pytest.mark.asyncio
async def test_build_corpus_embeddings_marks_index_failed_on_vector_error(monkeypatch):
    status_updates = []

    async def fake_list_chunks(corpus_id, chunking_profile_id, session):
        return [_chunk(101)]

    async def fake_create_index(index_in, session):
        return SimpleNamespace(id=77, status=index_in.status, built_at=None)

    async def fake_update_status(index, status_in, session):
        status_updates.append(status_in.status)
        index.status = status_in.status
        return index

    async def fake_store_docs(**kwargs):
        raise RuntimeError("vector store unavailable")

    monkeypatch.setattr(
        embeddings_service,
        "list_corpus_document_chunks_for_profile",
        fake_list_chunks,
    )
    monkeypatch.setattr(
        embeddings_service.corpus_indices_repo,
        "create_corpus_index",
        fake_create_index,
    )
    monkeypatch.setattr(
        embeddings_service.corpus_indices_repo,
        "update_corpus_index_status",
        fake_update_status,
    )

    from airag.embeddings import embeddings as embeddings_module
    from airag.vector_stores import vector_stores as vector_stores_module

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

    assert status_updates == ["building", "failed"]

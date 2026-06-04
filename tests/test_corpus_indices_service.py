from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from schemas.corpus_indices_schemas import (
    CorpusIndexBuildComplete,
    CorpusIndexCopy,
    CorpusIndexCreate,
    CorpusIndexMetadataUpdate,
    CorpusIndexReadWithIds,
    CorpusIndexReadWithIndexedChunks,
    CorpusIndexStatusUpdate,
)
from services import corpus_indices_service


def _index(
    index_id=10,
    name="Corpus index",
    corpus_id=1,
    vector_store_id=2,
    chunking_profile_id=3,
    status="created",
    embedding_model="mini-l6-v2",
    embedding_dimensions=384,
    vector_namespace="corpus-index-10",
    built_at=None,
):
    now = datetime.now(timezone.utc)
    return SimpleNamespace(
        id=index_id,
        name=name,
        corpus_id=corpus_id,
        vector_store_id=vector_store_id,
        chunking_profile_id=chunking_profile_id,
        status=status,
        embedding_model=embedding_model,
        embedding_dimensions=embedding_dimensions,
        vector_namespace=vector_namespace,
        built_at=built_at,
        created_at=now,
        last_updated=now,
    )


def _read_with_ids(index, indexed_document_chunk_ids=None):
    return CorpusIndexReadWithIds(
        **index.__dict__,
        indexed_document_chunk_ids=indexed_document_chunk_ids or [],
    )


@pytest.mark.asyncio
async def test_create_corpus_index_validates_refs_and_returns_ids(monkeypatch):
    captured = []
    created = _index(index_id=12)

    async def fake_get_corpus_by_id(corpus_id, session):
        assert corpus_id == 1
        return SimpleNamespace(id=corpus_id)

    async def fake_get_vector_store_by_id(vector_store_id, session):
        assert vector_store_id == 2
        return SimpleNamespace(id=vector_store_id)

    async def fake_get_chunking_profile_by_id(profile_id, session):
        assert profile_id == 3
        return SimpleNamespace(id=profile_id)

    async def fake_create_corpus_index(index_in, session):
        captured.append(index_in)
        return created

    async def fake_to_corpus_index_read_with_ids(index, session):
        assert index is created
        return _read_with_ids(index, [101, 102])

    monkeypatch.setattr(corpus_indices_service.corpus_repo, "get_corpus_by_id", fake_get_corpus_by_id)
    monkeypatch.setattr(corpus_indices_service.vector_stores_repo, "get_vector_store_by_id", fake_get_vector_store_by_id)
    monkeypatch.setattr(corpus_indices_service.chunking_profiles_repo, "get_chunking_profile_by_id", fake_get_chunking_profile_by_id)
    monkeypatch.setattr(corpus_indices_service.corpus_indices_repo, "create_corpus_index", fake_create_corpus_index)
    monkeypatch.setattr(corpus_indices_service.corpus_indices_repo, "to_corpus_index_read_with_ids", fake_to_corpus_index_read_with_ids)

    index_in = CorpusIndexCreate(
        name="Negotiation index",
        corpus_id=1,
        vector_store_id=2,
        chunking_profile_id=3,
        embedding_model="mini-l6-v2",
    )
    result = await corpus_indices_service.create_corpus_index_srvc(index_in, object())

    assert result.id == 12
    assert result.indexed_document_chunk_ids == [101, 102]
    assert captured == [index_in]


@pytest.mark.asyncio
async def test_create_corpus_index_requires_existing_refs(monkeypatch):
    async def fake_get_corpus_by_id(corpus_id, session):
        return None

    monkeypatch.setattr(corpus_indices_service.corpus_repo, "get_corpus_by_id", fake_get_corpus_by_id)

    with pytest.raises(ValueError, match="Corpus not found"):
        await corpus_indices_service.create_corpus_index_srvc(
            CorpusIndexCreate(
                name="Missing corpus",
                corpus_id=99,
                vector_store_id=2,
                chunking_profile_id=3,
                embedding_model="mini-l6-v2",
            ),
            object(),
        )


@pytest.mark.asyncio
async def test_list_corpus_indices_passes_filters_and_converts(monkeypatch):
    captured = []
    indices = [_index(1), _index(2, status="built")]

    async def fake_list_corpus_indices(
        session,
        skip=0,
        limit=20,
        corpus_id=None,
        vector_store_id=None,
        chunking_profile_id=None,
        status=None,
        has_indexed_chunks=None,
    ):
        captured.append(
            (
                skip,
                limit,
                corpus_id,
                vector_store_id,
                chunking_profile_id,
                status,
                has_indexed_chunks,
            )
        )
        return indices

    async def fake_to_corpus_index_read_with_ids(index, session):
        return _read_with_ids(index, [index.id])

    monkeypatch.setattr(corpus_indices_service.corpus_indices_repo, "list_corpus_indices", fake_list_corpus_indices)
    monkeypatch.setattr(corpus_indices_service.corpus_indices_repo, "to_corpus_index_read_with_ids", fake_to_corpus_index_read_with_ids)

    result = await corpus_indices_service.list_corpus_indices_srvc(
        object(),
        skip=5,
        limit=10,
        corpus_id=1,
        vector_store_id=2,
        chunking_profile_id=3,
        status="built",
        has_indexed_chunks=True,
    )

    assert captured == [(5, 10, 1, 2, 3, "built", True)]
    assert [index.id for index in result] == [1, 2]
    assert result[0].indexed_document_chunk_ids == [1]


@pytest.mark.asyncio
async def test_get_corpus_index_converts_with_ids(monkeypatch):
    target = _index(index_id=7)

    async def fake_to_corpus_index_read_with_ids(index, session):
        assert index is target
        return _read_with_ids(index, [33])

    monkeypatch.setattr(corpus_indices_service.corpus_indices_repo, "to_corpus_index_read_with_ids", fake_to_corpus_index_read_with_ids)

    result = await corpus_indices_service.get_corpus_index_srvc(target, object())

    assert result.id == 7
    assert result.indexed_document_chunk_ids == [33]


@pytest.mark.asyncio
async def test_get_corpus_index_detail_returns_indexed_chunks(monkeypatch):
    target = _index(index_id=8)

    async def fake_to_corpus_index_read_with_indexed_chunks(index, session):
        assert index is target
        return CorpusIndexReadWithIndexedChunks(
            **index.__dict__,
            indexed_chunks=[
                {
                    "document_chunk_id": 44,
                    "external_vector_id": "external-44",
                    "created_at": datetime.now(timezone.utc),
                }
            ],
        )

    monkeypatch.setattr(
        corpus_indices_service.corpus_indices_repo,
        "to_corpus_index_read_with_indexed_chunks",
        fake_to_corpus_index_read_with_indexed_chunks,
    )

    result = await corpus_indices_service.get_corpus_index_detail_srvc(target, object())

    assert result.id == 8
    assert result.indexed_chunks[0].document_chunk_id == 44


@pytest.mark.asyncio
async def test_update_corpus_index_uses_metadata_update(monkeypatch):
    target = _index(index_id=9)
    captured = []

    async def fake_update_corpus_index(index, index_in, session):
        captured.append(index_in)
        index.name = index_in.name
        return index

    async def fake_to_corpus_index_read_with_ids(index, session):
        return _read_with_ids(index)

    monkeypatch.setattr(corpus_indices_service.corpus_indices_repo, "update_corpus_index", fake_update_corpus_index)
    monkeypatch.setattr(corpus_indices_service.corpus_indices_repo, "to_corpus_index_read_with_ids", fake_to_corpus_index_read_with_ids)

    result = await corpus_indices_service.update_corpus_index_srvc(
        target,
        CorpusIndexMetadataUpdate(name="Updated index"),
        object(),
    )

    assert result.name == "Updated index"
    assert captured[0].model_dump(exclude_unset=True) == {"name": "Updated index"}


@pytest.mark.asyncio
async def test_update_corpus_index_status_delegates(monkeypatch):
    target = _index(index_id=10)
    captured = []

    async def fake_update_corpus_index_status(index, status_in, session):
        captured.append(status_in)
        index.status = status_in.status
        return index

    async def fake_to_corpus_index_read_with_ids(index, session):
        return _read_with_ids(index)

    monkeypatch.setattr(corpus_indices_service.corpus_indices_repo, "update_corpus_index_status", fake_update_corpus_index_status)
    monkeypatch.setattr(corpus_indices_service.corpus_indices_repo, "to_corpus_index_read_with_ids", fake_to_corpus_index_read_with_ids)

    result = await corpus_indices_service.update_corpus_index_status_srvc(
        target,
        CorpusIndexStatusUpdate(status="building"),
        object(),
    )

    assert result.status == "building"
    assert captured == [CorpusIndexStatusUpdate(status="building")]


@pytest.mark.asyncio
async def test_mark_corpus_index_built_delegates(monkeypatch):
    target = _index(index_id=11, status="building")
    built_at = datetime.now(timezone.utc)
    captured = []

    async def fake_mark_corpus_index_built(index, build_in, session):
        captured.append(build_in)
        index.status = build_in.status
        index.built_at = build_in.built_at
        return index

    async def fake_to_corpus_index_read_with_ids(index, session):
        return _read_with_ids(index)

    monkeypatch.setattr(corpus_indices_service.corpus_indices_repo, "mark_corpus_index_built", fake_mark_corpus_index_built)
    monkeypatch.setattr(corpus_indices_service.corpus_indices_repo, "to_corpus_index_read_with_ids", fake_to_corpus_index_read_with_ids)

    result = await corpus_indices_service.mark_corpus_index_built_srvc(
        target,
        CorpusIndexBuildComplete(built_at=built_at, embedding_dimensions=384),
        object(),
    )

    assert result.status == "built"
    assert result.built_at == built_at
    assert captured == [
        CorpusIndexBuildComplete(
            status="built",
            built_at=built_at,
            embedding_dimensions=384,
            vector_namespace=None,
        )
    ]


@pytest.mark.asyncio
async def test_copy_corpus_index_validates_override_refs_and_delegates(monkeypatch):
    source = _index(index_id=12)
    captured = []

    async def fake_get_corpus_by_id(corpus_id, session):
        assert corpus_id == 20
        return SimpleNamespace(id=corpus_id)

    async def fake_get_vector_store_by_id(vector_store_id, session):
        assert vector_store_id == 30
        return SimpleNamespace(id=vector_store_id)

    async def fake_get_chunking_profile_by_id(profile_id, session):
        assert profile_id == 40
        return SimpleNamespace(id=profile_id)

    async def fake_copy_corpus_index(index, copy_in, session):
        captured.append((index, copy_in))
        return _index(
            index_id=13,
            name=copy_in.name,
            corpus_id=copy_in.corpus_id,
            vector_store_id=copy_in.vector_store_id,
            chunking_profile_id=copy_in.chunking_profile_id,
        )

    async def fake_to_corpus_index_read_with_ids(index, session):
        return _read_with_ids(index, [55])

    monkeypatch.setattr(corpus_indices_service.corpus_repo, "get_corpus_by_id", fake_get_corpus_by_id)
    monkeypatch.setattr(corpus_indices_service.vector_stores_repo, "get_vector_store_by_id", fake_get_vector_store_by_id)
    monkeypatch.setattr(corpus_indices_service.chunking_profiles_repo, "get_chunking_profile_by_id", fake_get_chunking_profile_by_id)
    monkeypatch.setattr(corpus_indices_service.corpus_indices_repo, "copy_corpus_index", fake_copy_corpus_index)
    monkeypatch.setattr(corpus_indices_service.corpus_indices_repo, "to_corpus_index_read_with_ids", fake_to_corpus_index_read_with_ids)

    copy_in = CorpusIndexCopy(
        name="Copied index",
        corpus_id=20,
        vector_store_id=30,
        chunking_profile_id=40,
    )
    result = await corpus_indices_service.copy_corpus_index_srvc(
        source,
        copy_in,
        object(),
    )

    assert result.id == 13
    assert result.indexed_document_chunk_ids == [55]
    assert captured == [(source, copy_in)]


@pytest.mark.asyncio
async def test_delete_corpus_index_delegates_and_propagates_guards(monkeypatch):
    target = _index(index_id=14)

    async def fake_delete_corpus_index(index, session):
        assert index is target
        raise ValueError("Cannot delete corpus index with indexed chunks")

    monkeypatch.setattr(corpus_indices_service.corpus_indices_repo, "delete_corpus_index", fake_delete_corpus_index)

    with pytest.raises(ValueError, match="Cannot delete corpus index"):
        await corpus_indices_service.delete_corpus_index_srvc(target, object())

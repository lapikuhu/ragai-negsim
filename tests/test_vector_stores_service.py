from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from app.schemas.vector_stores_schemas import (
    VectorStoreConnectionUpdate,
    VectorStoreCreate,
    VectorStoreReadWithIds,
    VectorStoreUpdate,
)
from app.services import vector_stores_service


def _vector_store(
    vector_store_id=10,
    name="Vector store",
    backend="chroma",
    connection_uri=None,
    collection_name="negotiation-corpus",
    table_name=None,
    path="./chroma_db",
    store_metadata=None,
):
    now = datetime.now(timezone.utc)
    return SimpleNamespace(
        id=vector_store_id,
        name=name,
        backend=backend,
        connection_uri=connection_uri,
        collection_name=collection_name,
        table_name=table_name,
        path=path,
        store_metadata=store_metadata or {"purpose": "tests"},
        created_at=now,
        last_updated=now,
    )


@pytest.mark.asyncio
async def test_create_vector_store_delegates_and_returns_ids(monkeypatch):
    captured = []
    created = _vector_store(vector_store_id=12)

    async def fake_create_vector_store(vector_store_in, session):
        captured.append(vector_store_in)
        return created

    async def fake_to_vector_store_read_with_ids(vector_store, session):
        assert vector_store is created
        return VectorStoreReadWithIds(
            **vector_store.__dict__,
            corpus_index_ids=[1, 2],
        )

    monkeypatch.setattr(
        vector_stores_service.vector_stores_repo,
        "create_vector_store",
        fake_create_vector_store,
    )
    monkeypatch.setattr(
        vector_stores_service.vector_stores_repo,
        "to_vector_store_read_with_ids",
        fake_to_vector_store_read_with_ids,
    )

    vector_store_in = VectorStoreCreate(
        name="Negotiation Chroma",
        backend="chroma",
        collection_name="negotiation",
        path="./chroma_db",
    )
    result = await vector_stores_service.create_vector_store_srvc(
        vector_store_in,
        object(),
    )

    assert result.id == 12
    assert result.corpus_index_ids == [1, 2]
    assert captured == [vector_store_in]


@pytest.mark.asyncio
async def test_list_vector_stores_passes_filters_and_converts(monkeypatch):
    captured = []
    vector_stores = [_vector_store(1), _vector_store(2, backend="faiss", path="./faiss_db")]

    async def fake_list_vector_stores(
        session,
        skip=0,
        limit=20,
        backend=None,
        has_indexes=None,
    ):
        captured.append((skip, limit, backend, has_indexes))
        return vector_stores

    async def fake_to_vector_store_read_with_ids(vector_store, session):
        return VectorStoreReadWithIds(**vector_store.__dict__, corpus_index_ids=[vector_store.id])

    monkeypatch.setattr(
        vector_stores_service.vector_stores_repo,
        "list_vector_stores",
        fake_list_vector_stores,
    )
    monkeypatch.setattr(
        vector_stores_service.vector_stores_repo,
        "to_vector_store_read_with_ids",
        fake_to_vector_store_read_with_ids,
    )

    result = await vector_stores_service.list_vector_stores_srvc(
        object(),
        skip=5,
        limit=10,
        backend="chroma",
        has_indexes=True,
    )

    assert captured == [(5, 10, "chroma", True)]
    assert [vector_store.id for vector_store in result] == [1, 2]
    assert result[0].corpus_index_ids == [1]


@pytest.mark.asyncio
async def test_get_vector_store_converts_with_ids(monkeypatch):
    target = _vector_store(vector_store_id=7)

    async def fake_to_vector_store_read_with_ids(vector_store, session):
        assert vector_store is target
        return VectorStoreReadWithIds(**vector_store.__dict__, corpus_index_ids=[30])

    monkeypatch.setattr(
        vector_stores_service.vector_stores_repo,
        "to_vector_store_read_with_ids",
        fake_to_vector_store_read_with_ids,
    )

    result = await vector_stores_service.get_vector_store_srvc(target, object())

    assert result.id == 7
    assert result.corpus_index_ids == [30]


@pytest.mark.asyncio
async def test_update_vector_store_delegates_and_converts(monkeypatch):
    target = _vector_store(vector_store_id=8)
    captured = []

    async def fake_update_vector_store(vector_store, vector_store_in, session):
        captured.append(vector_store_in)
        vector_store.name = vector_store_in.name
        return vector_store

    async def fake_to_vector_store_read_with_ids(vector_store, session):
        return VectorStoreReadWithIds(**vector_store.__dict__, corpus_index_ids=[])

    monkeypatch.setattr(
        vector_stores_service.vector_stores_repo,
        "update_vector_store",
        fake_update_vector_store,
    )
    monkeypatch.setattr(
        vector_stores_service.vector_stores_repo,
        "to_vector_store_read_with_ids",
        fake_to_vector_store_read_with_ids,
    )

    result = await vector_stores_service.update_vector_store_srvc(
        target,
        VectorStoreUpdate(name="Updated store"),
        object(),
    )

    assert result.name == "Updated store"
    assert captured[0].model_dump(exclude_unset=True) == {"name": "Updated store"}


@pytest.mark.asyncio
async def test_update_vector_store_connection_delegates_and_converts(monkeypatch):
    target = _vector_store(vector_store_id=9)
    captured = []

    async def fake_update_vector_store_connection(vector_store, connection_in, session):
        captured.append(connection_in)
        vector_store.path = connection_in.path
        return vector_store

    async def fake_to_vector_store_read_with_ids(vector_store, session):
        return VectorStoreReadWithIds(**vector_store.__dict__, corpus_index_ids=[])

    monkeypatch.setattr(
        vector_stores_service.vector_stores_repo,
        "update_vector_store_connection",
        fake_update_vector_store_connection,
    )
    monkeypatch.setattr(
        vector_stores_service.vector_stores_repo,
        "to_vector_store_read_with_ids",
        fake_to_vector_store_read_with_ids,
    )

    result = await vector_stores_service.update_vector_store_connection_srvc(
        target,
        VectorStoreConnectionUpdate(path="./new_chroma_db"),
        object(),
    )

    assert result.path == "./new_chroma_db"
    assert captured[0].model_dump(exclude_unset=True) == {"path": "./new_chroma_db"}


@pytest.mark.asyncio
async def test_delete_vector_store_delegates_and_propagates_guards(monkeypatch):
    target = _vector_store()

    async def fake_delete_vector_store(vector_store, session):
        assert vector_store is target
        raise ValueError("Cannot modify vector store referenced by corpus indexes")

    monkeypatch.setattr(
        vector_stores_service.vector_stores_repo,
        "delete_vector_store",
        fake_delete_vector_store,
    )

    with pytest.raises(ValueError, match="Cannot modify vector store referenced by corpus indexes"):
        await vector_stores_service.delete_vector_store_srvc(target, object())

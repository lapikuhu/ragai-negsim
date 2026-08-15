from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models.corpus_chunk_sets import (
    CorpusChunkSet,
    CorpusChunkSetDocumentChunkLink,
)
from app.repositories import corpus_chunk_sets_repo
from app.schemas.corpus_chunk_sets_schemas import (
    CorpusChunkSetCreate,
    CorpusChunkSetUpdate,
)
from app.services import corpus_chunk_sets_service


def test_chunk_set_create_requires_explicit_name_and_members():
    value = CorpusChunkSetCreate(
        name="August recursive set",
        corpus_id=4,
        chunking_profile_id=7,
        document_chunk_ids=[13, 11],
    )

    assert value.name == "August recursive set"
    assert value.document_chunk_ids == [13, 11]


def test_link_model_supports_one_chunk_in_multiple_sets():
    first = CorpusChunkSetDocumentChunkLink(
        corpus_chunk_set_id=1,
        document_chunk_id=9,
    )
    second = CorpusChunkSetDocumentChunkLink(
        corpus_chunk_set_id=2,
        document_chunk_id=9,
    )

    assert first.corpus_chunk_set_id != second.corpus_chunk_set_id


def _persisted_set() -> CorpusChunkSet:
    return CorpusChunkSet(
        id=3,
        corpus_id=4,
        name="August recursive set",
        chunking_profile_id=7,
        chunking_profile_name="Recursive",
        chunking_strategy="recursive",
        chunking_config={"chunk_size": 500},
        revision=1,
        document_chunk_ids_checksum=corpus_chunk_sets_repo.document_chunk_ids_checksum(
            [11, 12]
        ),
    )


class _Rows:
    def __init__(self, values):
        self._values = values

    def all(self):
        return self._values


@pytest.mark.asyncio
async def test_create_rejects_chunk_from_document_outside_corpus():
    chunk = SimpleNamespace(id=11, raw_document_id=99, chunking_profile_id=7)
    session = SimpleNamespace(
        exec=AsyncMock(side_effect=[_Rows([chunk]), _Rows([10, 12])])
    )

    with pytest.raises(ValueError, match="not associated with corpus"):
        await corpus_chunk_sets_service._load_valid_members(
            corpus_id=4,
            chunking_profile_id=7,
            document_chunk_ids=[11],
            session=session,
        )


@pytest.mark.asyncio
async def test_create_rejects_mixed_profile_membership():
    chunks = [
        SimpleNamespace(id=11, raw_document_id=10, chunking_profile_id=7),
        SimpleNamespace(id=12, raw_document_id=10, chunking_profile_id=8),
    ]
    session = SimpleNamespace(exec=AsyncMock(return_value=_Rows(chunks)))

    with pytest.raises(ValueError, match="chunking profile"):
        await corpus_chunk_sets_service._load_valid_members(
            corpus_id=4,
            chunking_profile_id=7,
            document_chunk_ids=[11, 12],
            session=session,
        )


@pytest.mark.asyncio
async def test_membership_update_increments_revision_and_checksum(monkeypatch):
    chunk_set = _persisted_set()
    session = SimpleNamespace()
    monkeypatch.setattr(
        corpus_chunk_sets_service.repo,
        "get_corpus_chunk_set_by_id",
        AsyncMock(return_value=chunk_set),
    )
    monkeypatch.setattr(
        corpus_chunk_sets_service,
        "_load_valid_members",
        AsyncMock(return_value=[]),
    )
    monkeypatch.setattr(
        corpus_chunk_sets_service.repo,
        "replace_corpus_chunk_set_members",
        AsyncMock(return_value=chunk_set),
    )
    monkeypatch.setattr(
        corpus_chunk_sets_service,
        "_to_read",
        AsyncMock(side_effect=lambda value, _session: value),
    )

    updated = await corpus_chunk_sets_service.update_corpus_chunk_set_srvc(
        3,
        CorpusChunkSetUpdate(document_chunk_ids=[11, 12, 13]),
        session,
    )

    assert updated.revision == 2
    assert updated.document_chunk_ids_checksum == (
        corpus_chunk_sets_repo.document_chunk_ids_checksum([11, 12, 13])
    )


@pytest.mark.asyncio
async def test_rename_does_not_increment_revision(monkeypatch):
    chunk_set = _persisted_set()
    session = SimpleNamespace(
        add=MagicMock(),
        commit=AsyncMock(),
        refresh=AsyncMock(),
    )
    monkeypatch.setattr(
        corpus_chunk_sets_service.repo,
        "get_corpus_chunk_set_by_id",
        AsyncMock(return_value=chunk_set),
    )
    monkeypatch.setattr(
        corpus_chunk_sets_service.repo,
        "get_corpus_chunk_set_by_name",
        AsyncMock(return_value=None),
    )
    monkeypatch.setattr(
        corpus_chunk_sets_service,
        "_to_read",
        AsyncMock(side_effect=lambda value, _session: value),
    )

    updated = await corpus_chunk_sets_service.update_corpus_chunk_set_srvc(
        3,
        CorpusChunkSetUpdate(name="Renamed set"),
        session,
    )

    assert updated.name == "Renamed set"
    assert updated.revision == 1


@pytest.mark.asyncio
async def test_delete_rejects_index_or_active_job_references(monkeypatch):
    monkeypatch.setattr(
        corpus_chunk_sets_service.repo,
        "get_corpus_chunk_set_by_id",
        AsyncMock(return_value=_persisted_set()),
    )
    monkeypatch.setattr(
        corpus_chunk_sets_service.repo,
        "corpus_chunk_set_has_index_references",
        AsyncMock(return_value=True),
    )

    with pytest.raises(ValueError, match="referenced by an index or active job"):
        await corpus_chunk_sets_service.delete_corpus_chunk_set_srvc(
            3, SimpleNamespace()
        )


@pytest.mark.asyncio
async def test_create_copies_profile_snapshot(monkeypatch):
    profile = SimpleNamespace(
        name="Recursive",
        strategy="recursive",
        config={"chunk_size": 500},
    )

    async def get(model, _identifier):
        return SimpleNamespace() if model.__name__ == "Corpus" else profile

    session = SimpleNamespace(get=get)
    captured = {}

    async def create(row, member_ids, _session, **_kwargs):
        row.id = 3
        captured.update(row=row, member_ids=member_ids)
        return row

    monkeypatch.setattr(
        corpus_chunk_sets_service.repo,
        "get_corpus_chunk_set_by_name",
        AsyncMock(return_value=None),
    )
    monkeypatch.setattr(
        corpus_chunk_sets_service,
        "_load_valid_members",
        AsyncMock(return_value=[]),
    )
    monkeypatch.setattr(
        corpus_chunk_sets_service.repo,
        "create_corpus_chunk_set",
        create,
    )
    monkeypatch.setattr(
        corpus_chunk_sets_service,
        "_to_read",
        AsyncMock(side_effect=lambda value, _session: value),
    )

    await corpus_chunk_sets_service.create_corpus_chunk_set_srvc(
        CorpusChunkSetCreate(
            name="August recursive set",
            corpus_id=4,
            chunking_profile_id=7,
            document_chunk_ids=[11, 12],
        ),
        session,
    )
    profile.config["chunk_size"] = 999

    assert captured["row"].chunking_profile_name == "Recursive"
    assert captured["row"].chunking_config == {"chunk_size": 500}
    assert captured["member_ids"] == [11, 12]

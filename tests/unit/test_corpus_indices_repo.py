import pytest
from sqlalchemy.dialects import postgresql

from app.models.corpus_indices import CorpusIndex
from app.repositories import corpus_indices_repo
from app.schemas.corpus_indices_schemas import CorpusIndexCopy, CorpusIndexCreate


class _EmptyResult:
    def all(self):
        return []


class _RecordingSession:
    statement = None

    async def exec(self, statement):
        self.statement = statement
        return _EmptyResult()


@pytest.mark.asyncio
async def test_built_simulation_candidates_are_unpaginated_and_corpus_scoped():
    session = _RecordingSession()

    result = await corpus_indices_repo.list_built_corpus_indices_for_corpus(
        44,
        session,
    )

    assert result == []
    statement = session.statement
    assert statement._limit_clause is None
    assert statement._offset_clause is None
    assert list(statement._order_by_clauses) == [CorpusIndex.id]
    sql = str(statement.compile(dialect=postgresql.dialect()))
    assert "corpusindex.corpus_id" in sql
    assert "corpusindex.status" in sql


@pytest.mark.asyncio
async def test_create_corpus_index_persists_exact_chunk_set_identity(monkeypatch):
    async def name_is_available(_name, _session, _exclude_index_id=None):
        return None

    async def persist(_session, index):
        return index

    monkeypatch.setattr(
        corpus_indices_repo,
        "ensure_corpus_index_name_available",
        name_is_available,
    )
    monkeypatch.setattr(corpus_indices_repo, "commit_and_refresh", persist)

    created = await corpus_indices_repo.create_corpus_index(
        CorpusIndexCreate(
            name="dense candidate",
            corpus_id=2,
            vector_store_id=4,
            chunking_profile_id=7,
            corpus_chunk_set_id=21,
            corpus_chunk_set_revision=3,
            corpus_chunk_set_checksum="a" * 64,
            embedding_model="bge-base",
        ),
        object(),
    )

    assert created.corpus_chunk_set_id == 21
    assert created.corpus_chunk_set_revision == 3
    assert created.corpus_chunk_set_checksum == "a" * 64


@pytest.mark.asyncio
async def test_copy_corpus_index_retains_source_chunk_set_identity(monkeypatch):
    async def name_is_available(_name, _session, _exclude_index_id=None):
        return None

    async def no_indexed_chunks(_index_id, _session):
        return []

    monkeypatch.setattr(
        corpus_indices_repo,
        "ensure_corpus_index_name_available",
        name_is_available,
    )
    monkeypatch.setattr(
        corpus_indices_repo,
        "get_corpus_index_indexed_chunks",
        no_indexed_chunks,
    )

    class RecordingSession:
        copied_index = None

        def add(self, instance):
            if isinstance(instance, CorpusIndex):
                instance.id = 44
                self.copied_index = instance

        async def flush(self):
            return None

        async def commit(self):
            return None

        async def refresh(self, _instance):
            return None

        async def rollback(self):
            return None

    source = CorpusIndex(
        id=9,
        name="dense source",
        corpus_id=2,
        vector_store_id=4,
        chunking_profile_id=7,
        corpus_chunk_set_id=21,
        corpus_chunk_set_revision=3,
        corpus_chunk_set_checksum="a" * 64,
        status="built",
        embedding_model="bge-base",
    )

    copied = await corpus_indices_repo.copy_corpus_index(
        source,
        CorpusIndexCopy(name="dense copy"),
        RecordingSession(),
    )

    assert copied.corpus_chunk_set_id == 21
    assert copied.corpus_chunk_set_revision == 3
    assert copied.corpus_chunk_set_checksum == "a" * 64

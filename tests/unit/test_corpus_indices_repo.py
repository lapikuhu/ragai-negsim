import pytest
from sqlalchemy.dialects import postgresql

from app.models.corpus_indices import CorpusIndex
from app.repositories import corpus_indices_repo


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


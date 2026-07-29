from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.corpus_bm25_indices import CorpusBm25Index
from app.repositories import corpus_bm25_indices_repo
from app.schemas.corpus_bm25_indices_schemas import CorpusBm25IndexCreate


@pytest_asyncio.fixture
async def corpus_bm25_async_engine(migrated_async_engine):
    async with migrated_async_engine.begin() as connection:
        await connection.run_sync(CorpusBm25Index.__table__.create, checkfirst=True)
    try:
        yield migrated_async_engine
    finally:
        async with migrated_async_engine.begin() as connection:
            await connection.run_sync(CorpusBm25Index.__table__.drop, checkfirst=True)


@pytest_asyncio.fixture
async def corpus_bm25_parent_rows(corpus_bm25_async_engine):
    suffix = uuid4().hex
    session_factory = async_sessionmaker(
        corpus_bm25_async_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    user_id = None
    corpus_id = None
    chunking_profile_id = None
    async with session_factory() as session:
        try:
            user_id = (await session.exec(text(
                "INSERT INTO \"user\" (username, hashed_password) VALUES "
                "(:username, :password) RETURNING id"
            ), params={"username": f"bm25-{suffix}", "password": "test"})).scalar_one()
            corpus_id = (await session.exec(text(
                "INSERT INTO corpus (name, created_by_user_id, created_at) VALUES "
                "(:name, :user_id, CURRENT_TIMESTAMP) RETURNING id"
            ), params={"name": f"bm25 corpus {suffix}", "user_id": user_id})).scalar_one()
            chunking_profile_id = (await session.exec(text(
                "INSERT INTO chunkingprofile (name, strategy, config, created_at, last_updated) "
                "VALUES (:name, 'recursive', '{}'::json, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP) "
                "RETURNING id"
            ), params={"name": f"bm25 profile {suffix}"})).scalar_one()
            await session.commit()
            yield {
                "suffix": suffix,
                "session_factory": session_factory,
                "corpus_id": corpus_id,
                "chunking_profile_id": chunking_profile_id,
            }
        finally:
            await session.rollback()
            if corpus_id is not None:
                await session.exec(
                    text("DELETE FROM corpusbm25index WHERE corpus_id = :id"),
                    params={"id": corpus_id},
                )
                await session.exec(
                    text("DELETE FROM corpus WHERE id = :id"),
                    params={"id": corpus_id},
                )
            if chunking_profile_id is not None:
                await session.exec(
                    text("DELETE FROM chunkingprofile WHERE id = :id"),
                    params={"id": chunking_profile_id},
                )
            if user_id is not None:
                await session.exec(
                    text('DELETE FROM "user" WHERE id = :id'),
                    params={"id": user_id},
                )
            await session.commit()


@pytest.mark.asyncio
@pytest.mark.integration
@pytest.mark.postgres
async def test_postgres_bm25_repository_reads_metadata_without_artifact_and_fetches_binary_on_demand(
    corpus_bm25_parent_rows,
):
    parent_rows = corpus_bm25_parent_rows
    session_factory = parent_rows["session_factory"]
    async with session_factory() as session:
        created = await corpus_bm25_indices_repo.create_corpus_bm25_index(
            CorpusBm25IndexCreate(
                name=f"bm25 index {parent_rows['suffix']}",
                corpus_id=parent_rows["corpus_id"],
                chunking_profile_id=parent_rows["chunking_profile_id"],
                document_chunk_ids=[3, 2, 1],
            ),
            session,
        )
        created = await corpus_bm25_indices_repo.mark_corpus_bm25_index_building(
            created.id, session
        )
        created = await corpus_bm25_indices_repo.mark_corpus_bm25_index_built(
            created.id,
            artifact=b"compressed-artifact",
            document_chunk_ids=[3, 2, 1],
            session=session,
        )

        metadata = await corpus_bm25_indices_repo.get_corpus_bm25_index_metadata_by_id(
            created.id, session
        )
        artifact = await corpus_bm25_indices_repo.get_corpus_bm25_index_artifact_by_id(
            created.id, session
        )
        created = await corpus_bm25_indices_repo.mark_corpus_bm25_index_retired(
            created.id, session
        )
        await corpus_bm25_indices_repo.delete_corpus_bm25_index(created.id, session)

        assert metadata is not None
        assert "artifact" not in metadata.model_dump()
        assert metadata.status == "built"
        assert artifact == b"compressed-artifact"
        assert await corpus_bm25_indices_repo.get_corpus_bm25_index_metadata_by_id(created.id, session) is None


@pytest.mark.asyncio
@pytest.mark.integration
@pytest.mark.postgres
async def test_postgres_stale_bm25_object_cannot_overwrite_cancelled_row(
    corpus_bm25_parent_rows,
):
    parent_rows = corpus_bm25_parent_rows
    session_factory = parent_rows["session_factory"]
    async with session_factory() as first_session:
        created = await corpus_bm25_indices_repo.create_corpus_bm25_index(
            CorpusBm25IndexCreate(
                name=f"bm25 stale {parent_rows['suffix']}",
                corpus_id=parent_rows["corpus_id"],
                chunking_profile_id=parent_rows["chunking_profile_id"],
                document_chunk_ids=[1],
            ),
            first_session,
        )
        stale_building = await corpus_bm25_indices_repo.mark_corpus_bm25_index_building(
            created.id, first_session
        )

        async with session_factory() as second_session:
            cancelled = await corpus_bm25_indices_repo.mark_corpus_bm25_index_cancelled(
                stale_building.id,
                "cancelled elsewhere",
                second_session,
            )
            assert cancelled.status == "cancelled"

        with pytest.raises(ValueError, match="Invalid corpus BM25 index status transition"):
            await corpus_bm25_indices_repo.mark_corpus_bm25_index_built(
                stale_building.id,
                artifact=b"later",
                document_chunk_ids=[1],
                session=first_session,
            )

        metadata = await corpus_bm25_indices_repo.get_corpus_bm25_index_metadata_by_id(
            stale_building.id,
            first_session,
        )
        assert metadata is not None
        assert metadata.status == "cancelled"

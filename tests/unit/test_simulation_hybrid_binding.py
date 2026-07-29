import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

import app.models  # noqa: F401
from app.models.corpus_bm25_indices import CorpusBm25Index
from app.models.corpus_indices import CorpusIndex
from app.models.rag_profiles import RagProfile
from app.models.simulations import Simulation
from app.repositories import simulations_repo
from app.schemas.simulations_schemas import SimulationCreate, SimulationUpdate
from app.services import simulations_service


@pytest_asyncio.fixture
async def db_session():
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as connection:
        await connection.run_sync(SQLModel.metadata.create_all)
    async with AsyncSession(engine, expire_on_commit=False) as session:
        yield session
    await engine.dispose()


@pytest.mark.asyncio
async def test_simulation_create_update_and_read_persist_explicit_bm25_binding(
    db_session,
):
    profile_config = {
        "bm25_weight": 1.0,
        "dense_k": 4,
        "bm25_k": 7,
        "final_top_k": 4,
    }

    db_session.add(
        RagProfile(
            id=3,
            name="BM25 runtime profile",
            strategy="crag",
            config=profile_config,
            created_by_user_id=1,
        )
    )
    db_session.add(
        CorpusIndex(
            id=17,
            name="Dense snapshot",
            corpus_id=2,
            vector_store_id=9,
            chunking_profile_id=5,
            status="built",
            embedding_model="dense-model",
        )
    )
    for index_id in (41, 42):
        db_session.add(
            CorpusBm25Index(
                id=index_id,
                name=f"BM25 snapshot {index_id}",
                corpus_id=2,
                chunking_profile_id=5,
                status="built",
                artifact=b"trusted-artifact",
                document_count=2,
                document_chunk_ids_checksum="a" * 64,
                compressed_artifact_checksum="b" * 64,
            )
        )
    await db_session.commit()

    simulation = await simulations_repo.create_simulation(
        SimulationCreate(
            name="BM25-only negotiation",
            user_id_owner=1,
            corpus_id=2,
            corpus_index_id=None,
            bm25_index_id=41,
            rag_profile_id=3,
        ),
        db_session,
    )
    read = simulations_service._read_simulation(simulation)

    assert simulation.corpus_index_id is None
    assert simulation.bm25_index_id == 41
    assert read.corpus_index_id is None
    assert read.bm25_index_id == 41
    persisted_profile = await db_session.get(RagProfile, 3)
    assert persisted_profile.config == profile_config
    assert "bm25_index_id" not in persisted_profile.config

    updated = await simulations_repo.update_simulation(
        simulation,
        SimulationUpdate(corpus_index_id=17, bm25_index_id=42),
        db_session,
    )

    assert updated.corpus_index_id == 17
    assert updated.bm25_index_id == 42


def test_manual_simulation_schema_has_nullable_dense_and_bm25_foreign_key():
    table = Simulation.__table__
    bm25_targets = {
        foreign_key.target_fullname
        for foreign_key in table.c.bm25_index_id.foreign_keys
    }

    assert table.c.corpus_index_id.nullable is True
    assert table.c.bm25_index_id.nullable is True
    assert bm25_targets == {"corpusbm25index.id"}

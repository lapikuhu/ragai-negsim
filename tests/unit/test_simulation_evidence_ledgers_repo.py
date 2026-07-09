import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models import (  # noqa: F401
    chunking_profiles,
    corpus,
    corpus_indices,
    counterpart_personas,
    document_chunks,
    indexed_chunks,
    indexing_job_warnings,
    indexing_jobs,
    knowledge_graph_build_jobs,
    knowledge_graph_indices,
    prompts,
    rag_profiles,
    raw_documents,
    scenarios,
    sessions,
    simulations,
    user_roles,
    users,
    vector_stores,
)
from app.models.simulation_evidence_ledgers import SimulationEvidenceLedger
from app.models.simulations import Simulation
from app.repositories import simulation_evidence_ledgers_repo
from app.schemas.evidence_ledger_schemas import SimulationEvidenceLedgerCreate


@pytest_asyncio.fixture
async def db_session():
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    async with AsyncSession(engine, expire_on_commit=False) as session:
        yield session
    await engine.dispose()


@pytest_asyncio.fixture
async def simulation_factory(db_session):
    async def create_simulation() -> Simulation:
        simulation = Simulation(
            name="Evidence ledger simulation",
            user_id_owner=1,
            corpus_id=1,
            corpus_index_id=1,
            rag_profile_id=1,
        )
        db_session.add(simulation)
        await db_session.commit()
        await db_session.refresh(simulation)
        return simulation

    return create_simulation


@pytest.mark.asyncio
async def test_create_and_list_evidence_ledgers_orders_by_turn_and_sequence(
    db_session,
    simulation_factory,
):
    simulation = await simulation_factory()
    first = SimulationEvidenceLedgerCreate(
        simulation_id=simulation.id,
        turn_index=2,
        agent_name="coach",
        sequence=2,
        visibility_level="debug",
        pipeline={"steps": [{"name": "generate", "status": "success"}]},
        sources=[],
        quality_checks=[],
        model={"provider": "openai", "name": "gpt-test"},
        token_usage={"total_tokens": 12},
        output_summary={"kind": "coach_advice"},
        raw_debug={"event_log": ["coach:generated_advice"]},
    )
    second = SimulationEvidenceLedgerCreate(
        simulation_id=simulation.id,
        turn_index=1,
        agent_name="counterpart",
        sequence=1,
        visibility_level="debug",
        pipeline={"steps": [{"name": "generate", "status": "success"}]},
        sources=[],
        quality_checks=[],
        model={},
        token_usage={},
        output_summary={"kind": "counterpart_response"},
        raw_debug={},
    )

    await simulation_evidence_ledgers_repo.create_evidence_ledger(first, db_session)
    await simulation_evidence_ledgers_repo.create_evidence_ledger(second, db_session)

    rows = await simulation_evidence_ledgers_repo.list_evidence_ledgers_for_simulation(
        simulation.id,
        db_session,
    )

    assert [row.agent_name for row in rows] == ["counterpart", "coach"]
    assert [row.turn_index for row in rows] == [1, 2]
    assert isinstance(rows[0], SimulationEvidenceLedger)

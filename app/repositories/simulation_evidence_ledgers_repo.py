from sqlmodel import delete, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.simulation_evidence_ledgers import SimulationEvidenceLedger
from app.repositories.helpers import commit_and_refresh
from app.schemas.evidence_ledger_schemas import SimulationEvidenceLedgerCreate


async def create_evidence_ledger(
    ledger_in: SimulationEvidenceLedgerCreate,
    session: AsyncSession,
) -> SimulationEvidenceLedger:
    ledger = SimulationEvidenceLedger(**ledger_in.model_dump())
    return await commit_and_refresh(session, ledger)


async def list_evidence_ledgers_for_simulation(
    simulation_id: int,
    session: AsyncSession,
) -> list[SimulationEvidenceLedger]:
    statement = (
        select(SimulationEvidenceLedger)
        .where(SimulationEvidenceLedger.simulation_id == simulation_id)
        .order_by(
            SimulationEvidenceLedger.turn_index.asc(),
            SimulationEvidenceLedger.sequence.asc(),
            SimulationEvidenceLedger.id.asc(),
        )
    )
    result = await session.exec(statement)
    return list(result.all())


async def delete_evidence_ledgers_for_simulation(
    simulation_id: int,
    session: AsyncSession,
) -> None:
    await session.exec(
        delete(SimulationEvidenceLedger).where(
            SimulationEvidenceLedger.simulation_id == simulation_id
        )
    )
    await session.commit()

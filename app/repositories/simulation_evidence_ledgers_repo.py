from sqlmodel import delete, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.simulation_evidence_ledgers import SimulationEvidenceLedger
from app.repositories.helpers import commit_and_refresh
from app.schemas.evidence_ledger_schemas import SimulationEvidenceLedgerCreate


async def create_evidence_ledger(
    ledger_in: SimulationEvidenceLedgerCreate,
    session: AsyncSession,
) -> SimulationEvidenceLedger:
    """
    Create a new evidence ledger entry in the database.
    Args:
        ledger_in (SimulationEvidenceLedgerCreate): The data for the new 
            evidence ledger entry.
        session (AsyncSession): The database session to use for the operation.
    Returns:
        SimulationEvidenceLedger: The newly created evidence ledger entry.
    """
    ledger = SimulationEvidenceLedger(**ledger_in.model_dump())
    return await commit_and_refresh(session, ledger)


async def list_evidence_ledgers_for_simulation(
    simulation_id: int,
    session: AsyncSession,
) -> list[SimulationEvidenceLedger]:
    """
    List all evidence ledger entries for a given simulation.
    Args:
        simulation_id (int): The ID of the simulation.
        session (AsyncSession): The database session to use for the operation.
    Returns:
        list[SimulationEvidenceLedger]: A list of evidence ledger entries 
        for the simulation.
    """
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
    """
    Delete all evidence ledger entries for a given simulation.
    Args:
        simulation_id (int): The ID of the simulation.
        session (AsyncSession): The database session to use for the operation.
    Returns:
        None
    """
    await session.exec(
        delete(SimulationEvidenceLedger).where(
            SimulationEvidenceLedger.simulation_id == simulation_id
        )
    )
    await session.commit()

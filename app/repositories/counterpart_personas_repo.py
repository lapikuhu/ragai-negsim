from models.counterpart_personas import CounterPartPersonas
from models.simulations import Simulation
from repositories.helpers import commit_and_refresh, commit_delete, utc_now
from schemas.counterpart_personas_schemas import (
    CounterpartPersonaCopy,
    CounterpartPersonaCreate,
    CounterpartPersonaReadWithIds,
    CounterpartPersonaUpdate,
)
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession


async def counterpart_persona_has_simulations(
    persona_id: int,
    session: AsyncSession,
) -> bool:
    result = await session.exec(
        select(Simulation.id)
        .where(Simulation.counter_part_side_persona_id == persona_id)
        .limit(1)
    )
    return result.first() is not None


async def ensure_counterpart_persona_unused(
    persona: CounterPartPersonas,
    session: AsyncSession,
) -> None:
    if persona.id is None:
        raise ValueError("Counterpart persona must be persisted before this operation")

    if await counterpart_persona_has_simulations(persona.id, session):
        raise ValueError("Cannot modify counterpart persona that has been used in simulations")


async def get_counterpart_persona_by_id(
    persona_id: int,
    session: AsyncSession,
) -> CounterPartPersonas | None:
    return await session.get(CounterPartPersonas, persona_id)


async def get_counterpart_persona_by_name(
    name: str,
    session: AsyncSession,
) -> CounterPartPersonas | None:
    result = await session.exec(select(CounterPartPersonas).where(CounterPartPersonas.name == name))
    return result.first()


async def ensure_counterpart_persona_name_available(
    name: str,
    session: AsyncSession,
    exclude_persona_id: int | None = None,
) -> None:
    existing_persona = await get_counterpart_persona_by_name(name, session)
    if existing_persona is None:
        return

    if exclude_persona_id is not None and existing_persona.id == exclude_persona_id:
        return

    raise ValueError("Counterpart persona name already exists")


async def list_counterpart_personas(
    session: AsyncSession,
    skip: int = 0,
    limit: int = 20,
    created_by_user_id: int | None = None,
    name_contains: str | None = None,
    used: bool | None = None,
) -> list[CounterPartPersonas]:
    statement = select(CounterPartPersonas)

    if created_by_user_id is not None:
        statement = statement.where(CounterPartPersonas.created_by_user_id == created_by_user_id)
    if name_contains is not None:
        statement = statement.where(CounterPartPersonas.name.contains(name_contains))
    if used is not None:
        used_subquery = (
            select(Simulation.counter_part_side_persona_id)
            .where(Simulation.counter_part_side_persona_id.is_not(None))
            .distinct()
        )
        if used:
            statement = statement.where(CounterPartPersonas.id.in_(used_subquery))
        else:
            statement = statement.where(CounterPartPersonas.id.not_in(used_subquery))

    statement = statement.offset(skip).limit(limit)
    result = await session.exec(statement)
    return list(result.all())


async def get_counterpart_persona_simulation_ids(
    persona_id: int,
    session: AsyncSession,
) -> list[int]:
    result = await session.exec(
        select(Simulation.id).where(Simulation.counter_part_side_persona_id == persona_id)
    )
    return [simulation_id for simulation_id in result.all() if simulation_id is not None]


async def to_counterpart_persona_read_with_ids(
    persona: CounterPartPersonas,
    session: AsyncSession,
) -> CounterpartPersonaReadWithIds:
    if persona.id is None:
        raise ValueError("Counterpart persona must be persisted before relationship ids can be loaded")

    return CounterpartPersonaReadWithIds(
        **persona.model_dump(),
        simulation_ids=await get_counterpart_persona_simulation_ids(persona.id, session),
    )


async def create_counterpart_persona(
    persona_in: CounterpartPersonaCreate,
    session: AsyncSession,
) -> CounterPartPersonas:
    await ensure_counterpart_persona_name_available(persona_in.name, session)
    persona = CounterPartPersonas(**persona_in.model_dump())
    return await commit_and_refresh(session, persona)


async def update_counterpart_persona(
    persona: CounterPartPersonas,
    persona_in: CounterpartPersonaUpdate,
    session: AsyncSession,
) -> CounterPartPersonas:
    await ensure_counterpart_persona_unused(persona, session)
    update_data = persona_in.model_dump(exclude_unset=True)

    if "name" in update_data and update_data["name"] is not None:
        await ensure_counterpart_persona_name_available(update_data["name"], session, persona.id)

    for field_name, value in update_data.items():
        setattr(persona, field_name, value)

    persona.last_updated = utc_now()
    return await commit_and_refresh(session, persona)


async def copy_counterpart_persona(
    source_persona: CounterPartPersonas,
    copy_in: CounterpartPersonaCopy,
    created_by_user_id: int,
    session: AsyncSession,
) -> CounterPartPersonas:
    await ensure_counterpart_persona_name_available(copy_in.name, session)
    persona = CounterPartPersonas(
        name=copy_in.name,
        description=(
            copy_in.description
            if copy_in.description is not None
            else source_persona.description
        ),
        created_by_user_id=created_by_user_id,
    )
    return await commit_and_refresh(session, persona)


async def delete_counterpart_persona(
    persona: CounterPartPersonas,
    session: AsyncSession,
) -> None:
    await ensure_counterpart_persona_unused(persona, session)
    await commit_delete(session, persona)
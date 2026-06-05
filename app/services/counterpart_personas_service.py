from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.counterpart_personas import CounterPartPersonas
from app.models.users import User
from app.repositories import counterpart_personas_repo
from app.schemas.counterpart_personas_schemas import (
    CounterpartPersonaCopy,
    CounterpartPersonaCopyRequest,
    CounterpartPersonaCreate,
    CounterpartPersonaCreateRequest,
    CounterpartPersonaReadWithIds,
    CounterpartPersonaUpdate,
    CounterpartPersonaUpdateRequest,
)


async def create_counterpart_persona_srvc(
    persona_data: CounterpartPersonaCreateRequest,
    session: AsyncSession,
    current_user: User,
) -> CounterpartPersonaReadWithIds:
    """
    Create a new counterpart persona service function.
    Args:
        persona_data: The data for the new counterpart persona.
        session: The database session dependency.
        current_user: The current user dependency.
    Returns:
        The created counterpart persona with related simulation IDs.
    """
    persona_in = CounterpartPersonaCreate(
        **persona_data.model_dump(),
        created_by_user_id=current_user.id,
    )
    persona = await counterpart_personas_repo.create_counterpart_persona(persona_in, session)
    return await counterpart_personas_repo.to_counterpart_persona_read_with_ids(persona, session)


async def list_counterpart_personas_srvc(
    session: AsyncSession,
    skip: int = 0,
    limit: int = 20,
    created_by_user_id: int | None = None,
    name_contains: str | None = None,
    used: bool | None = None,
) -> list[CounterpartPersonaReadWithIds]:
    """
    List counterpart personas service function.
    Args:
        session: The database session dependency.
        skip: The number of records to skip for pagination.
        limit: The maximum number of records to return.
        created_by_user_id: Filter by the ID of the user who created the 
            counterpart persona.
        name_contains: Filter by a substring in the persona's name.
        used: Filter by whether the persona has been used.
    Returns:
        A list of counterpart personas with related simulation IDs.
    """
    personas = await counterpart_personas_repo.list_counterpart_personas(
        session=session,
        skip=skip,
        limit=limit,
        created_by_user_id=created_by_user_id,
        name_contains=name_contains,
        used=used,
    )
    return [
        await counterpart_personas_repo.to_counterpart_persona_read_with_ids(persona, session)
        for persona in personas
    ]


async def get_counterpart_persona_srvc(
    persona: CounterPartPersonas,
    session: AsyncSession,
) -> CounterpartPersonaReadWithIds:
    """
    Get a counterpart persona service function.
    Args:
        persona: The counterpart persona dependency.
        session: The database session dependency.
    Returns:
        The requested counterpart persona with related simulation IDs.
    """
    return await counterpart_personas_repo.to_counterpart_persona_read_with_ids(persona, session)


async def update_counterpart_persona_srvc(
    persona: CounterPartPersonas,
    persona_data: CounterpartPersonaUpdateRequest,
    session: AsyncSession,
    current_user: User,
) -> CounterpartPersonaReadWithIds:
    """
    Update a counterpart persona service function.
    Args:
        persona: The counterpart persona dependency.
        persona_data: The data for updating the counterpart persona.
        session: The database session dependency.
        current_user: The current user dependency.
    Returns:
        The updated counterpart persona with related simulation IDs.
    """
    persona_in = CounterpartPersonaUpdate(
        **persona_data.model_dump(exclude_unset=True),
        last_edit_by_user_id=current_user.id,
    )
    updated_persona = await counterpart_personas_repo.update_counterpart_persona(
        persona,
        persona_in,
        session,
    )
    return await counterpart_personas_repo.to_counterpart_persona_read_with_ids(
        updated_persona,
        session,
    )


async def copy_counterpart_persona_srvc(
    source_persona: CounterPartPersonas,
    copy_data: CounterpartPersonaCopyRequest,
    session: AsyncSession,
    current_user: User,
) -> CounterpartPersonaReadWithIds:
    """
    Copy a counterpart persona service function.
    Args:
        source_persona: The source counterpart persona dependency.
        copy_data: The data for copying the counterpart persona.
        session: The database session dependency.
        current_user: The current user dependency.
    Returns:
        The copied counterpart persona with related simulation IDs.
    """
    copy_in = CounterpartPersonaCopy(**copy_data.model_dump())
    copied_persona = await counterpart_personas_repo.copy_counterpart_persona(
        source_persona,
        copy_in,
        current_user.id,
        session,
    )
    return await counterpart_personas_repo.to_counterpart_persona_read_with_ids(
        copied_persona,
        session,
    )


async def delete_counterpart_persona_srvc(
    persona: CounterPartPersonas,
    session: AsyncSession,
) -> None:
    """
    Delete a counterpart persona service function.
    Args:
        persona: The counterpart persona dependency.
        session: The database session dependency.
    Returns:
        None
    """
    await counterpart_personas_repo.delete_counterpart_persona(persona, session)
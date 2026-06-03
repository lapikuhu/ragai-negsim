from fastapi import APIRouter, HTTPException, status

from core.dependencies import (
    CopyableCounterpartPersonaDep,
    CounterpartPersonaCreatorDep,
    CounterpartPersonaViewerDep,
    CurrentUserDep,
    Page,
    SessionDep,
    WritableCounterpartPersonaDep,
)
from schemas.counterpart_personas_schemas import (
    CounterpartPersonaCopyRequest,
    CounterpartPersonaCreateRequest,
    CounterpartPersonaReadWithIds,
    CounterpartPersonaUpdateRequest,
)
from services import counterpart_personas_service

router = APIRouter(prefix="/counterpart-personas", tags=["counterpart-personas"])


def _raise_counterpart_persona_service_error(exc: ValueError) -> None:
    """
    Raise an HTTPException with a 409 Conflict status code for counterpart 
    persona service errors.
    """
    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail=str(exc),
    ) from exc

### ------------------ CREATE COUNTERPART PERSONA ------------------ ###
@router.post(
    "/",
    response_model=CounterpartPersonaReadWithIds,
    status_code=status.HTTP_201_CREATED,
)
async def create_counterpart_persona(
    persona_data: CounterpartPersonaCreateRequest,
    session: SessionDep,
    current_user: CounterpartPersonaCreatorDep,
) -> CounterpartPersonaReadWithIds:
    """
    Create a new counterpart persona endpoint.
    Args:
        persona_data: The data for the new counterpart persona.
        session: The database session dependency.
        current_user: The current user dependency.
    Returns:
        The created counterpart persona with related simulation IDs.
    """
    try:
        return await counterpart_personas_service.create_counterpart_persona_srvc(
            persona_data,
            session,
            current_user,
        )
    except ValueError as exc:
        _raise_counterpart_persona_service_error(exc)

### ------------------- LIST COUNTERPART PERSONAS ------------------ ###
@router.get(
    "/",
    response_model=list[CounterpartPersonaReadWithIds],
    status_code=status.HTTP_200_OK,
)
async def list_counterpart_personas(
    session: SessionDep,
    _current_user: CurrentUserDep,
    page: Page,
    created_by_user_id: int | None = None,
    name_contains: str | None = None,
    used: bool | None = None,
) -> list[CounterpartPersonaReadWithIds]:
    """
    List counterpart personas endpoint.
    Args:
        session: The database session dependency.
        _current_user: The current user dependency.
        page: The pagination dependency.
        created_by_user_id: Filter by the user who created the persona.
        name_contains: Filter by a substring in the persona's name.
        used: Filter by whether the persona has been used in simulations.
    Returns:
        A list of counterpart personas with related simulation IDs.
    """
    return await counterpart_personas_service.list_counterpart_personas_srvc(
        session=session,
        skip=page["skip"],
        limit=page["limit"],
        created_by_user_id=created_by_user_id,
        name_contains=name_contains,
        used=used,
    )

### -------------------- GET COUNTERPART PERSONA ------------------- ###
@router.get(
    "/{persona_id}",
    response_model=CounterpartPersonaReadWithIds,
    status_code=status.HTTP_200_OK,
)
async def get_counterpart_persona(
    persona: CounterpartPersonaViewerDep,
    session: SessionDep,
) -> CounterpartPersonaReadWithIds:
    """
    Get a counterpart persona by ID endpoint.
    Args:
        persona: The counterpart persona dependency.
        session: The database session dependency.
    Returns:
        The requested counterpart persona with related simulation IDs.
    """
    try:
        return await counterpart_personas_service.get_counterpart_persona_srvc(persona, session)
    except ValueError as exc:
        _raise_counterpart_persona_service_error(exc)

### ------------------- UPDATE COUNTERPART PERSONA ----------------- ###
@router.patch(
    "/{persona_id}",
    response_model=CounterpartPersonaReadWithIds,
    status_code=status.HTTP_200_OK,
)
async def update_counterpart_persona(
    persona_data: CounterpartPersonaUpdateRequest,
    persona: WritableCounterpartPersonaDep,
    session: SessionDep,
    current_user: CurrentUserDep,
) -> CounterpartPersonaReadWithIds:
    """
    Update a counterpart persona endpoint.
    Args:
        persona_data: The data for updating the counterpart persona.
        persona: The counterpart persona dependency.
        session: The database session dependency.
        current_user: The current user dependency.
    Returns:
        The updated counterpart persona with related simulation IDs.
    """
    try:
        return await counterpart_personas_service.update_counterpart_persona_srvc(
            persona,
            persona_data,
            session,
            current_user,
        )
    except ValueError as exc:
        _raise_counterpart_persona_service_error(exc)

### -------------------- COPY COUNTERPART PERSONA ------------------ ###
@router.post(
    "/{persona_id}/copy",
    response_model=CounterpartPersonaReadWithIds,
    status_code=status.HTTP_201_CREATED,
)
async def copy_counterpart_persona(
    copy_data: CounterpartPersonaCopyRequest,
    source_persona: CopyableCounterpartPersonaDep,
    session: SessionDep,
    current_user: CounterpartPersonaCreatorDep,
) -> CounterpartPersonaReadWithIds:
    """
    Copy a counterpart persona endpoint.
    Args:
        copy_data: The data for copying the counterpart persona.
        source_persona: The source counterpart persona dependency.
        session: The database session dependency.
        current_user: The current user dependency.
    Returns:
        The copied counterpart persona with related simulation IDs.
    Raises:
        HTTPException: If the copy operation fails due to a ValueError in the service layer.
    """
    try:
        return await counterpart_personas_service.copy_counterpart_persona_srvc(
            source_persona,
            copy_data,
            session,
            current_user,
        )
    except ValueError as exc:
        _raise_counterpart_persona_service_error(exc)

### ------------------- DELETE COUNTERPART PERSONA ----------------- ###
@router.delete(
    "/{persona_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_counterpart_persona(
    persona: WritableCounterpartPersonaDep,
    session: SessionDep,
) -> None:
    """
    Delete a counterpart persona endpoint.
    Args:
        persona: The counterpart persona dependency.
        session: The database session dependency.
    Returns:
        None
    Raises:
        HTTPException: If the delete operation fails due to a ValueError 
        in the service layer.
    """
    try:
        await counterpart_personas_service.delete_counterpart_persona_srvc(persona, session)
    except ValueError as exc:
        _raise_counterpart_persona_service_error(exc)
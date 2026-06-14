from fastapi import APIRouter, HTTPException, status

from app.core.dependencies import (
    AdminRagProfileDep,
    CurrentUserDep,
    Page,
    RagProfileAdminDep,
    ReadableRagProfileDep,
    SessionDep,
)
from app.schemas.rag_profile_definitions_schemas import RagProfileDefinitionRead
from app.schemas.rag_profiles_schemas import (
    RagProfileCopy,
    RagProfileCreateRequest,
    RagProfileReadWithIds,
    RagProfileUpdateRequest,
)
from app.services import rag_profiles_service

# Instntiate the API router for RAG profiles.
router = APIRouter(prefix="/rag-profiles", tags=["rag-profiles"])

# Helper candidate
def _raise_rag_profile_service_error(exc: ValueError) -> None:
    """
    Raise an HTTP exception for RAG profile service errors.
    Args:
        exc (ValueError): The exception to raise.
    """
    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail=str(exc),
    ) from exc

### --------------------- RAG PROFILE CREATE ----------------------- ###
@router.post(
    "/",
    response_model=RagProfileReadWithIds,
    status_code=status.HTTP_201_CREATED,
)
async def create_rag_profile(
    profile_data: RagProfileCreateRequest,
    session: SessionDep,
    current_user: RagProfileAdminDep,
) -> RagProfileReadWithIds:
    """
    Create a new RAG profile route.
    Args:
        profile_data (RagProfileCreateRequest): The data for the new RAG 
            profile.
        session (SessionDep): The database session.
        current_user (RagProfileAdminDep): The current user performing 
            the creation.
    Returns:
        RagProfileReadWithIds: The created RAG profile read model with 
        associated simulation IDs.
    """
    try:
        return await rag_profiles_service.create_rag_profile_srvc(
            profile_data,
            session,
            current_user,
        )
    except ValueError as exc:
        _raise_rag_profile_service_error(exc)

### ----------------- RAG PROFILE DEFINITIONS LIST ----------------- ###
@router.get(
    "/definitions",
    response_model=list[RagProfileDefinitionRead],
    status_code=status.HTTP_200_OK,
)
async def list_rag_profile_definitions(
    _current_user: CurrentUserDep,
) -> list[RagProfileDefinitionRead]:
    """
    List all RAG profile definitions route.
    Args:
        _current_user (CurrentUserDep): The current user.
    Returns:
        list[RagProfileDefinitionRead]: A list of RAG profile definitions.
    """
    return await rag_profiles_service.list_rag_profile_definitions_srvc()

### ----------------------- RAG PROFILE LIST ----------------------- ###
@router.get(
    "/",
    response_model=list[RagProfileReadWithIds],
    status_code=status.HTTP_200_OK,
)
async def list_rag_profiles(
    session: SessionDep,
    _current_user: CurrentUserDep,
    page: Page,
    strategy: str | None = None,
    name_contains: str | None = None,
    used: bool | None = None,
    created_by_user_id: int | None = None,
) -> list[RagProfileReadWithIds]:
    """
    List all RAG profiles route with optional filters.
    Args:
        session (SessionDep): The database session.
        _current_user (CurrentUserDep): The current user.
        page (Page): Pagination information.
        strategy (str | None): Filter by strategy.
        name_contains (str | None): Filter by name substring.
        used (bool | None): Filter by usage status.
        created_by_user_id (int | None): Filter by creator user ID.
    Returns:
        list[RagProfileReadWithIds]: A list of RAG profiles.
    """
    return await rag_profiles_service.list_rag_profiles_srvc(
        session=session,
        skip=page["skip"],
        limit=page["limit"],
        strategy=strategy,
        name_contains=name_contains,
        used=used,
        created_by_user_id=created_by_user_id,
    )

### ----------------------- RAG PROFILE GET ------------------------ ###
@router.get(
    "/{profile_id}",
    response_model=RagProfileReadWithIds,
    status_code=status.HTTP_200_OK,
)
async def get_rag_profile(
    profile: ReadableRagProfileDep,
    session: SessionDep,
) -> RagProfileReadWithIds:
    """
    Get a RAG profile by ID route.
    Args:
        profile (ReadableRagProfileDep): The RAG profile dependency.
        session (SessionDep): The database session.
    Returns:
        RagProfileReadWithIds: The RAG profile read model with associated 
        simulation IDs.
    """
    return await rag_profiles_service.get_rag_profile_srvc(profile, session)

### ----------------------- RAG PROFILE UPDATE --------------------- ###
@router.patch(
    "/{profile_id}",
    response_model=RagProfileReadWithIds,
    status_code=status.HTTP_200_OK,
)
async def update_rag_profile(
    profile_data: RagProfileUpdateRequest,
    profile: AdminRagProfileDep,
    session: SessionDep,
    current_user: RagProfileAdminDep,
) -> RagProfileReadWithIds:
    """
    Update a RAG profile route.
    Args:
        profile_data (RagProfileUpdateRequest): The data to update the 
            RAG profile.
        profile (AdminRagProfileDep): The RAG profile dependency.
        session (SessionDep): The database session.
        current_user (RagProfileAdminDep): The current user performing 
            the update.
    Returns:
        RagProfileReadWithIds: The updated RAG profile read model with 
        associated simulation IDs.
    Raises:
        HTTPException: If the update fails due to validation or other issues.
    """
    try:
        return await rag_profiles_service.update_rag_profile_srvc(
            profile,
            profile_data,
            session,
            current_user,
        )
    except ValueError as exc:
        _raise_rag_profile_service_error(exc)

### ----------------------- RAG PROFILE COPY ----------------------- ###
@router.post(
    "/{profile_id}/copy",
    response_model=RagProfileReadWithIds,
    status_code=status.HTTP_201_CREATED,
)
async def copy_rag_profile(
    copy_data: RagProfileCopy,
    source_profile: AdminRagProfileDep,
    session: SessionDep,
    current_user: RagProfileAdminDep,
) -> RagProfileReadWithIds:
    """
    Copy a RAG profile route.
    Args:
        copy_data (RagProfileCopy): The data for the new RAG profile copy.
        source_profile (AdminRagProfileDep): The source RAG profile to copy.
        session (SessionDep): The database session.
        current_user (RagProfileAdminDep): The current user performing
            the copy.
    Returns:
        RagProfileReadWithIds: The newly created RAG profile copy read model
        with associated simulation IDs.
    Raises:
        HTTPException: If the copy fails due to validation or other issues.
    """
    try:
        return await rag_profiles_service.copy_rag_profile_srvc(
            source_profile,
            copy_data,
            session,
            current_user,
        )
    except ValueError as exc:
        _raise_rag_profile_service_error(exc)

### ----------------------- RAG PROFILE DELETE --------------------- ###
@router.delete(
    "/{profile_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_rag_profile(
    profile: AdminRagProfileDep,
    session: SessionDep,
) -> None:
    """
    Delete a RAG profile route if it has not been used in any simulations.
    Args:
        profile (AdminRagProfileDep): The RAG profile dependency.
        session (SessionDep): The database session.
    Returns:
        None
    Raises:
        HTTPException: If the deletion fails due to validation or other issues.
    """
    try:
        await rag_profiles_service.delete_rag_profile_srvc(profile, session)
    except ValueError as exc:
        _raise_rag_profile_service_error(exc)

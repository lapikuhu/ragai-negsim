from fastapi import APIRouter, HTTPException, status

from core.dependencies import (
    AdminChunkingProfileDep,
    ChunkingProfileAdminDep,
    Page,
    SessionDep,
)
from schemas.chunking_profiles_schemas import (
    ChunkingProfileCopy,
    ChunkingProfileCreate,
    ChunkingProfileReadWithIds,
    ChunkingProfileUpdate,
)
from services import chunking_profiles_service

# Instance of APIRouter for chunking profile related endpoints
router = APIRouter(prefix="/chunking-profiles", tags=["chunking-profiles"])


def _raise_chunking_profile_service_error(exc: ValueError) -> None:
    """
    Helper function to convert ValueErrors from the service layer into 
    HTTPExceptions with appropriate status codes.
        Args:
            exc: The ValueError exception to convert.
        Raises:
            HTTPException: The HTTP exception with a 409 status code and the error detail.
    """
    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail=str(exc),
    ) from exc

### -------------------- CHUNKING PROFILE CREATE ------------------- ###
@router.post(
    "/",
    response_model=ChunkingProfileReadWithIds,
    status_code=status.HTTP_201_CREATED,
)
async def create_chunking_profile(
    profile_data: ChunkingProfileCreate,
    session: SessionDep,
    _admin: ChunkingProfileAdminDep,
) -> ChunkingProfileReadWithIds:
    """
    Create a new chunking profile endpoint.
        Args:
            profile_data: The data to create the chunking profile with.
            session: The database session.
            _admin: The admin dependency.
        Returns:
            A ChunkingProfileReadWithIds object containing the created 
            chunking profile data and associated corpus index IDs.
        Raises:
            HTTPException: If the chunking profile cannot be created due to 
            validation errors or other constraints, with a 409 status code and
            error detail.
    """
    try:
        return await chunking_profiles_service.create_chunking_profile_srvc(
            profile_data,
            session,
        )
    except ValueError as exc:
        _raise_chunking_profile_service_error(exc)

### -------------------- CHUNKING PROFILE LIST -------------------- ###
@router.get(
    "/",
    response_model=list[ChunkingProfileReadWithIds],
    status_code=status.HTTP_200_OK,
)
async def list_chunking_profiles(
    session: SessionDep,
    _admin: ChunkingProfileAdminDep,
    page: Page,
    strategy: str | None = None,
    name_contains: str | None = None,
    has_references: bool | None = None,
) -> list[ChunkingProfileReadWithIds]:
    """
    List chunking profiles endpoint with optional filters and pagination.
        Args:
            session: The database session.
            _admin: The admin dependency.
            page: The pagination parameters.
            strategy: Optional filter to list profiles by chunking strategy.
            name_contains: Optional filter to list profiles whose names 
                contain a substring.
            has_references: Optional filter to list profiles that are 
                referenced by corpus indices.
        Returns:
            A list of ChunkingProfileReadWithIds objects matching the 
            filters and pagination.
    """
    return await chunking_profiles_service.list_chunking_profiles_srvc(
        session=session,
        skip=page["skip"],
        limit=page["limit"],
        strategy=strategy,
        name_contains=name_contains,
        has_references=has_references,
    )

### ---------------------- CHUNKING PROFILE GET -------------------- ###
@router.get(
    "/{profile_id}",
    response_model=ChunkingProfileReadWithIds,
    status_code=status.HTTP_200_OK,
)
async def get_chunking_profile(
    profile: AdminChunkingProfileDep,
    session: SessionDep,
) -> ChunkingProfileReadWithIds:
    """
    Get a chunking profile by ID endpoint.
        Args:
            profile: The admin chunking profile dependency.
            session: The database session.
        Returns:
            A ChunkingProfileReadWithIds object containing the chunking 
            profile data and associated corpus index IDs.
    """
    return await chunking_profiles_service.get_chunking_profile_srvc(profile, session)

### -------------------- CHUNKING PROFILE UPDATE ------------------- ###
@router.patch(
    "/{profile_id}",
    response_model=ChunkingProfileReadWithIds,
    status_code=status.HTTP_200_OK,
)
async def update_chunking_profile(
    profile_data: ChunkingProfileUpdate,
    profile: AdminChunkingProfileDep,
    session: SessionDep,
) -> ChunkingProfileReadWithIds:
    """
    Update a chunking profile endpoint.
        Args:
            profile_data: The data to update the chunking profile with.
            profile: The admin chunking profile dependency.
            session: The database session.
        Returns:
            A ChunkingProfileReadWithIds object containing the updated 
            chunking profile data and associated corpus index IDs.
        Raises:
            HTTPException: If the chunking profile cannot be updated due to 
            validation errors or other constraints, with a 409 status code and
            error detail.
    """
    try:
        return await chunking_profiles_service.update_chunking_profile_srvc(
            profile,
            profile_data,
            session,
        )
    except ValueError as exc:
        _raise_chunking_profile_service_error(exc)

### --------------------- CHUNKING PROFILE COPY -------------------- ###
@router.post(
    "/{profile_id}/copy",
    response_model=ChunkingProfileReadWithIds,
    status_code=status.HTTP_201_CREATED,
)
async def copy_chunking_profile(
    copy_data: ChunkingProfileCopy,
    source_profile: AdminChunkingProfileDep,
    session: SessionDep,
) -> ChunkingProfileReadWithIds:
    """
    Copy a chunking profile endpoint.
        Args:
            copy_data: The data for the new chunking profile to create from 
                the source profile.
            source_profile: The admin chunking profile dependency for the 
                source profile to copy.
            session: The database session.
        Returns:
            A ChunkingProfileReadWithIds object containing the new copied 
            chunking profile data and associated corpus index IDs.
        Raises:
            HTTPException: If the chunking profile cannot be copied due to 
            validation errors or other constraints, with a 409 status code and
            error detail.
    """
    try:
        return await chunking_profiles_service.copy_chunking_profile_srvc(
            source_profile,
            copy_data,
            session,
        )
    except ValueError as exc:
        _raise_chunking_profile_service_error(exc)

#### -------------------- CHUNKING PROFILE DELETE ------------------ ###
@router.delete(
    "/{profile_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_chunking_profile(
    profile: AdminChunkingProfileDep,
    session: SessionDep,
) -> None:
    """
    Delete a chunking profile endpoint.
        Args:
            profile: The admin chunking profile dependency for the profile 
                to delete.
            session: The database session.
        Returns:
            None
        Raises:
            HTTPException: If the chunking profile cannot be deleted due to 
            existing references or other constraints, with a 409 status code 
            and error detail.
    """
    try:
        await chunking_profiles_service.delete_chunking_profile_srvc(profile, session)
    except ValueError as exc:
        _raise_chunking_profile_service_error(exc)

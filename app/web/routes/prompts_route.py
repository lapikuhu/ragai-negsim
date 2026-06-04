from fastapi import APIRouter, HTTPException, status

from core.dependencies import AdminDep, AdminPromptDep, Page, SessionDep
from schemas.prompts_schemas import (
    PromptAdminUpdate,
    PromptClone,
    PromptCreate,
    PromptRead,
)
from services import prompts_service

# Register the router for prompt-related endpoints
router = APIRouter(prefix="/prompts", tags=["prompts"])


def _raise_prompt_service_error(exc: ValueError) -> None:
    """
    Handle errors from the prompt service and raise appropriate HTTP 
    exceptions.
    Args:
        exc (ValueError): The exception raised by the prompt service.
    Raises:
        HTTPException: The corresponding HTTP exception based on the error 
        message.
    """
    message = str(exc)
    if message == "User not found":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=message) from exc

    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail=message,
    ) from exc

### ------------------------- PROMPT CREATE ------------------------ ###
@router.post(
    "/",
    response_model=PromptRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_prompt(
    prompt_data: PromptCreate,
    session: SessionDep,
    admin_user: AdminDep,
) -> PromptRead:
    """
    Create a new prompt.
    Args:
        prompt_data (PromptCreate): The data for the new prompt.
        session (AsyncSession): The database session to use for the operation.
        admin_user (User): The current admin user creating the prompt.
    Returns:
        PromptRead: The created prompt.
    """
    try:
        return await prompts_service.create_prompt_srvc(
            prompt_data,
            session,
            admin_user,
        )
    except ValueError as exc:
        _raise_prompt_service_error(exc)

### -------------------------- PROMPT LIST ------------------------- ###
@router.get(
    "/",
    response_model=list[PromptRead],
    status_code=status.HTTP_200_OK,
)
async def list_prompts(
    session: SessionDep,
    _admin_user: AdminDep,
    page: Page,
    owner_id: int | None = None,
    is_system: bool | None = None,
    name_contains: str | None = None,
) -> list[PromptRead]:
    """
    List prompts with optional filters.
    Args:
        session (AsyncSession): The database session to use for the query.
        _admin_user (User): The current admin user.
        page (Page): The pagination parameters.
        owner_id (int | None): The ID of the owner to filter prompts by.
        is_system (bool | None): Whether to filter prompts by system status.
        name_contains (str | None): A substring to filter prompts by name.
    Returns:
        list[PromptRead]: A list of prompt schemas.
    """
    return await prompts_service.list_prompts_srvc(
        session=session,
        skip=page["skip"],
        limit=page["limit"],
        owner_id=owner_id,
        is_system=is_system,
        name_contains=name_contains,
    )

### ------------------------ PROMPT GET BY ID ---------------------- ###
@router.get(
    "/{prompt_id}",
    response_model=PromptRead,
    status_code=status.HTTP_200_OK,
)
async def get_prompt(
    prompt: AdminPromptDep,
) -> PromptRead:
    """
    Get a prompt by its ID.
    Args:
        prompt (Prompt): The Prompt model instance to retrieve.
    Returns:
        PromptRead: The corresponding PromptRead schema instance.
    """
    return await prompts_service.get_prompt_srvc(prompt)

### ------------------------- PROMPT UPDATE ------------------------ ###
@router.patch(
    "/{prompt_id}",
    response_model=PromptRead,
    status_code=status.HTTP_200_OK,
)
async def update_prompt(
    prompt_data: PromptAdminUpdate,
    prompt: AdminPromptDep,
    session: SessionDep,
) -> PromptRead:
    """
    Update an existing prompt.
    Args:
        prompt_data (PromptAdminUpdate): The data to update the prompt with.
        prompt (Prompt): The Prompt model instance to update.
        session (AsyncSession): The database session to use for the operation.
    Returns:
        PromptRead: The updated prompt.
    """
    try:
        return await prompts_service.update_prompt_srvc(
            prompt,
            prompt_data,
            session,
        )
    except ValueError as exc:
        _raise_prompt_service_error(exc)

### -------------------------- PROMPT COPY ------------------------- ###
@router.post(
    "/{prompt_id}/copy",
    response_model=PromptRead,
    status_code=status.HTTP_201_CREATED,
)
async def copy_prompt(
    copy_data: PromptClone,
    source_prompt: AdminPromptDep,
    session: SessionDep,
) -> PromptRead:
    """
    Copy an existing prompt.
    Args:
        copy_data (PromptClone): The data for the new copied prompt.
        source_prompt (Prompt): The Prompt model instance to copy.
        session (AsyncSession): The database session to use for the operation.
    Returns:
        PromptRead: The copied prompt.
    """
    try:
        return await prompts_service.copy_prompt_srvc(
            source_prompt,
            copy_data,
            session,
        )
    except ValueError as exc:
        _raise_prompt_service_error(exc)

### ------------------------- PROMPT DELETE ------------------------ ###
@router.delete(
    "/{prompt_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_prompt(
    prompt: AdminPromptDep,
    session: SessionDep,
) -> None:
    """
    Delete an existing prompt.
    Args:
        prompt (Prompt): The Prompt model instance to delete.
        session (AsyncSession): The database session to use for the operation.
    Returns:
        None
    """
    try:
        await prompts_service.delete_prompt_srvc(prompt, session)
    except ValueError as exc:
        _raise_prompt_service_error(exc)

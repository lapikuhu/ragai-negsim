from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.prompts import Prompt
from app.models.users import User
from app.repositories import prompts_repo, users_repo
from app.schemas.prompts_schemas import (
    PromptAdminUpdate,
    PromptClone,
    PromptCreate,
    PromptRead,
)


def _read_prompt(prompt: Prompt) -> PromptRead:
    """
    Helper function to convert a Prompt model instance to a PromptRead 
    schema instance.
    Args:
        prompt (Prompt): The Prompt model instance to convert.
    Returns:
        PromptRead: The corresponding PromptRead schema instance.
    """
    return PromptRead(
        id=prompt.id,
        name=prompt.name,
        description=prompt.description,
        messages=prompt.messages,
        owner_id=prompt.owner_id,
        is_system=prompt.is_system,
    )

# Helper candidate
async def _ensure_owner_exists(
    owner_id: int | None,
    session: AsyncSession,
) -> None:
    """
    Ensures that a user with the given owner_id exists in the database.
    Args:
        owner_id (int | None): The ID of the owner to check.
        session (AsyncSession): The database session to use for the query.
    Returns:
        None
    Raises:
        ValueError: If the owner_id is not None and no user with that ID 
        exists.
    """
    if owner_id is None:
        return

    owner = await users_repo.get_user_by_id(owner_id, session)
    if owner is None:
        raise ValueError("User not found")


async def create_prompt_srvc(
    prompt_data: PromptCreate,
    session: AsyncSession,
    current_user: User,
) -> PromptRead:
    """
    Create a new prompt.
    Args:
        prompt_data (PromptCreate): The data for the new prompt.
        session (AsyncSession): The database session to use for the operation.
        current_user (User): The current user creating the prompt.
    Returns:
        PromptRead: The created prompt.
    """
    owned_prompt_data = PromptCreate(
        **{
            **prompt_data.model_dump(),
            "owner_id": current_user.id,
        }
    )
    prompt = await prompts_repo.create_prompt(owned_prompt_data, session)
    return _read_prompt(prompt)


async def list_prompts_srvc(
    session: AsyncSession,
    skip: int = 0,
    limit: int = 20,
    owner_id: int | None = None,
    is_system: bool | None = None,
    name_contains: str | None = None,
) -> list[PromptRead]:
    """
    List prompts with optional filters.
    Args:
        session (AsyncSession): The database session to use for the query.
        skip (int): The number of prompts to skip for pagination.
        limit (int): The maximum number of prompts to return.
        owner_id (int | None): The ID of the owner to filter prompts by.
        is_system (bool | None): Whether to filter prompts by system status.
        name_contains (str | None): A substring to filter prompts by name.
    Returns:
        list[PromptRead]: A list of prompt schemas.
    """
    prompts = await prompts_repo.list_prompts(
        session=session,
        skip=skip,
        limit=limit,
        owner_id=owner_id,
        is_system=is_system,
        name_contains=name_contains,
    )
    return [_read_prompt(prompt) for prompt in prompts]


async def get_prompt_srvc(prompt: Prompt) -> PromptRead:
    """Get a prompt by its ID.
    Args:
        prompt (Prompt): The Prompt model instance to retrieve.
    Returns:
        PromptRead: The corresponding PromptRead schema instance.
    """
    return _read_prompt(prompt)


async def update_prompt_srvc(
    prompt: Prompt,
    prompt_data: PromptAdminUpdate,
    session: AsyncSession,
) -> PromptRead:
    """
    Update an existing prompt.
    Args:
        prompt (Prompt): The Prompt model instance to update.
        prompt_data (PromptAdminUpdate): The data to update the prompt with.
        session (AsyncSession): The database session to use for the operation.
    Returns:
        PromptRead: The updated prompt.
    """
    update_data = prompt_data.model_dump(exclude_unset=True)
    if "owner_id" in update_data:
        await _ensure_owner_exists(update_data["owner_id"], session)

    prompt_in = PromptAdminUpdate(**update_data)
    updated_prompt = await prompts_repo.admin_update_prompt(
        prompt,
        prompt_in,
        session,
    )
    return _read_prompt(updated_prompt)


async def copy_prompt_srvc(
    source_prompt: Prompt,
    copy_data: PromptClone,
    session: AsyncSession,
) -> PromptRead:
    """
    Copy an existing prompt.
    Args:
        source_prompt (Prompt): The Prompt model instance to copy.
        copy_data (PromptClone): The data for the new copied prompt.
        session (AsyncSession): The database session to use for the operation.
    Returns:
        PromptRead: The copied prompt.
    """
    await _ensure_owner_exists(copy_data.owner_id, session)
    copied_prompt = await prompts_repo.copy_prompt(source_prompt, copy_data, session)
    return _read_prompt(copied_prompt)


async def delete_prompt_srvc(
    prompt: Prompt,
    session: AsyncSession,
) -> None:
    """
    Delete a prompt.
    Args:
        prompt (Prompt): The Prompt model instance to delete.
        session (AsyncSession): The database session to use for the operation.
    Returns:
        None
    """
    await prompts_repo.delete_prompt(prompt, session)

from copy import deepcopy
from typing import Any

from models.prompts import Prompt
from repositories.helpers import commit_and_refresh, commit_delete
from schemas.prompts_schemas import (
    PromptAdminUpdate,
    PromptClone,
    PromptCreate,
    PromptUpdate,
)
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession


def ensure_prompt_messages_dict(messages: dict[str, Any] | None) -> None:
    """
    Ensure that the prompt messages are a dictionary if they are provided.
        Args:
            messages: The prompt messages to validate.
        Returns:
            None
        Raises:
            ValueError: If messages are provided and they are not a dictionary.
    """
    if messages is not None and not isinstance(messages, dict):
        raise ValueError("Prompt messages must be a dictionary")


async def get_prompt_by_id(
    prompt_id: int,
    session: AsyncSession,
) -> Prompt | None:
    """
    Get a prompt by its ID.
        Args:
            prompt_id: The ID of the prompt.
            session: The database session.
        Returns:
            The Prompt instance if found, None otherwise.
    """
    return await session.get(Prompt, prompt_id)


async def get_prompt_by_name(
    name: str,
    session: AsyncSession,
) -> Prompt | None:
    """
    Get a prompt by its name.
        Args:
            name: The name of the prompt.
            session: The database session.
        Returns:
            The Prompt instance if found, None otherwise.
    """
    result = await session.exec(select(Prompt).where(Prompt.name == name))
    return result.first()


async def ensure_prompt_name_available(
    name: str,
    session: AsyncSession,
    exclude_prompt_id: int | None = None,
) -> None:
    """
    Ensure that the prompt name is available.
        Args:
            name: The name of the prompt.
            session: The database session.
            exclude_prompt_id: An optional prompt ID to exclude from the check.
        Raises:
            ValueError: If the prompt name already exists.
    """
    existing_prompt = await get_prompt_by_name(name, session)
    if existing_prompt is None:
        return

    if exclude_prompt_id is not None and existing_prompt.id == exclude_prompt_id:
        return

    raise ValueError("Prompt name already exists")


async def list_prompts(
    session: AsyncSession,
    skip: int = 0,
    limit: int = 20,
    owner_id: int | None = None,
    is_system: bool | None = None,
    name_contains: str | None = None,
) -> list[Prompt]:
    """
    List prompts with optional filters.
        Args:
            session: The database session.
            skip: The number of prompts to skip.
            limit: The maximum number of prompts to return.
            owner_id: Optional owner ID to filter prompts.
            is_system: Optional flag to filter system prompts.
            name_contains: Optional substring to filter prompt names.
        Returns:
            A list of Prompt instances.
    """
    statement = select(Prompt)

    if owner_id is not None:
        statement = statement.where(Prompt.owner_id == owner_id)
    if is_system is not None:
        statement = statement.where(Prompt.is_system == is_system)
    if name_contains is not None:
        statement = statement.where(Prompt.name.contains(name_contains))

    statement = statement.offset(skip).limit(limit)
    result = await session.exec(statement)
    return list(result.all())


async def create_prompt(
    prompt_in: PromptCreate,
    session: AsyncSession,
) -> Prompt:
    """
    Create a new prompt.
        Args:
            prompt_in: The PromptCreate instance containing prompt data.
            session: The database session.
        Returns:
            The created Prompt instance.
        Raises:
            ValueError: If the prompt name already exists or messages are 
            invalid.
    """
    await ensure_prompt_name_available(prompt_in.name, session)
    ensure_prompt_messages_dict(prompt_in.messages)
    prompt = Prompt(**prompt_in.model_dump())
    return await commit_and_refresh(session, prompt)


async def create_owned_prompt(
    prompt_in: PromptCreate,
    owner_id: int,
    session: AsyncSession,
) -> Prompt:
    # TODO: Probably should be abandoned in favor of just calling create_prompt and passing the owner_id in the prompt_in, but for now this is a convenient wrapper for creating prompts owned by a specific user without having to include the owner_id in the request body
    """
    Create a new prompt owned by a specific user.
        Args:
            prompt_in: The PromptCreate instance containing prompt data.
            owner_id: The ID of the owner.
            session: The database session.
        Returns:
            The created Prompt instance.
        Raises:
            ValueError: If the prompt name already exists or messages are invalid.
    """
    await ensure_prompt_name_available(prompt_in.name, session)
    ensure_prompt_messages_dict(prompt_in.messages)
    prompt_data = prompt_in.model_dump()
    prompt_data["owner_id"] = owner_id
    prompt_data["is_system"] = False
    prompt = Prompt(**prompt_data)
    return await commit_and_refresh(session, prompt)


async def update_prompt(
    prompt: Prompt,
    prompt_in: PromptUpdate,
    session: AsyncSession,
) -> Prompt:
    """
    Update an existing prompt.
        Args:
            prompt: The Prompt instance to be updated.
            prompt_in: The PromptUpdate instance containing updated data.
            session: The database session.
        Returns:
            The updated Prompt instance.
        Raises:
            ValueError: If the prompt name already exists or messages are 
            invalid.
    """
    update_data = prompt_in.model_dump(exclude_unset=True)
    await _apply_prompt_update(prompt, update_data, session)
    return await commit_and_refresh(session, prompt)


async def admin_update_prompt(
    prompt: Prompt,
    prompt_in: PromptAdminUpdate,
    session: AsyncSession,
) -> Prompt:
    # TODO: Probably should be abandoned in favor of just calling update_prompt and passing the admin-only fields in the prompt_in, but for now this is a convenient wrapper for updating prompts with admin-only fields without having to include those fields in the request body for regular updates
    """
    Update an existing prompt as an admin.
        Args:
            prompt: The Prompt instance to be updated.
            prompt_in: The PromptAdminUpdate instance containing updated data.
            session: The database session.
        Returns:
            The updated Prompt instance.
        Raises:
            ValueError: If the prompt name already exists or messages are invalid.
    """
    update_data = prompt_in.model_dump(exclude_unset=True)
    await _apply_prompt_update(prompt, update_data, session)
    return await commit_and_refresh(session, prompt)


async def _apply_prompt_update(
    prompt: Prompt,
    update_data: dict[str, Any],
    session: AsyncSession,
) -> None:
    """
    Apply updates to a prompt instance.
        Args:
            prompt: The Prompt instance to be updated.
            update_data: A dictionary containing the updated data.
            session: The database session.
        Raises:
            ValueError: If the prompt name already exists or messages are invalid.
    """
    if "name" in update_data and update_data["name"] is not None:
        await ensure_prompt_name_available(update_data["name"], session, prompt.id)

    if "messages" in update_data:
        ensure_prompt_messages_dict(update_data["messages"])

    for field_name, value in update_data.items():
        setattr(prompt, field_name, value)


async def copy_prompt(
    source_prompt: Prompt,
    copy_in: PromptClone,
    session: AsyncSession,
) -> Prompt:
    """
    Create a copy of an existing prompt.
        Args:
            source_prompt: The Prompt instance to be copied.
            copy_in: The PromptClone instance containing copy data.
            session: The database session.
        Returns:
            The created Prompt instance.
        Raises:
            ValueError: If the prompt name already exists or messages are invalid.
    """
    await ensure_prompt_name_available(copy_in.name, session)
    prompt = Prompt(
        name=copy_in.name,
        description=(
            copy_in.description
            if copy_in.description is not None
            else source_prompt.description
        ),
        messages=deepcopy(source_prompt.messages),
        owner_id=copy_in.owner_id,
        is_system=False,
    )
    return await commit_and_refresh(session, prompt)


async def delete_prompt(
    prompt: Prompt,
    session: AsyncSession,
) -> None:
    # TODO: Should probably check if the prompt is in use by any simulations before allowing deletion and raise an error if it is, but for now just allow deletion without any checks
    """
    Delete an existing prompt.
        Args:
            prompt: The Prompt instance to be deleted.
            session: The database session.
    """
    await commit_delete(session, prompt)
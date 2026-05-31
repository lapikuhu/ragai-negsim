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
    if messages is not None and not isinstance(messages, dict):
        raise ValueError("Prompt messages must be a dictionary")


async def get_prompt_by_id(
    prompt_id: int,
    session: AsyncSession,
) -> Prompt | None:
    return await session.get(Prompt, prompt_id)


async def get_prompt_by_name(
    name: str,
    session: AsyncSession,
) -> Prompt | None:
    result = await session.exec(select(Prompt).where(Prompt.name == name))
    return result.first()


async def ensure_prompt_name_available(
    name: str,
    session: AsyncSession,
    exclude_prompt_id: int | None = None,
) -> None:
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
    await ensure_prompt_name_available(prompt_in.name, session)
    ensure_prompt_messages_dict(prompt_in.messages)
    prompt = Prompt(**prompt_in.model_dump())
    return await commit_and_refresh(session, prompt)


async def create_owned_prompt(
    prompt_in: PromptCreate,
    owner_id: int,
    session: AsyncSession,
) -> Prompt:
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
    update_data = prompt_in.model_dump(exclude_unset=True)
    await _apply_prompt_update(prompt, update_data, session)
    return await commit_and_refresh(session, prompt)


async def admin_update_prompt(
    prompt: Prompt,
    prompt_in: PromptAdminUpdate,
    session: AsyncSession,
) -> Prompt:
    update_data = prompt_in.model_dump(exclude_unset=True)
    await _apply_prompt_update(prompt, update_data, session)
    return await commit_and_refresh(session, prompt)


async def _apply_prompt_update(
    prompt: Prompt,
    update_data: dict[str, Any],
    session: AsyncSession,
) -> None:
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
    await commit_delete(session, prompt)
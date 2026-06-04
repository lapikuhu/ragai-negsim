from types import SimpleNamespace

import pytest

from schemas.prompts_schemas import (
    PromptAdminUpdate,
    PromptClone,
    PromptCreate,
)
from services import prompts_service


def _user(user_id=1):
    return SimpleNamespace(id=user_id, username=f"user-{user_id}", roles=[])


def _prompt(
    prompt_id=10,
    name="Prompt",
    description="A prompt",
    messages=None,
    owner_id=None,
    is_system=False,
):
    return SimpleNamespace(
        id=prompt_id,
        name=name,
        description=description,
        messages=messages or {"system": "Be helpful."},
        owner_id=owner_id,
        is_system=is_system,
    )


@pytest.mark.asyncio
async def test_create_prompt_validates_owner_and_converts(monkeypatch):
    captured = []

    async def fake_get_user_by_id(user_id, session):
        assert user_id == 7
        return _user(7)

    async def fake_create_prompt(prompt_in, session):
        captured.append(prompt_in)
        return _prompt(
            prompt_id=12,
            name=prompt_in.name,
            description=prompt_in.description,
            messages=prompt_in.messages,
            owner_id=prompt_in.owner_id,
            is_system=prompt_in.is_system,
        )

    monkeypatch.setattr(prompts_service.users_repo, "get_user_by_id", fake_get_user_by_id)
    monkeypatch.setattr(prompts_service.prompts_repo, "create_prompt", fake_create_prompt)

    result = await prompts_service.create_prompt_srvc(
        PromptCreate(
            name="Coach prompt",
            description="Negotiation coach",
            messages={"system": "Coach the student."},
            owner_id=7,
            is_system=True,
        ),
        object(),
        _user(1),
    )

    assert result.id == 12
    assert result.owner_id == 7
    assert result.is_system is True
    assert captured == [
        PromptCreate(
            name="Coach prompt",
            description="Negotiation coach",
            messages={"system": "Coach the student."},
            owner_id=7,
            is_system=True,
        )
    ]


@pytest.mark.asyncio
async def test_create_prompt_requires_existing_owner(monkeypatch):
    async def fake_get_user_by_id(user_id, session):
        return None

    monkeypatch.setattr(prompts_service.users_repo, "get_user_by_id", fake_get_user_by_id)

    with pytest.raises(ValueError, match="User not found"):
        await prompts_service.create_prompt_srvc(
            PromptCreate(name="Missing owner", owner_id=99),
            object(),
            _user(1),
        )


@pytest.mark.asyncio
async def test_list_prompts_passes_filters_and_converts(monkeypatch):
    captured = []
    prompts = [_prompt(1), _prompt(2, owner_id=7, is_system=True)]

    async def fake_list_prompts(
        session,
        skip=0,
        limit=20,
        owner_id=None,
        is_system=None,
        name_contains=None,
    ):
        captured.append((skip, limit, owner_id, is_system, name_contains))
        return prompts

    monkeypatch.setattr(prompts_service.prompts_repo, "list_prompts", fake_list_prompts)

    result = await prompts_service.list_prompts_srvc(
        object(),
        skip=5,
        limit=10,
        owner_id=7,
        is_system=True,
        name_contains="coach",
    )

    assert captured == [(5, 10, 7, True, "coach")]
    assert [prompt.id for prompt in result] == [1, 2]


@pytest.mark.asyncio
async def test_get_prompt_converts_model():
    result = await prompts_service.get_prompt_srvc(
        _prompt(
            prompt_id=3,
            name="Evaluator",
            messages={"system": "Evaluate."},
            is_system=True,
        )
    )

    assert result.id == 3
    assert result.name == "Evaluator"
    assert result.messages == {"system": "Evaluate."}
    assert result.is_system is True


@pytest.mark.asyncio
async def test_admin_update_prompt_validates_owner(monkeypatch):
    captured = []

    async def fake_get_user_by_id(user_id, session):
        assert user_id == 8
        return _user(8)

    async def fake_admin_update_prompt(prompt, prompt_in, session):
        captured.append(prompt_in)
        prompt.owner_id = prompt_in.owner_id
        prompt.is_system = prompt_in.is_system
        return prompt

    monkeypatch.setattr(prompts_service.users_repo, "get_user_by_id", fake_get_user_by_id)
    monkeypatch.setattr(prompts_service.prompts_repo, "admin_update_prompt", fake_admin_update_prompt)

    result = await prompts_service.update_prompt_srvc(
        _prompt(),
        PromptAdminUpdate(owner_id=8, is_system=True),
        object(),
    )

    assert result.owner_id == 8
    assert result.is_system is True
    assert captured[0].model_dump(exclude_unset=True) == {
        "owner_id": 8,
        "is_system": True,
    }


@pytest.mark.asyncio
async def test_copy_prompt_validates_owner_and_delegates(monkeypatch):
    captured = []
    source = _prompt(prompt_id=4, messages={"system": "Original."})

    async def fake_get_user_by_id(user_id, session):
        assert user_id == 9
        return _user(9)

    async def fake_copy_prompt(source_prompt, copy_in, session):
        captured.append((source_prompt, copy_in))
        return _prompt(
            prompt_id=5,
            name=copy_in.name,
            description=copy_in.description,
            messages=source_prompt.messages,
            owner_id=copy_in.owner_id,
        )

    monkeypatch.setattr(prompts_service.users_repo, "get_user_by_id", fake_get_user_by_id)
    monkeypatch.setattr(prompts_service.prompts_repo, "copy_prompt", fake_copy_prompt)

    result = await prompts_service.copy_prompt_srvc(
        source,
        PromptClone(name="Copied prompt", owner_id=9, description="Copy"),
        object(),
    )

    assert result.id == 5
    assert result.owner_id == 9
    assert captured == [
        (
            source,
            PromptClone(name="Copied prompt", owner_id=9, description="Copy"),
        )
    ]


@pytest.mark.asyncio
async def test_delete_prompt_delegates_to_repo(monkeypatch):
    deleted = []
    target = _prompt()

    async def fake_delete_prompt(prompt, session):
        deleted.append(prompt)

    monkeypatch.setattr(prompts_service.prompts_repo, "delete_prompt", fake_delete_prompt)

    await prompts_service.delete_prompt_srvc(target, object())

    assert deleted == [target]

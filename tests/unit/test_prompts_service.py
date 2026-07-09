from types import SimpleNamespace

import pytest

from app.schemas.prompts_schemas import (
    PromptAdminUpdate,
    PromptClone,
    PromptCreate,
)
from app.repositories import prompts_repo
from app.services import prompts_service


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


def test_validate_prompt_messages_accepts_template_key():
    prompts_repo.validate_prompt_messages({"template": "Add a custom instruction."})


@pytest.mark.parametrize(
    "messages",
    [
        {},
        {"template": ""},
        {"template": 123},
        {"unknown": "Add a custom instruction."},
    ],
)
def test_validate_prompt_messages_rejects_missing_template(messages):
    with pytest.raises(ValueError, match="non-empty template string"):
        prompts_repo.validate_prompt_messages(messages)


@pytest.mark.asyncio
async def test_create_prompt_stamps_current_user_owner_and_converts(
    monkeypatch,
    fake_user_factory,
    recording_async_session_factory,
):
    captured = []
    session = recording_async_session_factory()

    async def fake_create_prompt(prompt_in, session_arg):
        assert session_arg is session
        captured.append(prompt_in)
        return _prompt(
            prompt_id=12,
            name=prompt_in.name,
            description=prompt_in.description,
            messages=prompt_in.messages,
            owner_id=prompt_in.owner_id,
            is_system=prompt_in.is_system,
        )

    monkeypatch.setattr(prompts_service.prompts_repo, "create_prompt", fake_create_prompt)

    result = await prompts_service.create_prompt_srvc(
        PromptCreate(
            name="Coach prompt",
            description="Negotiation coach",
            messages={"system": "Coach the student."},
            owner_id=7,
            is_system=True,
        ),
        session,
        fake_user_factory(user_id=1, roles=()),
    )

    assert result.id == 12
    assert result.owner_id == 1
    assert result.is_system is True
    assert captured == [
        PromptCreate(
            name="Coach prompt",
            description="Negotiation coach",
            messages={"system": "Coach the student."},
            owner_id=1,
            is_system=True,
        )
    ]


@pytest.mark.asyncio
async def test_create_prompt_ignores_caller_supplied_owner(
    monkeypatch,
    fake_user_factory,
    recording_async_session_factory,
):
    captured = []
    session = recording_async_session_factory()

    async def fake_create_prompt(prompt_in, session_arg):
        assert session_arg is session
        captured.append(prompt_in)
        return _prompt(
            prompt_id=13,
            name=prompt_in.name,
            messages=prompt_in.messages,
            owner_id=prompt_in.owner_id,
        )

    monkeypatch.setattr(prompts_service.prompts_repo, "create_prompt", fake_create_prompt)

    result = await prompts_service.create_prompt_srvc(
        PromptCreate(
            name="Owned prompt",
            messages={"template": "Use this custom extension."},
            owner_id=99,
        ),
        session,
        fake_user_factory(user_id=4, roles=()),
    )

    assert result.owner_id == 4
    assert captured[0].owner_id == 4


@pytest.mark.asyncio
async def test_list_prompts_passes_filters_and_converts(
    monkeypatch,
    recording_async_session_factory,
):
    captured = []
    expected_session = recording_async_session_factory()
    prompts = [_prompt(1), _prompt(2, owner_id=7, is_system=True)]

    async def fake_list_prompts(
        session,
        skip=0,
        limit=20,
        owner_id=None,
        is_system=None,
        name_contains=None,
    ):
        assert session is expected_session
        captured.append((skip, limit, owner_id, is_system, name_contains))
        return prompts

    monkeypatch.setattr(prompts_service.prompts_repo, "list_prompts", fake_list_prompts)

    result = await prompts_service.list_prompts_srvc(
        expected_session,
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
async def test_admin_update_prompt_validates_owner(
    monkeypatch,
    fake_user_factory,
    recording_async_session_factory,
):
    captured = []
    session = recording_async_session_factory()

    async def fake_get_user_by_id(user_id, session_arg):
        assert user_id == 8
        assert session_arg is session
        return fake_user_factory(user_id=8, roles=())

    async def fake_admin_update_prompt(prompt, prompt_in, session_arg):
        assert session_arg is session
        captured.append(prompt_in)
        prompt.owner_id = prompt_in.owner_id
        prompt.is_system = prompt_in.is_system
        return prompt

    monkeypatch.setattr(prompts_service.users_repo, "get_user_by_id", fake_get_user_by_id)
    monkeypatch.setattr(prompts_service.prompts_repo, "admin_update_prompt", fake_admin_update_prompt)

    result = await prompts_service.update_prompt_srvc(
        _prompt(),
        PromptAdminUpdate(owner_id=8, is_system=True),
        session,
    )

    assert result.owner_id == 8
    assert result.is_system is True
    assert captured[0].model_dump(exclude_unset=True) == {
        "owner_id": 8,
        "is_system": True,
    }


@pytest.mark.asyncio
async def test_copy_prompt_validates_owner_and_delegates(
    monkeypatch,
    fake_user_factory,
    recording_async_session_factory,
):
    captured = []
    session = recording_async_session_factory()
    source = _prompt(prompt_id=4, messages={"system": "Original."})

    async def fake_get_user_by_id(user_id, session_arg):
        assert user_id == 9
        assert session_arg is session
        return fake_user_factory(user_id=9, roles=())

    async def fake_copy_prompt(source_prompt, copy_in, session_arg):
        assert session_arg is session
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
        session,
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
async def test_delete_prompt_delegates_to_repo(
    monkeypatch,
    recording_async_session_factory,
):
    deleted = []
    session = recording_async_session_factory()
    target = _prompt()

    async def fake_delete_prompt(prompt, session_arg):
        assert session_arg is session
        deleted.append(prompt)

    monkeypatch.setattr(prompts_service.prompts_repo, "delete_prompt", fake_delete_prompt)

    await prompts_service.delete_prompt_srvc(target, session)

    assert deleted == [target]

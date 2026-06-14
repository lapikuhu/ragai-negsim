from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from app.schemas.rag_profile_definitions_schemas import RagProfileDefinitionRead
from app.schemas.rag_profiles_schemas import (
    RagProfileCopy,
    RagProfileCreateRequest,
    RagProfileReadWithIds,
    RagProfileUpdateRequest,
)
from app.services import rag_profiles_service


def _user(user_id=1):
    return SimpleNamespace(id=user_id, username=f"user-{user_id}")


def _profile(
    profile_id=10,
    name="Default CRAG",
    strategy="crag",
    config=None,
    created_by_user_id=1,
    last_edit_by_user_id=None,
):
    now = datetime.now(timezone.utc)
    return SimpleNamespace(
        id=profile_id,
        name=name,
        strategy=strategy,
        config=config
        or {
            "top_k": 4,
            "reranker": "cross_encoder",
            "top_n": 3,
            "max_rewrite_attempts": 2,
        },
        created_by_user_id=created_by_user_id,
        last_edit_by_user_id=last_edit_by_user_id,
        created_at=now,
        last_updated=now,
    )


@pytest.mark.asyncio
async def test_create_rag_profile_stamps_current_admin(monkeypatch):
    captured = []
    created = _profile(profile_id=12, created_by_user_id=7)

    async def fake_create_rag_profile(profile_in, session):
        captured.append(profile_in)
        return created

    async def fake_to_read_with_ids(profile, session):
        return RagProfileReadWithIds(
            **profile.__dict__,
            simulation_ids=[],
        )

    monkeypatch.setattr(
        rag_profiles_service.rag_profiles_repo,
        "create_rag_profile",
        fake_create_rag_profile,
    )
    monkeypatch.setattr(
        rag_profiles_service.rag_profiles_repo,
        "to_rag_profile_read_with_ids",
        fake_to_read_with_ids,
    )

    result = await rag_profiles_service.create_rag_profile_srvc(
        RagProfileCreateRequest(
            name="CRAG strict",
            strategy="crag",
            config={
                "top_k": 5,
                "reranker": "cross_encoder",
                "top_n": 2,
                "max_rewrite_attempts": 1,
            },
        ),
        object(),
        _user(7),
    )

    assert result.id == 12
    assert result.created_by_user_id == 7
    assert captured[0].created_by_user_id == 7


@pytest.mark.asyncio
async def test_list_rag_profiles_passes_filters_and_converts(monkeypatch):
    captured = []
    profiles = [_profile(1), _profile(2, name="Fallback off")]

    async def fake_list_rag_profiles(
        session,
        skip=0,
        limit=20,
        strategy=None,
        name_contains=None,
        used=None,
        created_by_user_id=None,
    ):
        captured.append((skip, limit, strategy, name_contains, used, created_by_user_id))
        return profiles

    async def fake_to_read_with_ids(profile, session):
        return RagProfileReadWithIds(
            **profile.__dict__,
            simulation_ids=[profile.id],
        )

    monkeypatch.setattr(
        rag_profiles_service.rag_profiles_repo,
        "list_rag_profiles",
        fake_list_rag_profiles,
    )
    monkeypatch.setattr(
        rag_profiles_service.rag_profiles_repo,
        "to_rag_profile_read_with_ids",
        fake_to_read_with_ids,
    )

    result = await rag_profiles_service.list_rag_profiles_srvc(
        object(),
        skip=5,
        limit=10,
        strategy="crag",
        name_contains="Default",
        used=True,
        created_by_user_id=3,
    )

    assert captured == [(5, 10, "crag", "Default", True, 3)]
    assert [profile.id for profile in result] == [1, 2]
    assert result[0].simulation_ids == [1]


@pytest.mark.asyncio
async def test_list_rag_profile_definitions_returns_available_rerankers(monkeypatch):
    monkeypatch.setattr(
        rag_profiles_service,
        "list_rag_profile_definitions",
        lambda: [
            SimpleNamespace(
                strategy="crag",
                label="Corrective RAG",
                fields=(
                    SimpleNamespace(
                        name="reranker",
                        kind="enum",
                        label="Reranker",
                        required=True,
                        default="cross_encoder",
                        minimum=None,
                        maximum=None,
                        help_text="Pick a reranker.",
                        options=("cross_encoder", "none"),
                    ),
                ),
            )
        ],
    )

    result = await rag_profiles_service.list_rag_profile_definitions_srvc()

    assert all(isinstance(item, RagProfileDefinitionRead) for item in result)
    assert result[0].fields[0].options == ["cross_encoder", "none"]


@pytest.mark.asyncio
async def test_update_rag_profile_stamps_last_editor(monkeypatch):
    target = _profile(profile_id=8)
    captured = []

    async def fake_update_rag_profile(profile, profile_in, session):
        captured.append(profile_in)
        profile.name = profile_in.name or profile.name
        profile.last_edit_by_user_id = profile_in.last_edit_by_user_id
        return profile

    async def fake_to_read_with_ids(profile, session):
        return RagProfileReadWithIds(
            **profile.__dict__,
            simulation_ids=[],
        )

    monkeypatch.setattr(
        rag_profiles_service.rag_profiles_repo,
        "update_rag_profile",
        fake_update_rag_profile,
    )
    monkeypatch.setattr(
        rag_profiles_service.rag_profiles_repo,
        "to_rag_profile_read_with_ids",
        fake_to_read_with_ids,
    )

    result = await rag_profiles_service.update_rag_profile_srvc(
        target,
        RagProfileUpdateRequest(name="Renamed profile"),
        object(),
        _user(99),
    )

    assert result.name == "Renamed profile"
    assert result.last_edit_by_user_id == 99
    assert captured[0].last_edit_by_user_id == 99


@pytest.mark.asyncio
async def test_copy_rag_profile_assigns_new_owner(monkeypatch):
    source = _profile(profile_id=9, created_by_user_id=4)
    captured = []

    async def fake_copy_rag_profile(profile, copy_in, created_by_user_id, session):
        captured.append((profile, copy_in, created_by_user_id))
        return _profile(
            profile_id=10,
            name=copy_in.name,
            strategy=copy_in.strategy or profile.strategy,
            config=copy_in.config or profile.config,
            created_by_user_id=created_by_user_id,
        )

    async def fake_to_read_with_ids(profile, session):
        return RagProfileReadWithIds(
            **profile.__dict__,
            simulation_ids=[],
        )

    monkeypatch.setattr(
        rag_profiles_service.rag_profiles_repo,
        "copy_rag_profile",
        fake_copy_rag_profile,
    )
    monkeypatch.setattr(
        rag_profiles_service.rag_profiles_repo,
        "to_rag_profile_read_with_ids",
        fake_to_read_with_ids,
    )

    result = await rag_profiles_service.copy_rag_profile_srvc(
        source,
        RagProfileCopy(name="Copied CRAG"),
        object(),
        _user(77),
    )

    assert result.id == 10
    assert result.created_by_user_id == 77
    assert captured == [(source, RagProfileCopy(name="Copied CRAG"), 77)]


@pytest.mark.asyncio
async def test_delete_rag_profile_propagates_usage_guard(monkeypatch):
    target = _profile()

    async def fake_delete_rag_profile(profile, session):
        assert profile is target
        raise ValueError("Cannot delete RAG profile that has been used in simulations")

    monkeypatch.setattr(
        rag_profiles_service.rag_profiles_repo,
        "delete_rag_profile",
        fake_delete_rag_profile,
    )

    with pytest.raises(ValueError, match="Cannot delete RAG profile"):
        await rag_profiles_service.delete_rag_profile_srvc(target, object())

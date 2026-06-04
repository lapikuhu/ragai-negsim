from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from schemas.chunking_profiles_schemas import (
    ChunkingProfileCopy,
    ChunkingProfileCreate,
    ChunkingProfileReadWithIds,
    ChunkingProfileUpdate,
)
from services import chunking_profiles_service


def _profile(
    profile_id=10,
    name="Default chunking",
    strategy="recursive",
    config=None,
):
    now = datetime.now(timezone.utc)
    return SimpleNamespace(
        id=profile_id,
        name=name,
        strategy=strategy,
        config=config or {"chunk_size": 1000, "chunk_overlap": 200},
        created_at=now,
        last_updated=now,
    )


@pytest.mark.asyncio
async def test_create_chunking_profile_delegates_and_returns_ids(monkeypatch):
    captured = []
    created = _profile(profile_id=12)

    async def fake_create_chunking_profile(profile_in, session):
        captured.append(profile_in)
        return created

    async def fake_to_chunking_profile_read_with_ids(profile, session):
        assert profile is created
        return ChunkingProfileReadWithIds(
            **profile.__dict__,
            document_chunk_ids=[1, 2],
            corpus_index_ids=[3],
        )

    monkeypatch.setattr(
        chunking_profiles_service.chunking_profiles_repo,
        "create_chunking_profile",
        fake_create_chunking_profile,
    )
    monkeypatch.setattr(
        chunking_profiles_service.chunking_profiles_repo,
        "to_chunking_profile_read_with_ids",
        fake_to_chunking_profile_read_with_ids,
    )

    profile_in = ChunkingProfileCreate(
        name="Semantic chunking",
        strategy="semantic",
        config={"breakpoint_threshold_type": "percentile"},
    )
    result = await chunking_profiles_service.create_chunking_profile_srvc(
        profile_in,
        object(),
    )

    assert result.id == 12
    assert result.document_chunk_ids == [1, 2]
    assert result.corpus_index_ids == [3]
    assert captured == [profile_in]


@pytest.mark.asyncio
async def test_list_chunking_profiles_passes_filters_and_converts(monkeypatch):
    captured = []
    profiles = [_profile(1), _profile(2, strategy="semantic")]

    async def fake_list_chunking_profiles(
        session,
        skip=0,
        limit=20,
        strategy=None,
        name_contains=None,
        has_references=None,
    ):
        captured.append((skip, limit, strategy, name_contains, has_references))
        return profiles

    async def fake_to_chunking_profile_read_with_ids(profile, session):
        return ChunkingProfileReadWithIds(
            **profile.__dict__,
            document_chunk_ids=[profile.id],
            corpus_index_ids=[],
        )

    monkeypatch.setattr(
        chunking_profiles_service.chunking_profiles_repo,
        "list_chunking_profiles",
        fake_list_chunking_profiles,
    )
    monkeypatch.setattr(
        chunking_profiles_service.chunking_profiles_repo,
        "to_chunking_profile_read_with_ids",
        fake_to_chunking_profile_read_with_ids,
    )

    result = await chunking_profiles_service.list_chunking_profiles_srvc(
        object(),
        skip=5,
        limit=10,
        strategy="recursive",
        name_contains="default",
        has_references=True,
    )

    assert captured == [(5, 10, "recursive", "default", True)]
    assert [profile.id for profile in result] == [1, 2]
    assert result[0].document_chunk_ids == [1]


@pytest.mark.asyncio
async def test_get_chunking_profile_converts_with_ids(monkeypatch):
    target = _profile(profile_id=7)

    async def fake_to_chunking_profile_read_with_ids(profile, session):
        assert profile is target
        return ChunkingProfileReadWithIds(
            **profile.__dict__,
            document_chunk_ids=[11],
            corpus_index_ids=[22],
        )

    monkeypatch.setattr(
        chunking_profiles_service.chunking_profiles_repo,
        "to_chunking_profile_read_with_ids",
        fake_to_chunking_profile_read_with_ids,
    )

    result = await chunking_profiles_service.get_chunking_profile_srvc(target, object())

    assert result.id == 7
    assert result.document_chunk_ids == [11]
    assert result.corpus_index_ids == [22]


@pytest.mark.asyncio
async def test_update_chunking_profile_delegates_and_converts(monkeypatch):
    target = _profile(profile_id=8)
    captured = []

    async def fake_update_chunking_profile(profile, profile_in, session):
        captured.append(profile_in)
        profile.name = profile_in.name
        return profile

    async def fake_to_chunking_profile_read_with_ids(profile, session):
        return ChunkingProfileReadWithIds(
            **profile.__dict__,
            document_chunk_ids=[],
            corpus_index_ids=[],
        )

    monkeypatch.setattr(
        chunking_profiles_service.chunking_profiles_repo,
        "update_chunking_profile",
        fake_update_chunking_profile,
    )
    monkeypatch.setattr(
        chunking_profiles_service.chunking_profiles_repo,
        "to_chunking_profile_read_with_ids",
        fake_to_chunking_profile_read_with_ids,
    )

    result = await chunking_profiles_service.update_chunking_profile_srvc(
        target,
        ChunkingProfileUpdate(name="Renamed profile"),
        object(),
    )

    assert result.name == "Renamed profile"
    assert captured[0].model_dump(exclude_unset=True) == {"name": "Renamed profile"}


@pytest.mark.asyncio
async def test_copy_chunking_profile_delegates_and_converts(monkeypatch):
    source = _profile(profile_id=9)
    captured = []

    async def fake_copy_chunking_profile(profile, copy_in, session):
        captured.append((profile, copy_in))
        return _profile(
            profile_id=10,
            name=copy_in.name,
            strategy=copy_in.strategy or profile.strategy,
            config=copy_in.config or profile.config,
        )

    async def fake_to_chunking_profile_read_with_ids(profile, session):
        return ChunkingProfileReadWithIds(
            **profile.__dict__,
            document_chunk_ids=[],
            corpus_index_ids=[],
        )

    monkeypatch.setattr(
        chunking_profiles_service.chunking_profiles_repo,
        "copy_chunking_profile",
        fake_copy_chunking_profile,
    )
    monkeypatch.setattr(
        chunking_profiles_service.chunking_profiles_repo,
        "to_chunking_profile_read_with_ids",
        fake_to_chunking_profile_read_with_ids,
    )

    copy_in = ChunkingProfileCopy(name="Copied profile", strategy="recursive")
    result = await chunking_profiles_service.copy_chunking_profile_srvc(
        source,
        copy_in,
        object(),
    )

    assert result.id == 10
    assert result.name == "Copied profile"
    assert captured == [(source, copy_in)]


@pytest.mark.asyncio
async def test_delete_chunking_profile_delegates_and_propagates_guards(monkeypatch):
    target = _profile()

    async def fake_delete_chunking_profile(profile, session):
        assert profile is target
        raise ValueError("Cannot delete chunking profile with existing document chunks")

    monkeypatch.setattr(
        chunking_profiles_service.chunking_profiles_repo,
        "delete_chunking_profile",
        fake_delete_chunking_profile,
    )

    with pytest.raises(ValueError, match="Cannot delete chunking profile"):
        await chunking_profiles_service.delete_chunking_profile_srvc(target, object())

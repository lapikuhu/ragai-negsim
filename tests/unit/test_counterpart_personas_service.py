from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from app.schemas.counterpart_personas_schemas import (
    CounterpartPersonaCopyRequest,
    CounterpartPersonaCreateRequest,
    CounterpartPersonaReadWithIds,
    CounterpartPersonaUpdateRequest,
)
from app.services import counterpart_personas_service


def _persona(persona_id=10, created_by_user_id=1, last_edit_by_user_id=None):
    now = datetime.now(timezone.utc)
    return SimpleNamespace(
        id=persona_id,
        name=f"persona-{persona_id}",
        description="A negotiation counterpart persona",
        created_by_user_id=created_by_user_id,
        last_edit_by_user_id=last_edit_by_user_id,
        created_at=now,
        last_updated=now,
        model_dump=lambda: {
            "id": persona_id,
            "name": f"persona-{persona_id}",
            "description": "A negotiation counterpart persona",
            "created_by_user_id": created_by_user_id,
            "last_edit_by_user_id": last_edit_by_user_id,
            "created_at": now,
            "last_updated": now,
        },
    )


@pytest.mark.asyncio
async def test_create_counterpart_persona_stamps_current_user(monkeypatch, fake_user_factory):
    captured = []
    created = _persona(created_by_user_id=7)

    async def fake_create_counterpart_persona(persona_in, session):
        captured.append(persona_in)
        return created

    async def fake_to_read_with_ids(persona, session):
        return CounterpartPersonaReadWithIds(**persona.model_dump(), simulation_ids=[])

    monkeypatch.setattr(
        counterpart_personas_service.counterpart_personas_repo,
        "create_counterpart_persona",
        fake_create_counterpart_persona,
    )
    monkeypatch.setattr(
        counterpart_personas_service.counterpart_personas_repo,
        "to_counterpart_persona_read_with_ids",
        fake_to_read_with_ids,
    )

    result = await counterpart_personas_service.create_counterpart_persona_srvc(
        CounterpartPersonaCreateRequest(name="Hard bargainer", description="Pushes on price"),
        object(),
        fake_user_factory(user_id=7, roles=()),
    )

    assert result.created_by_user_id == 7
    assert captured[0].created_by_user_id == 7
    assert captured[0].name == "Hard bargainer"


@pytest.mark.asyncio
async def test_update_counterpart_persona_stamps_last_editor(monkeypatch, fake_user_factory):
    captured = []
    updated = _persona(created_by_user_id=2, last_edit_by_user_id=9)

    async def fake_update_counterpart_persona(persona, persona_in, session):
        captured.append((persona, persona_in))
        return updated

    async def fake_to_read_with_ids(persona, session):
        return CounterpartPersonaReadWithIds(**persona.model_dump(), simulation_ids=[33])

    monkeypatch.setattr(
        counterpart_personas_service.counterpart_personas_repo,
        "update_counterpart_persona",
        fake_update_counterpart_persona,
    )
    monkeypatch.setattr(
        counterpart_personas_service.counterpart_personas_repo,
        "to_counterpart_persona_read_with_ids",
        fake_to_read_with_ids,
    )

    result = await counterpart_personas_service.update_counterpart_persona_srvc(
        _persona(created_by_user_id=2),
        CounterpartPersonaUpdateRequest(name="Updated persona"),
        object(),
        fake_user_factory(user_id=9, roles=()),
    )

    assert result.last_edit_by_user_id == 9
    assert result.simulation_ids == [33]
    assert captured[0][1].last_edit_by_user_id == 9
    assert captured[0][1].name == "Updated persona"


@pytest.mark.asyncio
async def test_copy_counterpart_persona_stamps_current_user(monkeypatch, fake_user_factory):
    captured = []
    copied = _persona(persona_id=22, created_by_user_id=11)

    async def fake_copy_counterpart_persona(source_persona, copy_in, created_by_user_id, session):
        captured.append((source_persona, copy_in, created_by_user_id))
        return copied

    async def fake_to_read_with_ids(persona, session):
        return CounterpartPersonaReadWithIds(**persona.model_dump(), simulation_ids=[])

    monkeypatch.setattr(
        counterpart_personas_service.counterpart_personas_repo,
        "copy_counterpart_persona",
        fake_copy_counterpart_persona,
    )
    monkeypatch.setattr(
        counterpart_personas_service.counterpart_personas_repo,
        "to_counterpart_persona_read_with_ids",
        fake_to_read_with_ids,
    )

    result = await counterpart_personas_service.copy_counterpart_persona_srvc(
        _persona(),
        CounterpartPersonaCopyRequest(name="Copied persona"),
        object(),
        fake_user_factory(user_id=11, roles=()),
    )

    assert result.created_by_user_id == 11
    assert captured[0][1].name == "Copied persona"
    assert captured[0][2] == 11


@pytest.mark.asyncio
async def test_list_counterpart_personas_passes_filters_and_converts(monkeypatch):
    captured = []
    personas = [_persona(1), _persona(2)]

    async def fake_list_counterpart_personas(
        session,
        skip=0,
        limit=20,
        created_by_user_id=None,
        name_contains=None,
        used=None,
    ):
        captured.append((skip, limit, created_by_user_id, name_contains, used))
        return personas

    async def fake_to_read_with_ids(persona, session):
        return CounterpartPersonaReadWithIds(**persona.model_dump(), simulation_ids=[persona.id + 100])

    monkeypatch.setattr(
        counterpart_personas_service.counterpart_personas_repo,
        "list_counterpart_personas",
        fake_list_counterpart_personas,
    )
    monkeypatch.setattr(
        counterpart_personas_service.counterpart_personas_repo,
        "to_counterpart_persona_read_with_ids",
        fake_to_read_with_ids,
    )

    result = await counterpart_personas_service.list_counterpart_personas_srvc(
        object(),
        skip=5,
        limit=10,
        created_by_user_id=3,
        name_contains="hard",
        used=False,
    )

    assert captured == [(5, 10, 3, "hard", False)]
    assert [persona.simulation_ids for persona in result] == [[101], [102]]


@pytest.mark.asyncio
async def test_delete_counterpart_persona_propagates_repo_guard(monkeypatch):
    async def fake_delete_counterpart_persona(persona, session):
        raise ValueError("Cannot modify counterpart persona that has been used in simulations")

    monkeypatch.setattr(
        counterpart_personas_service.counterpart_personas_repo,
        "delete_counterpart_persona",
        fake_delete_counterpart_persona,
    )

    with pytest.raises(ValueError, match="used in simulations"):
        await counterpart_personas_service.delete_counterpart_persona_srvc(_persona(), object())

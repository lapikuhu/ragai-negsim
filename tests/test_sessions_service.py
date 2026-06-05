from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from app.schemas.sessions_schemas import (
    SessionCreate,
    SessionCreateRequest,
    SessionEnd,
    SessionHeartbeat,
    SessionUpdateRequest,
)
from app.services import sessions_service


def _user(user_id=1, roles=None):
    return SimpleNamespace(id=user_id, username=f"user-{user_id}", roles=roles or [])


def _admin(user_id=1):
    return _user(user_id=user_id, roles=[SimpleNamespace(name="admin")])


def _session(
    session_id=10,
    user_id=1,
    session_token="session-token",
    expires_at=None,
    last_seen_at=None,
    ended_at=None,
):
    now = datetime.now(timezone.utc)
    return SimpleNamespace(
        id=session_id,
        session_token=session_token,
        user_id=user_id,
        created_at=now,
        expires_at=expires_at,
        last_seen_at=last_seen_at,
        ended_at=ended_at,
    )


@pytest.mark.asyncio
async def test_create_session_generates_token_and_stamps_last_seen(monkeypatch):
    captured = []
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    expires_at = now + timedelta(hours=2)

    async def fake_get_user_by_id(user_id, session):
        assert user_id == 7
        return _user(7)

    async def fake_create_session(session_in, session):
        captured.append(session_in)
        return _session(
            session_id=12,
            user_id=session_in.user_id,
            session_token=session_in.session_token,
            expires_at=session_in.expires_at,
            last_seen_at=session_in.last_seen_at,
        )

    monkeypatch.setattr(sessions_service.users_repo, "get_user_by_id", fake_get_user_by_id)
    monkeypatch.setattr(sessions_service.sessions_repo, "create_session", fake_create_session)
    monkeypatch.setattr(sessions_service, "_generate_session_token", lambda: "opaque-token")
    monkeypatch.setattr(sessions_service, "utc_now", lambda: now)

    result = await sessions_service.create_session_srvc(
        SessionCreateRequest(user_id=7, expires_at=expires_at),
        object(),
        _admin(),
    )

    assert result.id == 12
    assert result.user_id == 7
    assert result.expires_at == expires_at
    assert result.last_seen_at == now
    assert captured == [
        SessionCreate(
            user_id=7,
            expires_at=expires_at,
            session_token="opaque-token",
            last_seen_at=now,
        )
    ]


@pytest.mark.asyncio
async def test_create_session_requires_existing_user(monkeypatch):
    async def fake_get_user_by_id(user_id, session):
        return None

    monkeypatch.setattr(sessions_service.users_repo, "get_user_by_id", fake_get_user_by_id)

    with pytest.raises(ValueError, match="User not found"):
        await sessions_service.create_session_srvc(
            SessionCreateRequest(user_id=99),
            object(),
            _admin(),
        )


@pytest.mark.asyncio
async def test_list_sessions_passes_filters_and_converts(monkeypatch):
    captured = []
    sessions = [_session(1), _session(2, user_id=3)]

    async def fake_list_sessions(
        session,
        skip=0,
        limit=20,
        user_id=None,
        active=None,
        expired=None,
    ):
        captured.append((skip, limit, user_id, active, expired))
        return sessions

    monkeypatch.setattr(sessions_service.sessions_repo, "list_sessions", fake_list_sessions)

    result = await sessions_service.list_sessions_srvc(
        object(),
        skip=5,
        limit=10,
        user_id=3,
        active=True,
        expired=False,
    )

    assert captured == [(5, 10, 3, True, False)]
    assert [session.id for session in result] == [1, 2]


@pytest.mark.asyncio
async def test_update_session_passes_patch_payload(monkeypatch):
    captured = []
    target = _session()
    ended_at = datetime(2026, 1, 1, tzinfo=timezone.utc)

    async def fake_update_session(session_obj, session_in, session):
        captured.append(session_in)
        session_obj.ended_at = session_in.ended_at
        return session_obj

    monkeypatch.setattr(sessions_service.sessions_repo, "update_session", fake_update_session)

    result = await sessions_service.update_session_srvc(
        target,
        SessionUpdateRequest(ended_at=ended_at),
        object(),
    )

    assert result.ended_at == ended_at
    assert captured[0].model_dump(exclude_unset=True) == {"ended_at": ended_at}


@pytest.mark.asyncio
async def test_heartbeat_defaults_last_seen_at(monkeypatch):
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    target = _session(last_seen_at=None)
    captured = []

    async def fake_heartbeat_session(session_obj, heartbeat_in, session):
        captured.append(heartbeat_in)
        session_obj.last_seen_at = heartbeat_in.last_seen_at
        return session_obj

    monkeypatch.setattr(sessions_service, "utc_now", lambda: now)
    monkeypatch.setattr(sessions_service.sessions_repo, "heartbeat_session", fake_heartbeat_session)

    result = await sessions_service.heartbeat_session_srvc(
        target,
        SessionHeartbeat(),
        object(),
    )

    assert result.last_seen_at == now
    assert captured == [SessionHeartbeat(last_seen_at=now)]


@pytest.mark.asyncio
async def test_end_defaults_ended_at(monkeypatch):
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    target = _session(ended_at=None)
    captured = []

    async def fake_end_session(session_obj, end_in, session):
        captured.append(end_in)
        session_obj.ended_at = end_in.ended_at
        return session_obj

    monkeypatch.setattr(sessions_service, "utc_now", lambda: now)
    monkeypatch.setattr(sessions_service.sessions_repo, "end_session", fake_end_session)

    result = await sessions_service.end_session_srvc(target, SessionEnd(), object())

    assert result.ended_at == now
    assert captured == [SessionEnd(ended_at=now)]


@pytest.mark.asyncio
async def test_delete_session_delegates_reference_guard(monkeypatch):
    async def fake_delete_session(session_obj, session):
        raise ValueError("Cannot delete session with simulations")

    monkeypatch.setattr(sessions_service.sessions_repo, "delete_session", fake_delete_session)

    with pytest.raises(ValueError, match="Cannot delete session with simulations"):
        await sessions_service.delete_session_srvc(_session(), object())

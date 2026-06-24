from datetime import datetime, timezone
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app import main as main_module
from app.core import dependencies
from app.schemas.sessions_schemas import SessionRead
from app.web.routes import sessions_route


def _session(session_id=1):
    return SimpleNamespace(
        id=session_id,
        user_id=1,
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        expires_at=None,
        last_seen_at=None,
        ended_at=None,
    )


def test_heartbeat_accepts_missing_body(monkeypatch):
    target = _session()
    captured = []

    async def fake_startup_seed():
        return None

    async def fake_get_current_user():
        return SimpleNamespace(
            id=1,
            username="admin",
            roles=[SimpleNamespace(name="admin")],
        )

    async def fake_get_session():
        yield object()

    async def fake_user_has_role(_user, _role_name, _session):
        return True

    def fake_get_admin_session():
        return target

    async def fake_heartbeat_session_srvc(user_session, heartbeat_data, session):
        captured.append(heartbeat_data)
        return SessionRead(
            id=user_session.id,
            user_id=user_session.user_id,
            created_at=user_session.created_at,
            expires_at=user_session.expires_at,
            last_seen_at=datetime(2026, 1, 2, tzinfo=timezone.utc),
            ended_at=user_session.ended_at,
        )

    monkeypatch.setattr(main_module, "startup_seed", fake_startup_seed)
    monkeypatch.setattr(dependencies, "user_has_role", fake_user_has_role)
    monkeypatch.setattr(
        sessions_route.sessions_service,
        "heartbeat_session_srvc",
        fake_heartbeat_session_srvc,
    )

    app = main_module.app
    app.dependency_overrides[dependencies.get_current_user] = fake_get_current_user
    app.dependency_overrides[dependencies.get_session] = fake_get_session
    app.dependency_overrides[dependencies.get_admin_session] = fake_get_admin_session

    try:
        with TestClient(app) as client:
            response = client.post("/sessions/1/heartbeat")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["last_seen_at"] == "2026-01-02T00:00:00Z"
    assert captured[0].last_seen_at is None

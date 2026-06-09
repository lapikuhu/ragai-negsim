from datetime import datetime, timezone
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app import main as main_module
from app.core import dependencies
from app.schemas.scenarios_schemas import (
    ScenarioAuthoringReadWithIds,
    ScenarioContextGenerateResponse,
    ScenarioPublicReadWithIds,
)
from app.services import scenarios_service


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _public_scenario() -> ScenarioPublicReadWithIds:
    return ScenarioPublicReadWithIds(
        id=10,
        name="Late checkout fee negotiation",
        public_context={"issue": "late checkout fee"},
        created_by_user_id=1,
        last_edit_by_user_id=None,
        created_at=_now(),
        last_updated=_now(),
        simulation_ids=[51],
    )


def _authoring_scenario() -> ScenarioAuthoringReadWithIds:
    return ScenarioAuthoringReadWithIds(
        id=10,
        name="Late checkout fee negotiation",
        description="AUTHORING-DESCRIPTION",
        public_context={"issue": "late checkout fee"},
        side_a_private_context={"reservation": "SIDE-A-SECRET"},
        side_b_private_context={"reservation": "SIDE-B-SECRET"},
        created_by_user_id=1,
        last_edit_by_user_id=None,
        created_at=_now(),
        last_updated=_now(),
        simulation_ids=[51],
    )


def test_scenarios_routes_keep_public_and_authoring_views_separate(monkeypatch):
    async def fake_startup_seed():
        return None

    async def fake_get_current_user():
        return SimpleNamespace(id=1, username="teacher", roles=[SimpleNamespace(name="teacher")])

    async def fake_get_session():
        yield object()

    async def fake_user_has_role(_user, _role_name, _session):
        return True

    async def fake_list_scenarios(*args, **kwargs):
        return [_public_scenario()]

    async def fake_get_scenario(*args, **kwargs):
        return _public_scenario()

    async def fake_get_scenario_authoring(*args, **kwargs):
        return _authoring_scenario()

    monkeypatch.setattr(dependencies, "user_has_role", fake_user_has_role)
    monkeypatch.setattr(
        scenarios_service,
        "list_scenarios_srvc",
        fake_list_scenarios,
    )
    monkeypatch.setattr(
        scenarios_service,
        "get_scenario_srvc",
        fake_get_scenario,
    )
    monkeypatch.setattr(
        scenarios_service,
        "get_scenario_authoring_srvc",
        fake_get_scenario_authoring,
        raising=False,
    )

    app = main_module.app
    monkeypatch.setattr(main_module, "startup_seed", fake_startup_seed)
    app.dependency_overrides[dependencies.get_current_user] = fake_get_current_user
    app.dependency_overrides[dependencies.get_session] = fake_get_session
    app.dependency_overrides[dependencies.get_visible_scenario] = lambda: SimpleNamespace(id=10)
    app.dependency_overrides[dependencies.get_writable_scenario] = lambda: SimpleNamespace(id=10)

    try:
        with TestClient(app) as client:
            list_response = client.get("/scenarios/")
            assert list_response.status_code == 200
            assert list_response.json()[0]["public_context"]["issue"] == "late checkout fee"
            assert "description" not in list_response.json()[0]
            assert "side_a_private_context" not in list_response.json()[0]

            get_response = client.get("/scenarios/10")
            assert get_response.status_code == 200
            assert "description" not in get_response.json()
            assert "side_b_private_context" not in get_response.json()

            authoring_response = client.get("/scenarios/10/authoring")
            assert authoring_response.status_code == 200
            assert authoring_response.json()["description"] == "AUTHORING-DESCRIPTION"
            assert authoring_response.json()["side_a_private_context"]["reservation"] == "SIDE-A-SECRET"
            assert authoring_response.json()["side_b_private_context"]["reservation"] == "SIDE-B-SECRET"
    finally:
        app.dependency_overrides.clear()


def test_generate_context_route_returns_authoring_preview(monkeypatch):
    async def fake_startup_seed():
        return None

    async def fake_get_current_user():
        return SimpleNamespace(id=1, username="teacher", roles=[SimpleNamespace(name="teacher")])

    async def fake_get_session():
        yield object()

    async def fake_user_has_role(_user, _role_name, _session):
        return True

    async def fake_generate_scenario_context(data, model):
        assert data.name == "Hotel late checkout"
        return ScenarioContextGenerateResponse(
            public_context={"issue": "late checkout"},
            side_a_private_context={"goal": "avoid fee"},
            side_b_private_context={"goal": "protect revenue"},
        )

    app = main_module.app
    monkeypatch.setattr(main_module, "startup_seed", fake_startup_seed)
    monkeypatch.setattr(dependencies, "user_has_role", fake_user_has_role)
    monkeypatch.setattr(
        scenarios_service,
        "generate_scenario_context_srvc",
        fake_generate_scenario_context,
    )
    app.dependency_overrides[dependencies.get_current_user] = fake_get_current_user
    app.dependency_overrides[dependencies.get_session] = fake_get_session
    app.dependency_overrides[dependencies.get_chat_model] = lambda: object()

    try:
        with TestClient(app) as client:
            response = client.post(
                "/scenarios/generate-context",
                json={
                    "name": "Hotel late checkout",
                    "description": "A guest wants more time and the manager must balance policy and satisfaction.",
                },
            )
        assert response.status_code == 200
        assert response.json()["public_context"]["issue"] == "late checkout"
        assert response.json()["side_a_private_context"]["goal"] == "avoid fee"
    finally:
        app.dependency_overrides.clear()

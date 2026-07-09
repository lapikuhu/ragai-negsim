from datetime import datetime, timezone
from types import SimpleNamespace

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
        description="PUBLIC-DESCRIPTION",
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
        side_a_summary="Side A should avoid the fee.",
        side_b_summary="Side B should protect policy.",
        created_by_user_id=1,
        last_edit_by_user_id=None,
        created_at=_now(),
        last_updated=_now(),
        simulation_ids=[51],
    )


def test_scenarios_routes_keep_public_and_authoring_views_separate(
    monkeypatch,
    api_client,
    test_app,
    override_current_user,
    override_session,
    allow_roles,
):
    async def fake_list_scenarios(*args, **kwargs):
        return [_public_scenario()]

    async def fake_get_scenario(*args, **kwargs):
        return _public_scenario()

    async def fake_get_scenario_authoring(*args, **kwargs):
        return _authoring_scenario()

    override_current_user(username="teacher", roles=["teacher"])
    override_session()
    allow_roles("teacher")
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

    test_app.dependency_overrides[dependencies.get_visible_scenario] = lambda: SimpleNamespace(id=10)
    test_app.dependency_overrides[dependencies.get_writable_scenario] = lambda: SimpleNamespace(id=10)

    list_response = api_client.get("/scenarios/")
    assert list_response.status_code == 200
    assert list_response.json()[0]["public_context"]["issue"] == "late checkout fee"
    assert list_response.json()[0]["description"] == "PUBLIC-DESCRIPTION"
    assert "side_a_private_context" not in list_response.json()[0]

    get_response = api_client.get("/scenarios/10")
    assert get_response.status_code == 200
    assert get_response.json()["description"] == "PUBLIC-DESCRIPTION"
    assert "side_b_private_context" not in get_response.json()
    assert "side_a_summary" not in get_response.json()
    assert "side_b_summary" not in get_response.json()

    authoring_response = api_client.get("/scenarios/10/authoring")
    assert authoring_response.status_code == 200
    assert authoring_response.json()["description"] == "AUTHORING-DESCRIPTION"
    assert authoring_response.json()["side_a_private_context"]["reservation"] == "SIDE-A-SECRET"
    assert authoring_response.json()["side_b_private_context"]["reservation"] == "SIDE-B-SECRET"
    assert authoring_response.json()["side_a_summary"] == "Side A should avoid the fee."
    assert authoring_response.json()["side_b_summary"] == "Side B should protect policy."


def test_generate_context_route_returns_authoring_preview(
    monkeypatch,
    api_client,
    test_app,
    override_current_user,
    override_session,
    allow_roles,
):
    async def fake_generate_scenario_context(data, model):
        assert data.name == "Hotel late checkout"
        return ScenarioContextGenerateResponse(
            public_context={"issue": "late checkout"},
            side_a_private_context={"goal": "avoid fee"},
            side_b_private_context={"goal": "protect revenue"},
            side_a_summary="You want to avoid the fee.",
            side_b_summary="You want to protect revenue.",
        )

    override_current_user(username="teacher", roles=["teacher"])
    override_session()
    allow_roles("teacher")
    monkeypatch.setattr(
        scenarios_service,
        "generate_scenario_context_srvc",
        fake_generate_scenario_context,
    )
    test_app.dependency_overrides[dependencies.get_chat_model] = lambda: object()

    response = api_client.post(
        "/scenarios/generate-context",
        json={
            "name": "Hotel late checkout",
            "description": "A guest wants more time and the manager must balance policy and satisfaction.",
        },
    )

    assert response.status_code == 200
    assert response.json()["public_context"]["issue"] == "late checkout"
    assert response.json()["side_a_private_context"]["goal"] == "avoid fee"
    assert response.json()["side_a_summary"] == "You want to avoid the fee."
    assert response.json()["side_b_summary"] == "You want to protect revenue."

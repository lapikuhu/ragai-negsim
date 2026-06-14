from datetime import datetime, timezone
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app import main as main_module
from app.core import dependencies
from app.schemas.simulations_schemas import (
    NegotiationStateSchema,
    SimulationEvaluationListItem,
    SimulationEvaluationListResponse,
    SimulationRead,
    SimulationReadWithState,
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _user(user_id: int, *roles: str) -> SimpleNamespace:
    return SimpleNamespace(
        id=user_id,
        username=f"user-{user_id}",
        roles=[SimpleNamespace(name=role) for role in roles],
    )


def _simulation_read(simulation_id: int, *, teacher_id: int | None = None, teacher_feedback: str | None = None) -> SimulationRead:
    return SimulationRead(
        id=simulation_id,
        name=f"simulation-{simulation_id}",
        description="Evaluation item",
        status="completed",
        session_id=None,
        user_id_owner=1,
        user_id_participant=2,
        scenario_id=100,
        corpus_id=11,
        corpus_index_id=77,
        rag_profile_id=500,
        coach_prompt_id=None,
        counterpart_prompt_id=None,
        evaluator_prompt_id=None,
        counter_part_side_persona_id=None,
        user_side="side_a",
        teacher_reviewed=teacher_id is not None,
        teacher_id=teacher_id,
        teacher_feedback=teacher_feedback,
        reviewed_at=_now() if teacher_id is not None else None,
        created_at=_now(),
        last_updated=_now(),
    )


def test_evaluations_api_routes_support_teacher_admin_workflow(monkeypatch):
    async def fake_startup_seed():
        return None

    async def fake_get_session():
        yield object()

    async def fake_get_current_user():
        return _user(7, "teacher")

    async def fake_user_has_role(user, role_name, session):
        return any(role.name == role_name for role in user.roles)

    async def fake_list_reviews(session, *, current_user, skip, limit):
        assert current_user.id == 7
        assert skip == 0
        assert limit == 20
        return SimulationEvaluationListResponse(
            items=[
                SimulationEvaluationListItem(
                    **_simulation_read(31, teacher_id=7, teacher_feedback="Strong BATNA framing").model_dump(),
                    scenario_name="Salary",
                    participant_user_id=2,
                )
            ],
            skip=0,
            limit=20,
            has_more=False,
        )

    async def fake_list_completed(session, *, current_user, skip, limit):
        assert current_user.id == 7
        return SimulationEvaluationListResponse(
            items=[
                SimulationEvaluationListItem(
                    **_simulation_read(41).model_dump(),
                    scenario_name="Vendor",
                    participant_user_id=2,
                )
            ],
            skip=skip,
            limit=limit,
            has_more=True,
        )

    async def fake_get_readable_simulation():
        return SimpleNamespace(id=41, status="completed")

    async def fake_get_simulation(simulation):
        return SimulationReadWithState(
            **_simulation_read(41).model_dump(),
            negotiation_state=NegotiationStateSchema(current_phase="ended", user_side="side_a", data={}),
            messages=[],
        )

    monkeypatch.setattr(main_module, "startup_seed", fake_startup_seed)
    from app.services import simulations_service

    monkeypatch.setattr(simulations_service, "list_reviewed_simulations_srvc", fake_list_reviews)
    monkeypatch.setattr(simulations_service, "list_completed_simulations_srvc", fake_list_completed)
    monkeypatch.setattr(simulations_service, "get_simulation_srvc", fake_get_simulation)

    app = main_module.app
    app.dependency_overrides[dependencies.get_current_user] = fake_get_current_user
    app.dependency_overrides[dependencies.get_session] = fake_get_session
    app.dependency_overrides[dependencies.get_readable_simulation] = fake_get_readable_simulation
    monkeypatch.setattr(dependencies, "user_has_role", fake_user_has_role)

    try:
        with TestClient(app) as client:
            reviews_response = client.get("/simulations/reviews")
            completed_response = client.get("/simulations/completed")
            simulation_response = client.get("/simulations/41")

        assert reviews_response.status_code == 200
        assert reviews_response.json()["items"][0]["teacher_feedback"] == "Strong BATNA framing"
        assert completed_response.status_code == 200
        assert completed_response.json()["has_more"] is True
        assert simulation_response.status_code == 200
        assert simulation_response.json()["status"] == "completed"
    finally:
        app.dependency_overrides.clear()


def test_review_update_and_delete_routes_allow_admin(monkeypatch):
    async def fake_startup_seed():
        return None

    async def fake_get_session():
        yield object()

    async def fake_get_current_user():
        return _user(99, "admin")

    async def fake_get_reviewable_simulation():
        return SimpleNamespace(id=31, status="completed", teacher_id=7, teacher_reviewed=True)

    async def fake_update_review(simulation, review_data, session, current_user):
        assert current_user.id == 99
        assert review_data.teacher_feedback == "Updated review"
        return _simulation_read(31, teacher_id=7, teacher_feedback="Updated review")

    async def fake_delete_review(simulation, session, current_user):
        assert current_user.id == 99
        return _simulation_read(31)

    monkeypatch.setattr(main_module, "startup_seed", fake_startup_seed)
    from app.services import simulations_service

    monkeypatch.setattr(simulations_service, "update_review_simulation_srvc", fake_update_review)
    monkeypatch.setattr(simulations_service, "delete_review_simulation_srvc", fake_delete_review)

    app = main_module.app
    app.dependency_overrides[dependencies.get_current_user] = fake_get_current_user
    app.dependency_overrides[dependencies.get_session] = fake_get_session
    app.dependency_overrides[dependencies.get_teacher_review_simulation] = fake_get_reviewable_simulation

    try:
        with TestClient(app) as client:
            patch_response = client.patch(
                "/simulations/31/review",
                json={"teacher_feedback": "Updated review"},
            )
            delete_response = client.delete("/simulations/31/review")

        assert patch_response.status_code == 200
        assert patch_response.json()["teacher_feedback"] == "Updated review"
        assert delete_response.status_code == 204
    finally:
        app.dependency_overrides.clear()

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from schemas.simulations_schemas import (
    SimulationCreate,
    SimulationCreateRequest,
    SimulationReadWithState,
    SimulationStartRequest,
    SimulationTurnRequest,
    SimulationTurnResponse,
    SimulationUpdateRequest,
)
from services import simulations_service


def _user(user_id=1):
    return SimpleNamespace(id=user_id, username=f"user-{user_id}", roles=[])


def _admin(user_id=1):
    return SimpleNamespace(
        id=user_id,
        username=f"user-{user_id}",
        roles=[SimpleNamespace(name="admin")],
    )


def _simulation(
    simulation_id=10,
    status="created",
    user_id_owner=1,
    user_id_participant=None,
    user_side="side_a",
    negotiation_state=None,
    messages=None,
):
    now = datetime.now(timezone.utc)
    return SimpleNamespace(
        id=simulation_id,
        name=f"simulation-{simulation_id}",
        description="A negotiation simulation",
        status=status,
        session_id=None,
        user_id_owner=user_id_owner,
        user_id_participant=user_id_participant,
        scenario_id=100,
        corpus_id=200,
        counter_part_side_persona_id=300,
        user_side=user_side,
        teacher_reviewed=False,
        teacher_id=None,
        teacher_feedback=None,
        reviewed_at=None,
        created_at=now,
        last_updated=now,
        negotiation_state=negotiation_state or {},
        messages=messages or [],
        model_dump=lambda: {
            "id": simulation_id,
            "name": f"simulation-{simulation_id}",
            "description": "A negotiation simulation",
            "status": status,
            "session_id": None,
            "user_id_owner": user_id_owner,
            "user_id_participant": user_id_participant,
            "scenario_id": 100,
            "corpus_id": 200,
            "counter_part_side_persona_id": 300,
            "user_side": user_side,
            "teacher_reviewed": False,
            "teacher_id": None,
            "teacher_feedback": None,
            "reviewed_at": None,
            "created_at": now,
            "last_updated": now,
            "negotiation_state": negotiation_state or {},
            "messages": messages or [],
        },
    )


@pytest.mark.asyncio
async def test_create_simulation_stamps_current_user(monkeypatch):
    captured = []
    created = _simulation(user_id_owner=7)

    async def fake_create_simulation(simulation_in, session):
        captured.append(simulation_in)
        return created

    monkeypatch.setattr(
        simulations_service.simulations_repo,
        "create_simulation",
        fake_create_simulation,
    )

    result = await simulations_service.create_simulation_srvc(
        SimulationCreateRequest(
            name="Salary negotiation",
            description="Practice pay discussions",
            corpus_id=200,
            scenario_id=100,
            counter_part_side_persona_id=300,
            user_side="side_a",
        ),
        object(),
        _user(7),
    )

    assert result.user_id_owner == 7
    assert captured == [
        SimulationCreate(
            name="Salary negotiation",
            description="Practice pay discussions",
            user_id_owner=7,
            corpus_id=200,
            session_id=None,
            user_id_participant=None,
            scenario_id=100,
            counter_part_side_persona_id=300,
            user_side="side_a",
        )
    ]


@pytest.mark.asyncio
async def test_list_simulations_passes_filters_and_converts(monkeypatch):
    captured = []
    simulations = [_simulation(1), _simulation(2)]

    async def fake_list_simulations(
        session,
        skip=0,
        limit=20,
        status=None,
        owner_id=None,
        participant_id=None,
        teacher_id=None,
        corpus_id=None,
        session_id=None,
        scenario_id=None,
    ):
        captured.append(
            (
                skip,
                limit,
                status,
                owner_id,
                participant_id,
                teacher_id,
                corpus_id,
                session_id,
                scenario_id,
            )
        )
        return simulations

    monkeypatch.setattr(
        simulations_service.simulations_repo,
        "list_simulations",
        fake_list_simulations,
    )

    result = await simulations_service.list_simulations_srvc(
        object(),
        skip=5,
        limit=10,
        status="active",
        owner_id=3,
        participant_id=4,
        corpus_id=200,
        session_id=8,
        scenario_id=100,
    )

    assert captured == [(5, 10, "active", 3, 4, None, 200, 8, 100)]
    assert [simulation.id for simulation in result] == [1, 2]


@pytest.mark.asyncio
async def test_list_simulations_filters_inaccessible_records_for_non_admin(monkeypatch):
    simulations = [
        _simulation(1, user_id_owner=7),
        _simulation(2, user_id_participant=7),
        _simulation(3, user_id_owner=99, user_id_participant=100),
    ]

    async def fake_list_simulations(**kwargs):
        return simulations

    monkeypatch.setattr(
        simulations_service.simulations_repo,
        "list_simulations",
        fake_list_simulations,
    )

    student_result = await simulations_service.list_simulations_srvc(
        object(),
        current_user=_user(7),
    )
    admin_result = await simulations_service.list_simulations_srvc(
        object(),
        current_user=_admin(9),
    )

    assert [simulation.id for simulation in student_result] == [1, 2]
    assert [simulation.id for simulation in admin_result] == [1, 2, 3]


@pytest.mark.asyncio
async def test_update_simulation_does_not_patch_graph_state(monkeypatch):
    captured = []
    updated = _simulation(status="paused")

    async def fake_update_simulation(simulation, simulation_in, session):
        captured.append(simulation_in)
        return updated

    monkeypatch.setattr(
        simulations_service.simulations_repo,
        "update_simulation",
        fake_update_simulation,
    )

    result = await simulations_service.update_simulation_srvc(
        _simulation(status="active"),
        SimulationUpdateRequest(name="Updated simulation", status="paused"),
        object(),
    )

    assert result.status == "paused"
    assert captured[0].model_dump(exclude_unset=True) == {
        "name": "Updated simulation",
        "status": "paused",
    }


@pytest.mark.asyncio
async def test_start_simulation_initializes_graph_state_and_activates(monkeypatch):
    captured_status = []
    simulation = _simulation(status="created", user_id_owner=7)

    async def fake_update_simulation(simulation_obj, simulation_in, session):
        simulation_obj.negotiation_state = simulation_in.negotiation_state.model_dump()
        simulation_obj.messages = [message.model_dump() for message in simulation_in.messages]
        simulation_obj.status = simulation_in.status
        return simulation_obj

    async def fake_update_status(simulation_obj, status_in, session):
        captured_status.append(status_in.status)
        simulation_obj.status = status_in.status
        return simulation_obj

    monkeypatch.setattr(
        simulations_service.simulations_repo,
        "update_simulation",
        fake_update_simulation,
    )
    monkeypatch.setattr(
        simulations_service.simulations_repo,
        "update_simulation_status",
        fake_update_status,
    )

    result = await simulations_service.start_simulation_srvc(
        simulation,
        SimulationStartRequest(
            side_a={"name": "Buyer", "role": "buyer"},
            side_b={"name": "Seller", "role": "seller"},
            opening_message="I would like to discuss the price.",
        ),
        object(),
        _user(7),
    )

    assert isinstance(result, SimulationReadWithState)
    assert result.status == "active"
    assert result.negotiation_state.user_side == "side_a"
    assert result.negotiation_state.current_phase == "opening"
    assert result.negotiation_state.data["side_a"]["name"] == "Buyer"
    assert result.messages[0].content == "I would like to discuss the price."
    assert captured_status == []


@pytest.mark.asyncio
async def test_submit_turn_invokes_graph_and_persists_json_safe_response(monkeypatch):
    captured_state = []
    simulation = _simulation(
        status="active",
        user_id_owner=7,
        negotiation_state={
            "current_phase": "opening",
            "user_side": "side_a",
            "data": {
                "session_id": "10",
                "user_id": "7",
                "user_side": "side_a",
                "phase": "opening",
                "messages": [],
                "event_log": [],
            },
        },
    )

    class FakeGraph:
        def invoke(self, state):
            captured_state.append(state)
            return {
                **state,
                "phase": "bargaining",
                "should_pause": True,
                "pause_reason": "counterpart_response_ready",
                "side_b_response": "I can move a little, but not that far.",
                "coach_advice": {"summary": "Hold near target."},
                "messages": [
                    *state["messages"],
                    {
                        "role": "assistant",
                        "content": "I can move a little, but not that far.",
                        "side": "side_b",
                    },
                ],
                "event_log": ["orchestrator:paused_for_user"],
            }

    async def fake_update_simulation(simulation_obj, simulation_in, session):
        simulation_obj.negotiation_state = simulation_in.negotiation_state.model_dump()
        simulation_obj.messages = [message.model_dump() for message in simulation_in.messages]
        simulation_obj.status = simulation_in.status
        return simulation_obj

    monkeypatch.setattr(
        simulations_service.simulations_repo,
        "update_simulation",
        fake_update_simulation,
    )

    result = await simulations_service.submit_simulation_turn_srvc(
        simulation,
        SimulationTurnRequest(message="Could you do 95?"),
        object(),
        _user(7),
        FakeGraph(),
    )

    assert isinstance(result, SimulationTurnResponse)
    assert result.status == "paused"
    assert result.phase == "bargaining"
    assert result.should_pause is True
    assert result.pause_reason == "counterpart_response_ready"
    assert result.coach_advice == {"summary": "Hold near target."}
    assert result.counterpart_response == "I can move a little, but not that far."
    assert captured_state[0]["messages"][0]["content"] == "Could you do 95?"
    assert simulation.negotiation_state["data"]["phase"] == "bargaining"


@pytest.mark.asyncio
async def test_cancel_simulation_uses_status_transition(monkeypatch):
    captured = []
    simulation = _simulation(status="paused")

    async def fake_update_status(simulation_obj, status_in, session):
        captured.append(status_in.status)
        simulation_obj.status = status_in.status
        return simulation_obj

    monkeypatch.setattr(
        simulations_service.simulations_repo,
        "update_simulation_status",
        fake_update_status,
    )

    result = await simulations_service.cancel_simulation_srvc(simulation, object())

    assert result.status == "cancelled"
    assert captured == ["cancelled"]

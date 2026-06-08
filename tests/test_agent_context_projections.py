import pytest

from app.airag.chains.agents.context_projections import (
    project_coach_state,
    project_counterpart_state,
    project_evaluator_state,
    project_intent_classifier_state,
)


def parent_state():
    return {
        "simulation_id": "10",
        "session_id": "10",
        "app_session_id": 44,
        "user_id": "7",
        "user_side": "side_b",
        "scenario_public_context": {"sentinel": "PUBLIC"},
        "side_a_private_context": {"sentinel": "SIDE_A_SECRET"},
        "side_b_private_context": {"sentinel": "SIDE_B_SECRET"},
        "counterpart_persona": {"sentinel": "PERSONA"},
        "side_a": {"sentinel": "RAW_SIDE_A"},
        "side_b": {"sentinel": "RAW_SIDE_B"},
        "messages": [{"role": "user", "content": "LATEST-STUDENT"}],
        "phase": "bargaining",
        "active_side": "side_b",
        "current_offer": {"terms": {"sentinel": "OFFER"}},
        "offer_history": [{"terms": {"sentinel": "HISTORY"}}],
        "coach_advice": {"sentinel": "COACH_SECRET"},
        "evaluation": {"sentinel": "EVALUATOR_SECRET"},
        "final_evaluation": {"sentinel": "FINAL_SECRET"},
        "retrieval_result": {"summary": "SHARED_RETRIEVAL"},
        "side_a_response": "COUNTERPART_RESPONSE",
        "turn_count": 2,
        "evaluation_mode": "rolling",
        "terminal_reason": None,
        "requested_action": None,
        "event_log": ["INTERNAL_EVENT"],
    }


def test_counterpart_projection_contains_only_counterpart_privileges():
    projected = project_counterpart_state(parent_state())
    serialized = repr(projected)

    assert projected["scenario_public_context"]["sentinel"] == "PUBLIC"
    assert projected["own_private_context"]["sentinel"] == "SIDE_A_SECRET"
    assert projected["counterpart_persona"]["sentinel"] == "PERSONA"
    assert "SIDE_B_SECRET" not in serialized
    assert "COACH_SECRET" not in serialized
    assert "EVALUATOR_SECRET" not in serialized
    assert "RAW_SIDE_A" not in serialized
    assert "SHARED_RETRIEVAL" not in serialized
    assert projected["event_log"] == []


def test_coach_projection_contains_only_student_privileges():
    projected = project_coach_state(parent_state())
    serialized = repr(projected)

    assert projected["student_private_context"]["sentinel"] == "SIDE_B_SECRET"
    assert "SIDE_A_SECRET" not in serialized
    assert "EVALUATOR_SECRET" not in serialized
    assert "PERSONA" not in serialized


def test_evaluator_projection_is_omniscient():
    projected = project_evaluator_state(parent_state())
    serialized = repr(projected)

    for sentinel in (
        "PUBLIC",
        "SIDE_A_SECRET",
        "SIDE_B_SECRET",
        "COACH_SECRET",
        "EVALUATOR_SECRET",
    ):
        assert sentinel in serialized


def test_intent_projection_contains_only_latest_student_message():
    state = parent_state()
    state["messages"] = [
        {"role": "assistant", "content": "OLD-COUNTERPART"},
        {"role": "user", "content": "LATEST-STUDENT"},
    ]

    projected = project_intent_classifier_state(state)

    assert projected == {
        "messages": [{"role": "user", "content": "LATEST-STUDENT"}],
        "event_log": [],
    }


@pytest.mark.parametrize(
    "projector",
    [
        project_counterpart_state,
        project_coach_state,
        project_evaluator_state,
        project_intent_classifier_state,
    ],
)
def test_projections_do_not_share_mutable_parent_values(projector):
    state = parent_state()
    projected = projector(state)

    if "messages" in projected:
        projected["messages"].append({"role": "user", "content": "MUTATED"})

    assert all(
        message.get("content") != "MUTATED"
        for message in state["messages"]
    )

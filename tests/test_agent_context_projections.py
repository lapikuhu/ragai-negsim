import pytest

from app.airag.chains.agents.context_projections import (
    project_coach_state,
    project_counterpart_state,
    project_evaluator_state,
    project_intent_classifier_state,
    project_simulation_learner_state,
)


def test_counterpart_projection_contains_only_counterpart_privileges(agent_parent_state):
    projected = project_counterpart_state(agent_parent_state)
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


def test_coach_projection_contains_only_student_privileges(agent_parent_state):
    projected = project_coach_state(agent_parent_state)
    serialized = repr(projected)

    assert projected["student_private_context"]["sentinel"] == "SIDE_B_SECRET"
    assert "SIDE_A_SECRET" not in serialized
    assert "EVALUATOR_SECRET" not in serialized
    assert "PERSONA" not in serialized


def test_simulation_learner_projection_contains_learner_safe_negotiation_context(agent_parent_state):
    projected = project_simulation_learner_state(agent_parent_state)
    serialized = repr(projected)

    assert projected["user_side"] == "side_b"
    assert projected["messages"] == [{"role": "user", "content": "LATEST-STUDENT"}]
    assert projected["phase"] == "bargaining"
    assert projected["active_side"] == "side_b"
    assert projected["current_offer"] == {"terms": {"sentinel": "OFFER"}}
    assert projected["offer_history"] == [{"terms": {"sentinel": "HISTORY"}}]
    assert projected["student_private_context"]["sentinel"] == "SIDE_B_SECRET"
    assert "SIDE_A_SECRET" not in serialized
    assert "EVALUATOR_SECRET" not in serialized
    assert "PERSONA" not in serialized
    assert "COACH_SECRET" not in serialized
    assert "LEARNER_VISIBLE" in serialized
    assert "TEACHER_ONLY" not in serialized
    assert "DEBUG_ONLY" not in serialized
    assert projected["event_log"] == []


def test_evaluator_projection_is_omniscient(agent_parent_state):
    projected = project_evaluator_state(agent_parent_state)
    serialized = repr(projected)

    for sentinel in (
        "PUBLIC",
        "SIDE_A_SECRET",
        "SIDE_B_SECRET",
        "COACH_SECRET",
        "EVALUATOR_SECRET",
    ):
        assert sentinel in serialized


def test_intent_projection_contains_only_latest_student_message(agent_parent_state_factory):
    state = agent_parent_state_factory(
        messages=[
            {"role": "assistant", "content": "OLD-COUNTERPART"},
            {"role": "user", "content": "LATEST-STUDENT"},
        ],
    )

    projected = project_intent_classifier_state(state)

    assert projected == {
        "messages": [{"role": "user", "content": "LATEST-STUDENT"}],
        "evidence_ledger": state["evidence_ledger"],
        "event_log": [],
    }


@pytest.mark.parametrize(
    "projector",
    [
        project_counterpart_state,
        project_coach_state,
        project_evaluator_state,
        project_intent_classifier_state,
        project_simulation_learner_state,
    ],
)
def test_projections_do_not_share_mutable_parent_values(projector, agent_parent_state_factory):
    state = agent_parent_state_factory()
    projected = projector(state)

    if "messages" in projected:
        projected["messages"].append({"role": "user", "content": "MUTATED"})

    assert all(
        message.get("content") != "MUTATED"
        for message in state["messages"]
    )

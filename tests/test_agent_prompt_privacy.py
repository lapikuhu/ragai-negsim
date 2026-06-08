from app.airag.chains.agents.coach.coach import make_coach_node
from app.airag.chains.agents.coach.coach_helpers import render_coach_prompt
from app.airag.chains.agents.counterpart.counterpart import make_counterpart_node
from app.airag.chains.agents.counterpart.counterpart_helpers import (
    fallback_counterpart_response,
    render_counterpart_prompt,
)
from app.airag.chains.agents.evaluator.evaluator import make_evaluator_node
from app.airag.chains.agents.evaluator.evaluator_helpers import (
    render_evaluator_prompt,
    render_final_evaluator_prompt,
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
        "messages": [{"role": "user", "content": "Student offer"}],
        "phase": "bargaining",
        "active_side": "side_b",
        "current_offer": {},
        "offer_history": [],
        "coach_advice": {"sentinel": "COACH_SECRET"},
        "evaluation": {"sentinel": "EVALUATOR_SECRET"},
        "final_evaluation": {"sentinel": "FINAL_SECRET"},
        "retrieval_result": {"summary": "SHARED_RETRIEVAL"},
        "event_log": [],
    }


def counterpart_payload():
    return {
        "side": "side_a",
        "message": "Counterpart reply",
        "action": "counter",
        "offer": {
            "side": "side_a",
            "price": None,
            "terms": {},
            "raw_text": "Counterpart reply",
        },
        "private_notes": {
            "strategy_used": "test",
            "reservation_value_check": "ok",
            "target_value_check": "ok",
            "risk": "low",
        },
    }


def test_counterpart_prompt_contains_only_allowed_context():
    state = {
        "user_side": "side_b",
        "counterpart_side": "side_a",
        "scenario_public_context": {"sentinel": "PUBLIC"},
        "own_private_context": {"sentinel": "COUNTERPART_SECRET"},
        "counterpart_persona": {"sentinel": "PERSONA"},
        "messages": [{"role": "user", "content": "Student offer"}],
        "current_offer": {},
        "offer_history": [],
    }

    rendered = render_counterpart_prompt(state)

    assert "PUBLIC" in rendered
    assert "COUNTERPART_SECRET" in rendered
    assert "PERSONA" in rendered
    assert "{side_a_profile}" not in rendered
    assert "{side_b_profile}" not in rendered
    assert "{evaluation}" not in rendered


def test_legacy_counterpart_template_appends_only_safe_context():
    rendered = render_counterpart_prompt(
        {
            "user_side": "side_b",
            "scenario_public_context": {"sentinel": "PUBLIC"},
            "own_private_context": {"sentinel": "COUNTERPART_SECRET"},
            "counterpart_persona": {"sentinel": "PERSONA"},
        },
        prompt_template=(
            "Legacy {side_a_profile} {side_b_profile} "
            "{scenario_context} {evaluation}"
        ),
    )

    assert "PUBLIC" in rendered
    assert "COUNTERPART_SECRET" in rendered
    assert "PERSONA" in rendered
    assert "SIDE_B_SECRET" not in rendered


def test_counterpart_fallback_uses_public_context_only():
    response = fallback_counterpart_response(
        {
            "user_side": "side_b",
            "scenario_public_context": {"name": "Late checkout"},
            "own_private_context": {"reservation": "COUNTERPART_SECRET"},
        },
        reason="structured output failed",
    )

    assert "Late checkout" in response["message"]
    assert "COUNTERPART_SECRET" not in response["message"]


def test_counterpart_wrapper_invokes_graph_with_projected_state():
    captured = {}

    class CapturingGraph:
        def invoke(self, state):
            captured.update(state)
            return {
                **state,
                "counterpart_response": counterpart_payload(),
                "event_log": ["counterpart:completed"],
            }

    node = make_counterpart_node(CapturingGraph())
    node(parent_state())

    serialized = repr(captured)
    assert "SIDE_A_SECRET" in serialized
    assert "SIDE_B_SECRET" not in serialized
    assert "EVALUATOR_SECRET" not in serialized


def test_coach_prompt_contains_student_context_without_counterpart_or_evaluation():
    rendered = render_coach_prompt(
        {
            "user_side": "side_b",
            "scenario_public_context": {"sentinel": "PUBLIC"},
            "student_private_context": {"sentinel": "STUDENT_SECRET"},
            "messages": [],
            "current_offer": {},
            "offer_history": [],
        }
    )

    assert "PUBLIC" in rendered
    assert "STUDENT_SECRET" in rendered
    assert "COUNTERPART_SECRET" not in rendered
    assert "EVALUATOR_SECRET" not in rendered


def test_legacy_coach_template_appends_only_coach_safe_context():
    rendered = render_coach_prompt(
        {
            "user_side": "side_b",
            "scenario_public_context": {"sentinel": "PUBLIC"},
            "student_private_context": {"sentinel": "STUDENT_SECRET"},
        },
        prompt_template=(
            "Legacy {side_a_profile} {side_b_profile} "
            "{scenario_context} {evaluation}"
        ),
    )

    assert "PUBLIC" in rendered
    assert "STUDENT_SECRET" in rendered


def test_coach_wrapper_invokes_graph_with_projected_state():
    captured = {}

    class CapturingGraph:
        def invoke(self, state):
            captured.update(state)
            return {
                **state,
                "coach_advice": {"summary": "Advice"},
                "event_log": ["coach:completed"],
            }

    node = make_coach_node(CapturingGraph())
    node(parent_state())

    serialized = repr(captured)
    assert "SIDE_B_SECRET" in serialized
    assert "SIDE_A_SECRET" not in serialized
    assert "EVALUATOR_SECRET" not in serialized


def test_evaluator_prompt_contains_all_structured_contexts():
    state = {
        "user_side": "side_b",
        "scenario_public_context": {"sentinel": "PUBLIC"},
        "side_a_private_context": {"sentinel": "SIDE_A_SECRET"},
        "side_b_private_context": {"sentinel": "SIDE_B_SECRET"},
        "messages": [],
        "offer_history": [],
        "coach_advice": {"sentinel": "COACH"},
        "evaluation": {"sentinel": "PRIOR_EVALUATION"},
    }

    rolling = render_evaluator_prompt(state)
    final = render_final_evaluator_prompt(state)

    for sentinel in ("PUBLIC", "SIDE_A_SECRET", "SIDE_B_SECRET"):
        assert sentinel in rolling
        assert sentinel in final


def test_evaluator_wrapper_invokes_graph_with_full_context():
    captured = {}

    class CapturingGraph:
        def invoke(self, state):
            captured.update(state)
            return {
                **state,
                "evaluation": {"score": 0.5},
                "event_log": ["evaluator:completed"],
            }

    node = make_evaluator_node(CapturingGraph())
    node(parent_state())

    serialized = repr(captured)
    assert "SIDE_A_SECRET" in serialized
    assert "SIDE_B_SECRET" in serialized
    assert "EVALUATOR_SECRET" in serialized

from app.airag.chains.agents.user_proxy_negotiator.user_proxy import make_user_proxy_node
from app.airag.chains.agents.user_proxy_negotiator.user_proxy_helpers import (
    fallback_user_proxy_response,
    render_user_proxy_prompt,
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
        "counterpart_persona": {"sentinel": "COUNTERPART_PERSONA"},
        "user_proxy_persona": {"sentinel": "PROXY_PERSONA"},
        "messages": [{"role": "assistant", "content": "Counterpart reply"}],
        "phase": "bargaining",
        "active_side": "side_b",
        "current_offer": {"price": 95},
        "offer_history": [],
        "coach_advice": {"suggested_response": "Ask for 100 and hold firm."},
        "evaluation": {"sentinel": "EVALUATOR_SECRET"},
        "event_log": [],
    }


def test_user_proxy_prompt_contains_only_allowed_context():
    state = {
        "user_side": "side_b",
        "scenario_public_context": {"sentinel": "PUBLIC"},
        "student_private_context": {"sentinel": "STUDENT_SECRET"},
        "proxy_persona": {"sentinel": "PROXY_PERSONA"},
        "coach_advice": {"suggested_response": "Hold firm"},
        "messages": [{"role": "assistant", "content": "Counterpart reply"}],
        "current_offer": {},
        "offer_history": [],
    }

    rendered = render_user_proxy_prompt(state)

    assert "PUBLIC" in rendered
    assert "STUDENT_SECRET" in rendered
    assert "PROXY_PERSONA" in rendered
    assert "Hold firm" in rendered
    assert "{evaluation}" not in rendered


def test_user_proxy_fallback_does_not_echo_private_values():
    response = fallback_user_proxy_response(
        {
            "user_side": "side_b",
            "scenario_public_context": {"name": "Late checkout"},
            "student_private_context": {"reservation": "STUDENT_SECRET"},
            "coach_advice": {"suggested_response": "Ask for a trade."},
        },
        reason="structured output failed",
    )

    assert "Late checkout" in response["message"]
    assert "STUDENT_SECRET" not in response["message"]


def test_user_proxy_wrapper_invokes_graph_with_projected_state():
    captured = {}

    class CapturingGraph:
        def invoke(self, state):
            captured.update(state)
            return {
                **state,
                "proxy_response": {"message": "I can do 100 if we sign today."},
                "event_log": ["user_proxy:completed"],
            }

    node = make_user_proxy_node(CapturingGraph())
    node(parent_state())

    serialized = repr(captured)
    assert "SIDE_B_SECRET" in serialized
    assert "SIDE_A_SECRET" not in serialized
    assert "EVALUATOR_SECRET" not in serialized

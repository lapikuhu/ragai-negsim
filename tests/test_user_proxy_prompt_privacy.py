from app.airag.chains.agents.user_proxy_negotiator.user_proxy import make_user_proxy_node
from app.airag.chains.agents.user_proxy_negotiator.user_proxy_helpers import (
    fallback_user_proxy_response,
    render_user_proxy_prompt,
)


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


def test_user_proxy_wrapper_invokes_graph_with_projected_state(
    agent_parent_state_factory,
    capturing_graph_factory,
):
    graph, captured = capturing_graph_factory(
        lambda state: {
            **state,
            "proxy_response": {"message": "I can do 100 if we sign today."},
            "event_log": ["user_proxy:completed"],
        }
    )
    node = make_user_proxy_node(graph)
    node(
        agent_parent_state_factory(
            counterpart_persona={"sentinel": "COUNTERPART_PERSONA"},
            user_proxy_persona={"sentinel": "PROXY_PERSONA"},
            messages=[{"role": "assistant", "content": "Counterpart reply"}],
            current_offer={"price": 95},
            offer_history=[],
            coach_advice={"suggested_response": "Ask for 100 and hold firm."},
            evaluation={"sentinel": "EVALUATOR_SECRET"},
            event_log=[],
        )
    )

    serialized = repr(captured)
    assert "SIDE_B_SECRET" in serialized
    assert "SIDE_A_SECRET" not in serialized
    assert "EVALUATOR_SECRET" not in serialized

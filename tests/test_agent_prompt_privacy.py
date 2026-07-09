from app.airag.chains.agents.coach.coach import make_coach_node
from app.airag.chains.agents.helpers import format_messages
from app.airag.chains.agents.coach.coach_helpers import render_coach_prompt
from app.airag.chains.agents.counterpart.counterpart import make_counterpart_node
from app.airag.chains.agents.counterpart.counterpart_helpers import (
    fallback_counterpart_response,
    render_counterpart_prompt,
)
from langgraph.graph.message import add_messages
from app.airag.chains.agents.evaluator.evaluator import make_evaluator_node
from app.airag.chains.agents.evaluator.evaluator_helpers import (
    render_evaluator_prompt,
    render_final_evaluator_prompt,
    summarize_proxy_authorship,
)


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


def test_counterpart_wrapper_invokes_graph_with_projected_state(
    agent_parent_state_factory,
    agent_counterpart_payload,
    capturing_graph_factory,
):
    graph, captured = capturing_graph_factory(
        lambda state: {
            **state,
            "counterpart_response": agent_counterpart_payload,
            "event_log": ["counterpart:completed"],
        }
    )

    node = make_counterpart_node(graph)
    node(
        agent_parent_state_factory(
            messages=[{"role": "user", "content": "Student offer"}],
            current_offer={},
            offer_history=[],
            event_log=[],
        )
    )

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


def test_coach_wrapper_invokes_graph_with_projected_state(
    agent_parent_state_factory,
    capturing_graph_factory,
):
    graph, captured = capturing_graph_factory(
        lambda state: {
            **state,
            "coach_advice": {"summary": "Advice"},
            "event_log": ["coach:completed"],
        }
    )

    node = make_coach_node(graph)
    node(
        agent_parent_state_factory(
            messages=[{"role": "user", "content": "Student offer"}],
            current_offer={},
            offer_history=[],
            event_log=[],
        )
    )

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
        "messages": [
            {
                "role": "user",
                "content": "Student offer",
                "metadata": {"user_reply_origin": "user"},
            },
            {
                "role": "user",
                "content": "Proxy offer",
                "metadata": {"user_reply_origin": "auto_user_proxy"},
            },
        ],
        "offer_history": [],
        "coach_advice": {"sentinel": "COACH"},
        "evaluation": {"sentinel": "PRIOR_EVALUATION"},
    }

    rolling = render_evaluator_prompt(state)
    final = render_final_evaluator_prompt(state)

    for sentinel in ("PUBLIC", "SIDE_A_SECRET", "SIDE_B_SECRET"):
        assert sentinel in rolling
        assert sentinel in final

    assert "auto_user_proxy" in rolling
    assert "auto_user_proxy" in final


def test_format_messages_preserves_proxy_metadata_after_langgraph_coercion():
    messages = add_messages(
        [],
        [
            {
                "role": "user",
                "content": "Proxy offer",
                "side": "side_b",
                "metadata": {"user_reply_origin": "auto_user_proxy"},
            }
        ],
    )

    rendered = format_messages(messages)

    assert "auto_user_proxy" in rendered
    assert "user_reply_origin" in rendered
    assert "side_b" in rendered


def test_summarize_proxy_authorship_reads_deeply_nested_metadata():
    messages = [
        {
            "role": "human",
            "content": "Proxy offer",
            "metadata": {
                "metadata": {
                    "metadata": {
                        "timestamp": "2026-06-16T10:14:39.939181+00:00",
                        "side": "side_a",
                        "metadata": {"user_reply_origin": "auto_user_proxy"},
                    }
                }
            },
        },
        {
            "role": "ai",
            "content": "Counterpart reply",
            "metadata": {"metadata": {"side": "side_b"}},
        },
        {
            "role": "human",
            "content": "Proxy accept",
            "metadata": {
                "timestamp": "2026-06-16T10:20:18.356642+00:00",
                "side": "side_a",
                "metadata": {"user_reply_origin": "auto_user_proxy"},
            },
        },
    ]

    summary = summarize_proxy_authorship(messages)

    assert summary["student_authored_turns"] == 0
    assert summary["proxy_authored_turns"] == 2
    assert summary["proxy_extent"] == "extensive"


def test_evaluator_prompts_define_proxy_authorship_and_student_attribution_rules():
    state = {
        "user_side": "side_b",
        "messages": [
            {
                "role": "user",
                "content": "Legacy student turn",
            },
            {
                "role": "user",
                "content": "Proxy turn",
                "metadata": {"user_reply_origin": "auto_user_proxy"},
            },
        ],
    }

    rolling = render_evaluator_prompt(state)
    final = render_final_evaluator_prompt(state)

    for rendered in (rolling, final):
        assert 'metadata.user_reply_origin == "auto_user_proxy"' in rendered
        assert "Missing provenance means the message should be treated as student-authored." in rendered
        assert "Do not count proxy-authored tactics as evidence of the student's own negotiation skill." in rendered

    assert 'If every student-side turn was proxy-authored, set "overall_score" to 0.0.' in final


def test_custom_rolling_evaluator_prompt_appends_proxy_guidance_and_summary():
    messages = add_messages(
        [],
        [
            {
                "role": "user",
                "content": "Student turn",
                "side": "side_b",
                "metadata": {"user_reply_origin": "user"},
            },
            {
                "role": "user",
                "content": "Proxy turn",
                "side": "side_b",
                "metadata": {"user_reply_origin": "auto_user_proxy"},
            },
        ],
    )
    rendered = render_evaluator_prompt(
        {
            "user_side": "side_b",
            "messages": messages,
        },
        prompt_template="Evaluate this turn carefully.",
    )

    assert "Evaluate this turn carefully." in rendered
    assert "Proxy authorship rules:" in rendered
    assert "student_authored_turns" in rendered
    assert "proxy_authored_turns" in rendered
    assert "auto_user_proxy" in rendered


def test_evaluator_wrapper_invokes_graph_with_full_context(
    agent_parent_state_factory,
    capturing_graph_factory,
):
    graph, captured = capturing_graph_factory(
        lambda state: {
            **state,
            "evaluation": {"score": 0.5},
            "event_log": ["evaluator:completed"],
        }
    )

    node = make_evaluator_node(graph)
    node(
        agent_parent_state_factory(
            messages=[{"role": "user", "content": "Student offer"}],
            current_offer={},
            offer_history=[],
            event_log=[],
        )
    )

    serialized = repr(captured)
    assert "SIDE_A_SECRET" in serialized
    assert "SIDE_B_SECRET" in serialized
    assert "EVALUATOR_SECRET" in serialized

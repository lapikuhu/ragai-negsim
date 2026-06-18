from app.airag.chains.agents.coach.coach_helpers import render_coach_prompt
from app.airag.chains.agents.counterpart.counterpart_helpers import (
    render_counterpart_prompt,
)
from app.airag.chains.agents.evaluator.evaluator_helpers import (
    render_evaluator_prompt,
    render_final_evaluator_prompt,
)


def test_coach_prompt_appends_only_public_and_student_private_context():
    rendered = render_coach_prompt(
        {
            "user_side": "side_b",
            "scenario_public_context": {"name": "Hotel late checkout"},
            "student_private_context": {"reservation": "STUDENT-SECRET"},
        },
        prompt_template="Coach the student.",
    )

    assert '"name": "Hotel late checkout"' in rendered
    assert '"reservation": "STUDENT-SECRET"' in rendered
    assert "You are a negotiation coach." in rendered
    assert "CUSTOM PROMPT EXTENSION" in rendered
    assert "Coach the student." in rendered


def test_counterpart_prompt_adds_custom_extension_without_replacing_base():
    rendered = render_counterpart_prompt(
        {
            "user_side": "side_b",
            "scenario_public_context": {"name": "Hotel late checkout"},
            "own_private_context": {"reservation": "COUNTERPART-SECRET"},
            "counterpart_persona": {"name": "Firm manager"},
        },
        prompt_template="Reply as the counterpart in a terse style.",
    )

    assert "You are the negotiating counterpart in a simulated negotiation." in rendered
    assert "CUSTOM PROMPT EXTENSION" in rendered
    assert "Reply as the counterpart in a terse style." in rendered


def test_rolling_evaluator_prompt_appends_structured_contexts():
    rendered = render_evaluator_prompt(
        {
            "user_side": "side_b",
            "scenario_public_context": {"name": "Hotel late checkout"},
            "side_a_private_context": {"reservation": "SIDE-A-SECRET"},
            "side_b_private_context": {"reservation": "SIDE-B-SECRET"},
        },
        prompt_template="Evaluate the turn.",
    )

    assert '"name": "Hotel late checkout"' in rendered
    assert '"reservation": "SIDE-A-SECRET"' in rendered
    assert '"reservation": "SIDE-B-SECRET"' in rendered
    assert "You are a negotiation evaluator." in rendered
    assert "CUSTOM PROMPT EXTENSION" in rendered
    assert "Evaluate the turn." in rendered


def test_final_evaluator_prompt_includes_structured_contexts():
    rendered = render_final_evaluator_prompt(
        {
            "user_side": "side_b",
            "scenario_public_context": {
                "name": "Hotel late checkout",
                "description": "The guest wants a free late checkout.",
            },
            "side_a_private_context": {"reservation": "SIDE-A-SECRET"},
            "side_b_private_context": {"reservation": "SIDE-B-SECRET"},
        }
    )

    assert "Hotel late checkout" in rendered
    assert "The guest wants a free late checkout." in rendered
    assert "SIDE-A-SECRET" in rendered
    assert "SIDE-B-SECRET" in rendered
    assert '"overall_score": 0.0' in rendered
    assert '"goal_achievement": "..."' in rendered


def test_custom_final_evaluator_prompt_adds_extension_to_default_template():
    rendered = render_final_evaluator_prompt(
        {
            "user_side": "side_b",
            "messages": [{"role": "user", "content": "Student turn"}],
        },
        prompt_template="Custom final review\n{messages}",
    )

    assert "Custom final review" in rendered
    assert "Student turn" in rendered
    assert "You are the final evaluator for a negotiation simulation." in rendered
    assert '"overall_score": 0.0' in rendered
    assert "CUSTOM PROMPT EXTENSION" in rendered


def test_custom_rolling_evaluator_prompt_appends_proxy_policy_and_summary():
    rendered = render_evaluator_prompt(
        {
            "user_side": "side_b",
            "messages": [
                {
                    "role": "user",
                    "content": "Proxy turn",
                    "metadata": {"user_reply_origin": "auto_user_proxy"},
                }
            ],
        },
        prompt_template="Evaluate the turn.",
    )

    assert "Evaluate the turn." in rendered
    assert "You are a negotiation evaluator." in rendered
    assert "Proxy authorship rules:" in rendered
    assert "proxy_authored_turns" in rendered

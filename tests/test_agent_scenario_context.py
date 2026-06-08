from app.airag.chains.agents.coach.coach_helpers import render_coach_prompt
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

    assert "PUBLIC CONTEXT" in rendered
    assert '"name": "Hotel late checkout"' in rendered
    assert '"reservation": "STUDENT-SECRET"' in rendered


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

    assert "PUBLIC CONTEXT" in rendered
    assert '"name": "Hotel late checkout"' in rendered
    assert '"reservation": "SIDE-A-SECRET"' in rendered
    assert '"reservation": "SIDE-B-SECRET"' in rendered


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

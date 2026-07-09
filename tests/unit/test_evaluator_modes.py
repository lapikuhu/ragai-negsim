import pytest
from pydantic import ValidationError

from app.airag.chains.agents.evaluator.evaluator_helpers import (
    compact_evaluation_from_response,
    final_evaluation_from_response,
)
from app.airag.chains.agents.evaluator.evaluator_model import (
    EvaluatorResponseModel,
    FinalEvaluatorResponseModel,
)


def rolling_payload(next_best_action):
    return {
        "score": 0.4,
        "phase_assessment": "Opening position.",
        "side_a_assessment": {
            "position": "unknown",
            "target_value_check": "unknown",
            "reservation_value_check": "unknown",
            "constraint_check": "unknown",
            "risk_level": "medium",
        },
        "side_b_assessment": {
            "position": "unknown",
            "target_value_check": "unknown",
            "reservation_value_check": "unknown",
            "constraint_check": "unknown",
            "risk_level": "medium",
        },
        "zopa_assessment": {
            "zopa_exists": None,
            "reasoning": "Insufficient data.",
            "confidence": "low",
        },
        "detected_risks": ["insufficient data"],
        "deal_quality": {
            "for_side_a": "unknown",
            "for_side_b": "unknown",
            "overall": "unknown",
        },
        "proxy_usage_assessment": {
            "student_authored_turns": 1,
            "proxy_authored_turns": 0,
            "proxy_extent": "none",
            "impact_on_student_score": "No proxy use detected.",
        },
        "next_best_action": next_best_action,
        "reasoning": "Continue using available information.",
        "missing_information": ["reservation values"],
        "confidence": "low",
    }


def test_rolling_evaluator_rejects_graph_actions():
    with pytest.raises(ValidationError):
        EvaluatorResponseModel.model_validate(rolling_payload("ask_user"))


@pytest.mark.parametrize(
    "strategy",
    ["continue", "counter", "accept", "walk_away"],
)
def test_rolling_evaluator_accepts_student_strategy(strategy):
    assert (
        EvaluatorResponseModel.model_validate(
            rolling_payload(strategy)
        ).next_best_action
        == strategy
    )


def test_final_evaluator_compacts_overall_student_assessment():
    response = FinalEvaluatorResponseModel(
        overall_score=0.75,
        goal_achievement="Protected the main constraint.",
        strengths=["Asked direct questions."],
        mistakes=["Conceded early."],
        concession_quality="Mixed.",
        communication_quality="Clear.",
        outcome_quality="Acceptable.",
        proxy_usage_assessment={
            "student_authored_turns": 4,
            "proxy_authored_turns": 1,
            "proxy_extent": "limited",
            "impact_on_student_score": "One proxy turn slightly reduces confidence in the score.",
        },
        lessons=["Trade concessions instead of giving them away."],
        reasoning="The full transcript shows steady improvement.",
        confidence="high",
        missing_information=[],
    ).model_dump()

    compact = final_evaluation_from_response(
        {"user_side": "side_b"},
        response,
    )

    assert compact["evaluated_side"] == "side_b"
    assert compact["overall_score"] == 0.75


def test_rolling_evaluator_requires_proxy_usage_assessment():
    payload = rolling_payload("continue")
    payload.pop("proxy_usage_assessment")

    with pytest.raises(ValidationError):
        EvaluatorResponseModel.model_validate(payload)


def test_final_evaluator_requires_proxy_usage_assessment():
    payload = {
        "overall_score": 0.75,
        "goal_achievement": "Protected the main constraint.",
        "strengths": ["Asked direct questions."],
        "mistakes": ["Conceded early."],
        "concession_quality": "Mixed.",
        "communication_quality": "Clear.",
        "outcome_quality": "Acceptable.",
        "lessons": ["Trade concessions instead of giving them away."],
        "reasoning": "The full transcript shows steady improvement.",
        "confidence": "high",
        "missing_information": [],
    }

    with pytest.raises(ValidationError):
        FinalEvaluatorResponseModel.model_validate(payload)


def test_final_evaluation_overrides_model_proxy_count_and_clamps_all_proxy_score(
    agent_parent_state_factory,
):
    response = FinalEvaluatorResponseModel(
        overall_score=0.85,
        goal_achievement="The deal was favorable.",
        strengths=["Persistent."],
        mistakes=[],
        concession_quality="Good.",
        communication_quality="Clear.",
        outcome_quality="Good.",
        proxy_usage_assessment={
            "student_authored_turns": 8,
            "proxy_authored_turns": 1,
            "proxy_extent": "limited",
            "impact_on_student_score": "The model counted this incorrectly.",
        },
        lessons=[],
        reasoning="The model missed the nested proxy metadata.",
        confidence="high",
        missing_information=[],
    ).model_dump()

    state = agent_parent_state_factory(
        user_side="side_a",
        messages=[
            {
                "role": "human",
                "content": "Proxy offer",
                "metadata": {
                    "metadata": {
                        "side": "side_a",
                        "metadata": {"user_reply_origin": "auto_user_proxy"},
                    }
                },
            },
            {
                "role": "human",
                "content": "Proxy accept",
                "metadata": {
                    "side": "side_a",
                    "metadata": {"user_reply_origin": "auto_user_proxy"},
                },
            },
        ],
    )

    compact = final_evaluation_from_response(state, response)

    assert compact["overall_score"] == 0.0
    assert compact["proxy_usage_assessment"]["student_authored_turns"] == 0
    assert compact["proxy_usage_assessment"]["proxy_authored_turns"] == 2
    assert compact["proxy_usage_assessment"]["proxy_extent"] == "extensive"


def test_rolling_evaluation_overrides_model_proxy_count_from_state(
    agent_parent_state_factory,
):
    response = rolling_payload("continue")
    response["proxy_usage_assessment"] = {
        "student_authored_turns": 2,
        "proxy_authored_turns": 0,
        "proxy_extent": "none",
        "impact_on_student_score": "The model counted this incorrectly.",
    }

    state = agent_parent_state_factory(
        user_side="side_a",
        messages=[
            {
                "role": "human",
                "content": "Proxy offer",
                "metadata": {"metadata": {"user_reply_origin": "auto_user_proxy"}},
            }
        ],
    )

    compact = compact_evaluation_from_response(state, response)

    assert compact["proxy_usage_assessment"]["student_authored_turns"] == 0
    assert compact["proxy_usage_assessment"]["proxy_authored_turns"] == 1
    assert compact["proxy_usage_assessment"]["proxy_extent"] == "extensive"

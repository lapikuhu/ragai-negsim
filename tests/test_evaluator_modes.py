import pytest
from pydantic import ValidationError

from app.airag.chains.agents.evaluator.evaluator_helpers import (
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

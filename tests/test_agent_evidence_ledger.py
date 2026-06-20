from app.airag.chains.agents.coach.coach_nodes import node_finalize_coach
from app.airag.chains.agents.evaluator.evaluator_nodes import node_finalize_evaluator
from app.airag.chains.agents.intent_classifier.intent_classifier_nodes import (
    node_finalize_intent,
)


def test_intent_finalize_preserves_evidence_ledger():
    result = node_finalize_intent(
        {
            "intent_classification": {
                "intent": "continue",
                "confidence": "high",
                "reasoning": "Not ending.",
            },
            "evidence_ledger": {"intent_classifier": {"pipeline": {"steps": []}}},
        }
    )

    assert "evidence_ledger" in result
    assert "intent_classifier" in result["evidence_ledger"]


def test_coach_finalize_adds_agent_output_summary():
    result = node_finalize_coach(
        {
            "coach_advice": {
                "summary": "Hold price.",
                "confidence": "medium",
            },
            "evidence_ledger": {"coach": {"pipeline": {"steps": []}}},
        }
    )

    assert result["evidence_ledger"]["coach"]["output_summary"]["kind"] == "coach_advice"
    assert result["evidence_ledger"]["coach"]["output_summary"]["confidence"] == "medium"


def test_evaluator_finalize_adds_agent_output_summary():
    result = node_finalize_evaluator(
        {
            "evaluation_mode": "final",
            "evaluator_response": {
                "overall_score": 8,
                "confidence": "high",
                "reasoning": "Strong outcome.",
            },
            "evidence_ledger": {"evaluator": {"pipeline": {"steps": []}}},
            "user_side": "side_a",
        }
    )

    assert result["evidence_ledger"]["evaluator"]["output_summary"]["kind"] == "final_evaluation"

from types import SimpleNamespace

from langchain_core.documents import Document

from app.airag.chains.agents.coach.coach_helpers import build_coach_trusted_context
from app.airag.chains.agents.coach.coach_nodes import make_call_crag_node as make_call_coach_crag_node
from app.airag.chains.agents.evaluator.evaluator_helpers import (
    build_evaluator_trusted_context,
)
from app.airag.chains.agents.evaluator.evaluator_nodes import (
    make_call_crag_node as make_call_evaluator_crag_node,
)
from app.airag.chains.crag import crag_nodes
from app.airag.prompts.sys_prompts import DOC_GRADE_PROMPT


def test_document_grader_prompt_accepts_transferable_negotiation_concepts():
    rendered = DOC_GRADE_PROMPT.invoke(
        {
            "question": "How should I negotiate a hotel late checkout fee?",
            "context": (
                "A ZOPA exists when the parties' reservation values overlap. "
                "Use conditional concessions and avoid conceding without receiving value."
            ),
        }
    ).to_string()

    assert "transferable" in rendered.lower()
    assert "scenario-specific" in rendered.lower()
    assert "single materially useful concept" in rendered.lower()
    assert "zopa" in rendered.lower()
    assert "unrelated" in rendered.lower()


def test_node_grade_accepts_general_theory_for_scenario_query(monkeypatch):
    captured = {}

    class FakeDocumentGrader:
        def invoke(self, payload):
            captured.update(payload)
            return SimpleNamespace(
                relevance="relevant",
                reasoning=(
                    "The context explains ZOPA and reservation values, which "
                    "apply to evaluating the late-checkout fee negotiation."
                ),
            )

    result = crag_nodes.make_node_grade(FakeDocumentGrader())(
        {
            "question": "How should I negotiate a hotel late checkout fee?",
            "documents": [
                Document(
                    page_content=(
                        "A ZOPA exists when reservation values overlap. "
                        "Conditional concessions can protect value."
                    ),
                    metadata={"source": "negotiation-guide"},
                )
            ],
        }
    )

    assert result["grade"] == "relevant"
    assert result["evidence_ledger"]["quality_checks"][0]["name"] == "document_relevance"
    assert "hotel late checkout" in captured["question"]
    assert "ZOPA exists" in captured["context"]


def test_node_grade_rejects_unrelated_documents(monkeypatch):
    class FakeDocumentGrader:
        def invoke(self, payload):
            return SimpleNamespace(
                relevance="not_relevant",
                reasoning="The context concerns database indexing, not negotiation.",
            )

    result = crag_nodes.make_node_grade(FakeDocumentGrader())(
        {
            "question": "How should I negotiate a hotel late checkout fee?",
            "documents": [
                Document(
                    page_content="Database indexes speed up query lookup.",
                    metadata={"source": "database-guide"},
                )
            ],
        }
    )

    assert result["grade"] == "not_relevant"
    assert result["evidence_ledger"]["quality_checks"][0]["verdict"] == "not_relevant"


def test_node_grade_rejects_empty_documents_without_invoking_grader(monkeypatch):
    class FailingDocumentGrader:
        def invoke(self, payload):
            raise AssertionError("document grader should not be invoked")

    result = crag_nodes.make_node_grade(FailingDocumentGrader())(
        {
            "question": "How should I negotiate a hotel late checkout fee?",
            "documents": [],
        }
    )

    assert result["grade"] == "not_relevant"
    assert result["evidence_ledger"]["quality_checks"][0]["reasoning"] == "No documents retrieved."


def test_node_generate_passes_retrieval_and_trusted_context(monkeypatch):
    captured = {}

    class FakeGenerationChain:
        def invoke(self, payload):
            captured.update(payload)
            return "Grounded answer"

    result = crag_nodes.make_node_generate(FakeGenerationChain())(
        {
            "question": "What should I do?",
            "documents": [],
            "trusted_context": "TRUSTED\nCurrent offer: EUR 40",
        }
    )

    assert result["answer"] == "Grounded answer"
    assert captured["question"] == "What should I do?"
    assert captured["context"] == ""
    assert captured["trusted_context"] == "TRUSTED\nCurrent offer: EUR 40"
    assert result["evidence_ledger"]["pipeline"]["steps"][0]["name"] == "generate"


def test_node_quality_check_passes_both_evidence_sources(monkeypatch):
    captured = {}

    class FakeHallucinationGrader:
        def invoke(self, payload):
            captured.update(payload)
            return SimpleNamespace(
                grounded="yes",
                reasoning="Supported by retrieved theory and trusted simulation values.",
            )

    class FakeAnswerGrader:
        def invoke(self, payload):
            return SimpleNamespace(addresses="yes")

    result = crag_nodes.make_node_quality_check(
        FakeHallucinationGrader(),
        FakeAnswerGrader(),
    )(
        {
            "question": "Is this offer inside the zone of possible agreement?",
            "context": "Context: ZOPA exists when reservation values overlap.",
            "trusted_context": "Trusted: Side B reservation value is EUR 25.\nTrusted: Current offer is EUR 40.",
            "answer": "The current offer of EUR 40 is above Side B's EUR 25 reservation value, so it may be inside the ZOPA depending on Side A's floor.",
        }
    )

    assert captured["context"] == "Context: ZOPA exists when reservation values overlap."
    assert "EUR 25" in captured["trusted_context"]
    assert result["hallucination_grade"] == "yes"
    assert result["answer_grade"] == "yes"
    assert "grounded=yes" in result["quality_reasoning"]
    assert [check["name"] for check in result["evidence_ledger"]["quality_checks"]] == [
        "groundedness",
        "answer_relevance",
    ]


def test_node_quality_check_fails_when_both_evidence_sources_missing():
    result = crag_nodes.node_quality_check(
        {
            "question": "Question",
            "answer": "Answer",
            "context": "",
            "trusted_context": "",
        }
    )

    assert result["hallucination_grade"] == "no"
    assert result["answer_grade"] == "no"
    assert result["quality_reasoning"] == "Missing context or answer."
    assert result["evidence_ledger"]["pipeline"]["steps"][0]["status"] == "failed"


def test_build_coach_trusted_context_contains_only_coach_safe_fields():
    trusted_context = build_coach_trusted_context(
        {
            "user_side": "side_b",
            "phase": "bargaining",
            "scenario_public_context": {"name": "Late checkout"},
            "student_private_context": {"reservation_value": 25.0},
            "current_offer": {"price": 40.0, "raw_text": "I can do EUR 40."},
            "offer_history": [{"price": 45.0}],
        }
    )

    assert "Late checkout" in trusted_context
    assert '"reservation_value": 25.0' in trusted_context
    assert '"price": 40.0' in trusted_context
    assert "SIDE_A_SECRET" not in trusted_context


def test_build_evaluator_trusted_context_contains_all_authorized_fields():
    trusted_context = build_evaluator_trusted_context(
        {
            "user_side": "side_b",
            "phase": "closing",
            "evaluation_mode": "rolling",
            "scenario_public_context": {"name": "Late checkout"},
            "side_a_private_context": {"reservation_value": 18.0},
            "side_b_private_context": {"reservation_value": 25.0},
            "side_a": {"name": "Hotel", "target_value": 50.0},
            "side_b": {"name": "Guest", "target_value": 20.0},
            "current_offer": {"price": 40.0},
            "offer_history": [{"price": 45.0}],
        }
    )

    assert "Late checkout" in trusted_context
    assert '"reservation_value": 18.0' in trusted_context
    assert '"reservation_value": 25.0' in trusted_context
    assert '"target_value": 50.0' in trusted_context


def test_coach_crag_call_passes_coach_safe_trusted_context():
    captured = {}

    class CapturingCrag:
        def invoke(self, payload):
            captured.update(payload)
            return {"answer": "retrieved answer", "context": "retrieved context"}

    node = make_call_coach_crag_node(CapturingCrag())
    node(
        {
            "coach_query": "query",
            "user_side": "side_b",
            "phase": "bargaining",
            "scenario_public_context": {"name": "Late checkout"},
            "student_private_context": {"reservation_value": 25.0},
            "current_offer": {"price": 40.0},
            "offer_history": [{"price": 45.0}],
        }
    )

    assert captured["question"] == "query"
    assert "Late checkout" in captured["trusted_context"]
    assert '"reservation_value": 25.0' in captured["trusted_context"]
    assert "SIDE_A_SECRET" not in captured["trusted_context"]


def test_evaluator_crag_call_passes_full_authorized_trusted_context():
    captured = {}

    class CapturingCrag:
        def invoke(self, payload):
            captured.update(payload)
            return {"answer": "retrieved answer", "context": "retrieved context"}

    node = make_call_evaluator_crag_node(CapturingCrag())
    node(
        {
            "evaluator_query": "query",
            "user_side": "side_b",
            "phase": "closing",
            "evaluation_mode": "final",
            "scenario_public_context": {"name": "Late checkout"},
            "side_a_private_context": {"reservation_value": 18.0},
            "side_b_private_context": {"reservation_value": 25.0},
            "side_a": {"name": "Hotel"},
            "side_b": {"name": "Guest"},
            "current_offer": {"price": 40.0},
            "offer_history": [{"price": 45.0}],
            "retrieval_result": {"summary": "Shared retrieval summary"},
        }
    )

    assert captured["question"] == "query"
    assert "Late checkout" in captured["trusted_context"]
    assert '"reservation_value": 18.0' in captured["trusted_context"]
    assert '"reservation_value": 25.0' in captured["trusted_context"]

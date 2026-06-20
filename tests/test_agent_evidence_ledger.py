from app.airag.chains.agents.coach.coach_nodes import node_finalize_coach
from app.airag.chains.agents.coach.coach_model import CoachGraphState
from app.airag.chains.agents.context_projections import (
    project_coach_state,
    project_counterpart_state,
    project_evaluator_state,
    project_intent_classifier_state,
)
from app.airag.chains.agents.coach.coach import make_coach_node
from app.airag.chains.agents.counterpart.counterpart import make_counterpart_node
from app.airag.chains.agents.counterpart.counterpart_model import CounterpartGraphState
from app.airag.chains.agents.evaluator.evaluator import make_evaluator_node
from app.airag.chains.agents.evaluator.evaluator_model import EvaluatorGraphState
from app.airag.chains.agents.evaluator.evaluator_nodes import node_finalize_evaluator
from app.airag.chains.agents.intent_classifier.intent_classifier import (
    make_intent_classifier_node,
)
from app.airag.chains.agents.intent_classifier.intent_classifier_model import (
    IntentClassifierGraphState,
)
from app.airag.chains.agents.intent_classifier.intent_classifier_nodes import (
    node_finalize_intent,
)
from app.airag.chains.agents.user_proxy_negotiator.user_proxy_model import (
    UserProxyGraphState,
)
from langgraph.graph import END, START, StateGraph


class FakeGraph:
    def __init__(self, result):
        self.result = result
        self.payload = None

    def invoke(self, payload, config=None):
        self.payload = payload
        return self.result


def _invoke_schema_probe(state_schema):
    def node(state):
        return {"evidence_ledger": {"probe": {"pipeline": {"steps": []}}}}

    graph = StateGraph(state_schema)
    graph.add_node("probe", node)
    graph.add_edge(START, "probe")
    graph.add_edge("probe", END)
    return graph.compile().invoke({})


def test_agent_graph_state_schemas_preserve_evidence_ledger_channel():
    for state_schema in [
        IntentClassifierGraphState,
        CounterpartGraphState,
        CoachGraphState,
        EvaluatorGraphState,
        UserProxyGraphState,
    ]:
        result = _invoke_schema_probe(state_schema)

        assert result["evidence_ledger"]["probe"]["pipeline"]["steps"] == []


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


def test_parent_agent_wrappers_propagate_evidence_ledgers():
    cases = [
        (
            make_intent_classifier_node,
            {"messages": [{"role": "user", "content": "Let's continue."}]},
            {
                "intent_classification": {"intent": "continue"},
                "event_log": ["intent_classifier:completed"],
                "evidence_ledger": {"intent_classifier": {"pipeline": {"steps": []}}},
            },
            "intent_classifier",
        ),
        (
            make_counterpart_node,
            {"user_side": "side_a"},
            {
                "counterpart_response": {
                    "side": "side_b",
                    "message": "I can do 95.",
                    "offer": {"side": "side_b", "price": 95},
                },
                "event_log": ["counterpart:completed"],
                "evidence_ledger": {"counterpart": {"pipeline": {"steps": []}}},
            },
            "counterpart",
        ),
        (
            make_coach_node,
            {"user_side": "side_a"},
            {
                "coach_advice": {"summary": "Hold price."},
                "event_log": ["coach:completed"],
                "evidence_ledger": {"coach": {"pipeline": {"steps": []}}},
            },
            "coach",
        ),
        (
            make_evaluator_node,
            {"evaluation_mode": "rolling"},
            {
                "evaluation": {"score": 0.5},
                "event_log": ["evaluator:completed"],
                "evidence_ledger": {"evaluator": {"pipeline": {"steps": []}}},
            },
            "evaluator",
        ),
    ]

    for make_node, state, graph_result, agent_name in cases:
        node = make_node(FakeGraph(graph_result))

        updates = node(state)

        assert agent_name in updates["evidence_ledger"]


def test_agent_state_projections_preserve_existing_evidence_ledger():
    state = {
        "user_side": "side_a",
        "messages": [{"role": "user", "content": "Let's continue."}],
        "evidence_ledger": {
            "counterpart": {
                "pipeline": {"steps": [{"name": "generate"}]},
            },
        },
    }

    projections = [
        project_intent_classifier_state(state),
        project_counterpart_state(state),
        project_coach_state(state),
        project_evaluator_state(state),
    ]

    for projected in projections:
        assert projected["evidence_ledger"] == state["evidence_ledger"]
        assert projected["evidence_ledger"] is not state["evidence_ledger"]

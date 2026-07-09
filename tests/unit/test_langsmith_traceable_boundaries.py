from app.airag.chains.agents.coach import coach, coach_nodes
from app.airag.chains.agents.counterpart import counterpart, counterpart_nodes
from app.airag.chains.agents.evaluator import evaluator, evaluator_nodes
from app.airag.chains.agents.intent_classifier import (
    intent_classifier,
    intent_classifier_nodes,
)
from app.airag.chains.agents.learner import learner_agent
from app.airag.chains.agents.user_proxy_negotiator import (
    user_proxy,
    user_proxy_nodes,
)
from app.airag.chains.crag import crag, crag_nodes
from app.airag.chains.negotiation import negotiation


class _DummyStructuredModel:
    def with_structured_output(self, *args, **kwargs):
        return self

    def invoke(self, prompt):
        return prompt


class _CapturingStructuredModel:
    def __init__(self, response):
        self.response = response
        self.prompts = []

    def with_structured_output(self, *args, **kwargs):
        return self

    def invoke(self, prompt):
        self.prompts.append(prompt)
        return self.response


def test_public_invoke_wrappers_are_traceable():
    assert hasattr(negotiation.invoke_negotiation_turn, "__wrapped__")
    assert hasattr(coach.invoke_coach_advice, "__wrapped__")
    assert hasattr(counterpart.invoke_counterpart_response, "__wrapped__")
    assert hasattr(evaluator.invoke_evaluator_response, "__wrapped__")
    assert hasattr(evaluator.invoke_compact_evaluation, "__wrapped__")
    assert hasattr(user_proxy.invoke_user_proxy_turn, "__wrapped__")
    assert hasattr(learner_agent.invoke_simulation_learner_agent, "__wrapped__")


def test_graph_wrapper_nodes_are_traceable(capturing_graph_factory):
    graph, _captured = capturing_graph_factory(lambda state: state)

    assert hasattr(coach.make_coach_node(graph), "__wrapped__")
    assert hasattr(counterpart.make_counterpart_node(graph), "__wrapped__")
    assert hasattr(evaluator.make_evaluator_node(graph), "__wrapped__")
    assert hasattr(
        intent_classifier.make_intent_classifier_node(graph),
        "__wrapped__",
    )
    assert hasattr(user_proxy.make_user_proxy_node(graph), "__wrapped__")
    assert hasattr(crag.make_crag_node(graph), "__wrapped__")


def test_crag_invoke_nodes_are_traceable(capturing_graph_factory):
    graph, _captured = capturing_graph_factory(lambda state: state)

    assert hasattr(crag_nodes.make_crag_retrieve_node(graph), "__wrapped__")
    assert hasattr(crag_nodes.node_grade, "__wrapped__")
    assert hasattr(crag_nodes.node_rewrite, "__wrapped__")
    assert hasattr(crag_nodes.node_quality_check, "__wrapped__")
    assert hasattr(crag_nodes.node_generate, "__wrapped__")
    assert hasattr(crag_nodes.node_fallback, "__wrapped__")


def test_agent_model_and_subgraph_nodes_are_traceable(capturing_graph_factory):
    graph, _captured = capturing_graph_factory(lambda state: state)

    assert hasattr(coach_nodes.make_call_rag_node(graph), "__wrapped__")
    assert hasattr(
        coach_nodes.make_generate_coach_advice_node(_DummyStructuredModel()),
        "__wrapped__",
    )
    assert hasattr(
        coach_nodes.make_repair_coach_advice_node(_DummyStructuredModel()),
        "__wrapped__",
    )

    assert hasattr(
        counterpart_nodes.make_generate_counterpart_response_node(
            _DummyStructuredModel()
        ),
        "__wrapped__",
    )
    assert hasattr(
        counterpart_nodes.make_repair_counterpart_response_node(
            _DummyStructuredModel()
        ),
        "__wrapped__",
    )

    assert hasattr(evaluator_nodes.make_call_rag_node(graph), "__wrapped__")
    assert hasattr(
        evaluator_nodes.make_generate_evaluator_response_node(
            _DummyStructuredModel()
        ),
        "__wrapped__",
    )
    assert hasattr(
        evaluator_nodes.make_repair_evaluator_response_node(_DummyStructuredModel()),
        "__wrapped__",
    )

    assert hasattr(
        intent_classifier_nodes.make_classify_intent_node(_DummyStructuredModel()),
        "__wrapped__",
    )

    assert hasattr(
        user_proxy_nodes.make_generate_user_proxy_response_node(
            _DummyStructuredModel()
        ),
        "__wrapped__",
    )
    assert hasattr(
        user_proxy_nodes.make_repair_user_proxy_response_node(
            _DummyStructuredModel()
        ),
        "__wrapped__",
    )


def test_final_evaluator_nodes_use_custom_prompt_template():
    state = {
        "evaluation_mode": "final",
        "messages": [{"role": "user", "content": "Student turn"}],
        "evaluator_validation_error": "schema mismatch",
    }
    response = {
        "overall_score": 0.8,
        "goal_achievement": "Met the main negotiation goal.",
        "strengths": ["Clear framing"],
        "mistakes": ["Missed one tradeoff"],
        "concession_quality": "Measured and intentional.",
        "communication_quality": "Direct and credible.",
        "outcome_quality": "Strong overall outcome.",
        "proxy_usage_assessment": {
            "student_authored_turns": 1,
            "proxy_authored_turns": 0,
            "proxy_extent": "none",
            "impact_on_student_score": "No proxy use detected.",
        },
        "lessons": ["Keep probing for non-price terms."],
        "reasoning": "Final review.",
        "confidence": "medium",
        "missing_information": [],
    }
    model = _CapturingStructuredModel(response)
    prompt_template = "Custom final template\n{messages}"

    evaluator_nodes.make_generate_evaluator_response_node(
        model,
        prompt_template=prompt_template,
    )(state)
    evaluator_nodes.make_repair_evaluator_response_node(
        model,
        prompt_template=prompt_template,
    )(state)

    assert any("Custom final template" in prompt for prompt in model.prompts)

from app.airag.chains.agents.intent_classifier.intent_classifier import (
    make_intent_classifier_graph,
    make_intent_classifier_node,
)
from app.airag.chains.agents.intent_classifier.intent_classifier_helpers import (
    latest_user_message,
    render_intent_prompt,
)


class StructuredModel:
    def __init__(self, response=None, error=None):
        self.response = response
        self.error = error

    def with_structured_output(self, schema):
        return self

    def invoke(self, prompt):
        if self.error:
            raise self.error
        return self.response


def test_classifier_returns_high_confidence_end():
    graph = make_intent_classifier_graph(
        model=StructuredModel(
            {
                "intent": "end",
                "confidence": "high",
                "reasoning": "The student explicitly wants to finish.",
            }
        )
    )

    result = graph.invoke(
        {
            "messages": [
                {"role": "user", "content": "I am done with this simulation."}
            ]
        }
    )

    assert result["intent_classification"]["intent"] == "end"
    assert result["intent_classification"]["confidence"] == "high"


def test_classifier_failure_defaults_to_continue():
    graph = make_intent_classifier_graph(
        model=StructuredModel(error=RuntimeError("model unavailable"))
    )

    result = graph.invoke(
        {"messages": [{"role": "user", "content": "Maybe that could work."}]}
    )

    assert result["intent_classification"] == {
        "intent": "continue",
        "confidence": "low",
        "reasoning": "Intent classification failed; continue safely.",
    }
    assert "intent_classifier:fallback_continue" in result["event_log"]


def test_classifier_acceptance_language_can_end_simulation():
    graph = make_intent_classifier_graph(
        model=StructuredModel(
            {
                "intent": "end",
                "confidence": "high",
                "reasoning": "The student explicitly accepted the deal, so the simulation should end.",
            }
        )
    )

    result = graph.invoke(
        {
            "messages": [
                {"role": "user", "content": "OK. I agree to your terms."}
            ]
        }
    )

    assert result["intent_classification"]["intent"] == "end"
    assert result["intent_classification"]["confidence"] == "high"


def test_latest_user_message_supports_message_objects():
    class MessageObject:
        type = "human"
        content = "That works for me."

    state = {
        "messages": [
            {"role": "assistant", "content": "Can you accept this package?"},
            MessageObject(),
        ]
    }

    assert latest_user_message(state) == "That works for me."


def test_render_intent_prompt_uses_latest_user_message_only():
    prompt = render_intent_prompt(
        {
            "messages": [
                {"role": "user", "content": "Earlier offer."},
                {"role": "assistant", "content": "Can you confirm?"},
                {"role": "human", "content": "Let's do it."},
            ]
        }
    )

    assert "Let's do it." in prompt
    assert "Earlier offer." not in prompt


def test_intent_wrapper_passes_only_latest_student_message(
    agent_parent_state_factory,
    capturing_graph_factory,
):
    graph, captured = capturing_graph_factory(
        {
            "intent_classification": {
                "intent": "continue",
                "confidence": "high",
                "reasoning": "Continue.",
            },
            "event_log": ["intent_classifier:classified"],
        }
    )
    node = make_intent_classifier_node(graph)
    parent_state = agent_parent_state_factory(
        messages=[
            {"role": "assistant", "content": "OLD COUNTERPART"},
            {"role": "user", "content": "LATEST STUDENT"},
        ],
        event_log=["PARENT EVENT"],
    )

    result = node(parent_state)

    assert captured["messages"] == [{"role": "user", "content": "LATEST STUDENT"}]
    assert captured["event_log"] == []
    assert captured["evidence_ledger"] == parent_state["evidence_ledger"]
    assert captured["evidence_ledger"] is not parent_state["evidence_ledger"]
    assert "side_a_private_context" not in captured
    assert "evaluation" not in captured
    assert result == {
        "intent_classification": {
            "intent": "continue",
            "confidence": "high",
            "reasoning": "Continue.",
        },
        "event_log": ["intent_classifier:classified"],
    }

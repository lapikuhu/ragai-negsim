from typing import Any

from langgraph.graph import END, START, StateGraph

from app.airag.chains.agents.intent_classifier.intent_classifier_helpers import (
    get_default_intent_classifier_model,
)
from app.airag.chains.agents.context_projections import project_intent_classifier_state
from app.airag.chains.agents.intent_classifier.intent_classifier_model import (
    IntentClassifierGraphState,
)
from app.airag.chains.agents.intent_classifier.intent_classifier_nodes import (
    make_classify_intent_node,
    node_finalize_intent,
)


def make_intent_classifier_graph(
    model: Any = None,
    state_schema: type[IntentClassifierGraphState] = IntentClassifierGraphState,
):
    """
    Build and compile the end-intent classifier graph.
    Args:
        model: The language model to use for intent classification, 
            which should support structured output with 
            IntentClassificationModel. If None, the function will attempt 
            to load a default model.
        state_schema: The Pydantic model class to use for validating the graph
            state, which should be compatible with IntentClassifierGraphState.
    Returns:
        A compiled StateGraph instance representing the intent classifier flow.
    """
    classifier_model = model or get_default_intent_classifier_model()

    flow = StateGraph(state_schema)
    flow.add_node("classify_intent", make_classify_intent_node(classifier_model))
    flow.add_node("finalize_intent", node_finalize_intent)

    flow.add_edge(START, "classify_intent")
    flow.add_edge("classify_intent", "finalize_intent")
    flow.add_edge("finalize_intent", END)

    return flow.compile()


def make_intent_classifier_node(intent_classifier_graph: Any):
    """
    Wrap the classifier graph for use as a parent negotiation node.
    Args:
        intent_classifier_graph: The compiled intent classifier graph to wrap.
    Returns:
        A function that takes the current state and returns updates from the
        intent classifier graph.
    """

    def intent_classifier_node(state: dict[str, Any]) -> dict[str, Any]:
        result = intent_classifier_graph.invoke(project_intent_classifier_state(state))
        updates = {
            "intent_classification": result.get("intent_classification", {}),
        }
        if result.get("event_log"):
            updates["event_log"] = result["event_log"]
        return updates

    return intent_classifier_node

import pytest


def test_registry_resolves_crag_and_graphrag_handlers():
    from app.airag.evaluation.rag_eval_strategies import EVALUATION_STRATEGIES

    assert EVALUATION_STRATEGIES.require("crag").handler_name == "_evaluate_crag"
    assert EVALUATION_STRATEGIES.require("graphrag").handler_name == "_evaluate_graphrag"


@pytest.mark.parametrize("strategy", [None, "", "basic-rag"])
def test_registry_rejects_unregistered_strategies(strategy):
    from app.airag.evaluation.rag_eval_strategies import EVALUATION_STRATEGIES

    with pytest.raises(ValueError, match="Unsupported RAG evaluation strategy"):
        EVALUATION_STRATEGIES.require(strategy)

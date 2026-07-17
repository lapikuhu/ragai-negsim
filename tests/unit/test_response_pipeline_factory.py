from types import SimpleNamespace

import pytest


COMPONENT_SELECTIONS = {
    "document_grader": {"provider": "openai", "model": "grader-model"},
    "rewrite": {"provider": "ollama", "model": "rewrite-model"},
    "generate": {"provider": "openai", "model": "generate-model"},
    "hallucination_grader": {"provider": "ollama", "model": "hallucination-model"},
    "answer_grader": {"provider": "openai", "model": "answer-model"},
    "fallback": {"provider": "ollama", "model": "fallback-model"},
}


@pytest.mark.parametrize("strategy", ["crag", "graphrag"])
def test_shared_factory_forwards_complete_response_configuration(monkeypatch, strategy):
    from app.airag import pipeline_factory

    retriever = object()
    graph = object()
    captured = {}

    def fake_make_component_chains(selections):
        captured["selections"] = selections
        return {"chains": selections}

    def fake_make_crag(**kwargs):
        captured["make_crag"] = kwargs
        return graph

    monkeypatch.setattr(
        pipeline_factory,
        "make_crag_component_chains",
        fake_make_component_chains,
    )
    monkeypatch.setattr(pipeline_factory, "make_crag", fake_make_crag)

    config = pipeline_factory.ResponsePipelineConfig(
        strategy=strategy,
        reranker="cohere",
        top_n=5,
        max_rewrite_attempts=4,
        llm_components=COMPONENT_SELECTIONS,
    )
    pipeline = pipeline_factory.build_response_pipeline(retriever, config)

    assert captured["selections"] == COMPONENT_SELECTIONS
    assert captured["make_crag"] == {
        "retriever_obj": retriever,
        "state_schema": pipeline_factory.CRAGState,
        "max_rewrite_attempts": 4,
        "reranker_name": "cohere",
        "rerank_top_k": 5,
        "component_chains": {"chains": COMPONENT_SELECTIONS},
    }
    assert pipeline.graph is graph
    assert pipeline.resolved_metadata["llm_components"] == COMPONENT_SELECTIONS
    assert pipeline.resolved_metadata["reranker"]["implementation"] == "cohere"
    assert pipeline.resolved_metadata["pipeline_version"]
    assert set(pipeline.resolved_metadata["prompt_hashes"]) == set(COMPONENT_SELECTIONS)


def test_normalize_graphrag_response_configuration_preserves_simulation_defaults():
    from app.airag.pipeline_factory import normalize_response_pipeline_config

    config = normalize_response_pipeline_config(
        "graphrag",
        {
            "evidence_limit": 7,
            "llm_components": COMPONENT_SELECTIONS,
        },
    )

    assert config.strategy == "graphrag"
    assert config.reranker == "none"
    assert config.top_n == 7
    assert config.max_rewrite_attempts == 1
    assert config.llm_components == COMPONENT_SELECTIONS


def test_response_pipeline_delegates_invocation_to_compiled_graph():
    from app.airag.pipeline_factory import ResponsePipeline

    compiled = SimpleNamespace(invoke=lambda state, config=None: (state, config))
    pipeline = ResponsePipeline(
        graph=compiled,
        resolved_metadata={"pipeline_version": "test"},
    )

    assert pipeline.invoke({"question": "BATNA?"}, {"run": "test"}) == (
        {"question": "BATNA?"},
        {"run": "test"},
    )

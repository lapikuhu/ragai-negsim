from datetime import datetime

import pytest
from pydantic import ValidationError

from app.schemas.llm_models_schemas import (
    LLMModelCatalogItem,
    LLMModelCatalogResponse,
    LLMProviderCatalog,
)
from app.schemas.rag_eval_schemas import (
    CragEvaluationConfiguration,
    GraphRagEvaluationConfiguration,
    HybridChunkingConfiguration,
    RagEvalConfigurationCreateRequest,
    RagEvalConfigurationRead,
    RagEvalConfigurationUpdate,
    RagEvalConfigurationUpdateRequest,
    RecursiveChunkingConfiguration,
    SemanticChunkingConfiguration,
    apply_rag_eval_configuration_patch,
    dump_rag_eval_configuration_snapshot,
)
from app.services import llm_models_service


COMPONENT_SELECTIONS = {
    "document_grader": {"provider": "OPENAI", "model": " gpt-4o-mini "},
    "query_rewriter": {"provider": "openai", "model": "gpt-4o-mini"},
    "answer_generator": {"provider": "openai", "model": "gpt-4o-mini"},
    "hallucination_grader": {"provider": "openai", "model": "gpt-4o-mini"},
    "answer_grader": {"provider": "openai", "model": "gpt-4o-mini"},
    "fallback_generator": {"provider": "openai", "model": "gpt-4o-mini"},
}


@pytest.fixture(autouse=True)
def available_llm_catalog(monkeypatch):
    catalog = LLMModelCatalogResponse(
        providers=[
            LLMProviderCatalog(
                provider="openai",
                models=[LLMModelCatalogItem(name="gpt-4o-mini")],
            ),
            LLMProviderCatalog(
                provider="ollama",
                models=[LLMModelCatalogItem(name="qwen2.5:3b")],
            ),
        ]
    )
    monkeypatch.setattr(llm_models_service, "list_llm_model_catalog", lambda: catalog)


def crag_payload(**overrides):
    value = {
        "strategy": "crag",
        "retrieval_embedding_model": "text-embedding-3-small",
        "top_k": 4,
        "reranker": "cross_encoder",
        "top_n": 3,
        "rewrite_limit": 2,
        **COMPONENT_SELECTIONS,
    }
    value.update(overrides)
    return value


def graph_payload(**overrides):
    value = {
        "strategy": "graphrag",
        "extraction_llm": {"provider": "openai", "model": "gpt-4o-mini"},
        "graph_embedding_model": "text-embedding-3-small",
        "max_paths_per_chunk": 10,
        "retrieval_mode": "semantic",
        "evidence_limit": 6,
        "traversal_depth": 2,
        "rrf_constant": 60,
        **COMPONENT_SELECTIONS,
    }
    value.update(overrides)
    return value


def configuration_payload(*, chunking=None, rag=None, metric_k=3):
    return {
        "name": "baseline evaluation",
        "chunking": chunking
        or {"strategy": "recursive", "chunk_size": 1000, "chunk_overlap": 200},
        "rag": rag or crag_payload(),
        "metrics": {
            "k": metric_k,
            "ragas_judge": {"provider": "openai", "model": "gpt-4o-mini"},
            "judge_embedding_model": "text-embedding-3-small",
        },
    }


@pytest.mark.parametrize(
    ("payload", "expected_type"),
    [
        ({"strategy": "recursive"}, RecursiveChunkingConfiguration),
        ({"strategy": "semantic"}, SemanticChunkingConfiguration),
        ({"strategy": "hybrid"}, HybridChunkingConfiguration),
    ],
)
def test_chunking_discriminator_normalizes_each_supported_variant(payload, expected_type):
    config = RagEvalConfigurationCreateRequest.model_validate(
        configuration_payload(chunking=payload)
    )

    assert isinstance(config.chunking, expected_type)


@pytest.mark.parametrize("strategy", ["semantic", "hybrid"])
def test_semantic_chunking_variants_reject_user_embedding_selection(strategy):
    with pytest.raises(ValidationError) as exc:
        RagEvalConfigurationCreateRequest.model_validate(
            configuration_payload(
                chunking={
                    "strategy": strategy,
                    "embedding_model": "text-embedding-3-small",
                }
            )
        )

    assert f"chunking.{strategy}" in str(exc.value)
    assert "embedding_model" in str(exc.value)


def test_chunking_variants_accept_only_applicable_parameters():
    with pytest.raises(ValidationError) as exc:
        RagEvalConfigurationCreateRequest.model_validate(
            configuration_payload(
                chunking={"strategy": "semantic", "chunk_size": 1000}
            )
        )

    assert "chunking.semantic" in str(exc.value)
    assert "chunk_size" in str(exc.value)


@pytest.mark.parametrize(
    "chunking",
    [
        {"strategy": "recursive", "chunk_size": 99},
        {"strategy": "recursive", "chunk_size": 100, "chunk_overlap": 100},
        {"strategy": "semantic", "breakpoint_threshold_amount": 0},
        {"strategy": "semantic", "breakpoint_threshold_type": " "},
        {"strategy": "hybrid", "buffer_size": -1},
    ],
)
def test_chunking_variants_enforce_production_bounds_and_relationships(chunking):
    with pytest.raises(ValidationError):
        RagEvalConfigurationCreateRequest.model_validate(
            configuration_payload(chunking=chunking)
        )


@pytest.mark.parametrize(
    ("rag", "expected_type"),
    [
        (crag_payload(), CragEvaluationConfiguration),
        (graph_payload(), GraphRagEvaluationConfiguration),
    ],
)
def test_rag_discriminator_normalizes_each_supported_variant(rag, expected_type):
    config = RagEvalConfigurationCreateRequest.model_validate(
        configuration_payload(rag=rag)
    )

    assert isinstance(config.rag, expected_type)
    assert config.rag.document_grader.provider == "openai"
    assert config.rag.document_grader.model == "gpt-4o-mini"


def test_default_crag_and_metric_controls_form_a_valid_configuration():
    rag = crag_payload()
    rag.pop("top_n")
    payload = configuration_payload(rag=rag)
    payload["metrics"].pop("k")

    config = RagEvalConfigurationCreateRequest.model_validate(payload)

    assert config.rag.top_n == 3
    assert config.metrics.k == 3


def test_configuration_contains_no_profile_foreign_keys():
    with pytest.raises(ValidationError) as exc:
        RagEvalConfigurationCreateRequest.model_validate(
            {
                **configuration_payload(),
                "rag_profile_id": 1,
                "chunking_profile_id": 2,
            }
        )

    assert "rag_profile_id" in str(exc.value)
    assert "chunking_profile_id" in str(exc.value)


def test_crag_requires_all_six_explicit_component_selections():
    payload = crag_payload()
    del payload["fallback_generator"]

    with pytest.raises(ValidationError) as exc:
        RagEvalConfigurationCreateRequest.model_validate(
            configuration_payload(rag=payload)
        )

    assert "fallback_generator" in str(exc.value)


def test_crag_enforces_top_n_not_greater_than_top_k():
    with pytest.raises(ValidationError, match="top_n must be less than or equal to top_k"):
        RagEvalConfigurationCreateRequest.model_validate(
            configuration_payload(rag=crag_payload(top_k=2, top_n=3), metric_k=2)
        )


def test_crag_none_reranker_normalizes_final_context_capacity_to_top_k():
    config = RagEvalConfigurationCreateRequest.model_validate(
        configuration_payload(
            rag=crag_payload(reranker="none", top_k=4, top_n=1),
            metric_k=4,
        )
    )

    assert config.rag.top_n == 4


@pytest.mark.parametrize(
    "forbidden",
    [
        {"extractors": ["simple"]},
        {"extractor": "simple"},
        {"schema": {"entities": []}},
        {"schema_definition": {}},
        {"strict_schema": True},
    ],
)
def test_graphrag_rejects_extractor_and_schema_configuration(forbidden):
    with pytest.raises(ValidationError):
        RagEvalConfigurationCreateRequest.model_validate(
            configuration_payload(rag=graph_payload(**forbidden))
        )


@pytest.mark.parametrize("mode", ["semantic", "cypher", "hybrid"])
def test_graphrag_accepts_supported_retrieval_modes(mode):
    result = RagEvalConfigurationCreateRequest.model_validate(
        configuration_payload(rag=graph_payload(retrieval_mode=mode))
    )

    assert result.rag.retrieval_mode == mode


@pytest.mark.parametrize(
    "overrides",
    [
        {"retrieval_mode": "keyword"},
        {"evidence_limit": 31},
        {"traversal_depth": 6},
        {"rrf_constant": 201},
        {"max_paths_per_chunk": 0},
    ],
)
def test_graphrag_controls_are_bounded_and_validated(overrides):
    with pytest.raises(ValidationError):
        RagEvalConfigurationCreateRequest.model_validate(
            configuration_payload(rag=graph_payload(**overrides))
        )


@pytest.mark.parametrize(
    ("rag", "metric_k", "message"),
    [
        (crag_payload(top_n=2), 3, "metrics.k must be less than or equal to rag.top_n"),
        (
            graph_payload(evidence_limit=2),
            3,
            "metrics.k must be less than or equal to rag.evidence_limit",
        ),
    ],
)
def test_metric_k_cannot_exceed_final_context_capacity(rag, metric_k, message):
    with pytest.raises(ValidationError, match=message):
        RagEvalConfigurationCreateRequest.model_validate(
            configuration_payload(rag=rag, metric_k=metric_k)
        )


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("chunking", "chunk_size"), True),
        (("rag", "top_k"), True),
        (("rag", "rewrite_limit"), False),
        (("metrics", "k"), True),
    ],
)
def test_boolean_values_are_rejected_for_integer_controls(path, value):
    payload = configuration_payload()
    payload[path[0]][path[1]] = value

    with pytest.raises(ValidationError) as exc:
        RagEvalConfigurationCreateRequest.model_validate(payload)

    assert all(part in str(exc.value) for part in path)


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("rag", "retrieval_embedding_model"), "unknown-embedding"),
        (("metrics", "judge_embedding_model"), "unknown-embedding"),
    ],
)
def test_project_embedding_availability_is_enforced(path, value):
    payload = configuration_payload()
    payload[path[0]][path[1]] = value

    with pytest.raises(ValidationError, match="Unsupported model name"):
        RagEvalConfigurationCreateRequest.model_validate(payload)


def test_graph_embedding_availability_is_enforced():
    with pytest.raises(ValidationError, match="Unsupported model name"):
        RagEvalConfigurationCreateRequest.model_validate(
            configuration_payload(
                rag=graph_payload(graph_embedding_model="unknown-embedding")
            )
        )


def test_reranker_availability_is_enforced():
    with pytest.raises(ValidationError, match="reranker"):
        RagEvalConfigurationCreateRequest.model_validate(
            configuration_payload(rag=crag_payload(reranker="not-installed"))
        )


@pytest.mark.parametrize(
    "selection",
    [
        {"provider": "unknown", "model": "gpt-4o-mini"},
        {"provider": "openai", "model": "not-available"},
        {"provider": "openai", "model": " "},
    ],
)
def test_llm_provider_and_model_availability_is_enforced(selection):
    with pytest.raises(ValidationError):
        RagEvalConfigurationCreateRequest.model_validate(
            configuration_payload(
                rag=crag_payload(document_grader=selection)
            )
        )


def test_patch_replaces_nested_objects_then_revalidates_complete_configuration():
    current = RagEvalConfigurationCreateRequest.model_validate(configuration_payload())
    patch = RagEvalConfigurationUpdateRequest.model_validate(
        {"rag": crag_payload(top_k=3, top_n=3)}
    )

    updated = apply_rag_eval_configuration_patch(current, patch)

    assert updated.rag.top_k == 3
    assert updated.rag.top_n == 3
    assert updated.chunking == current.chunking


def test_patch_cannot_bypass_cross_field_validation():
    current = RagEvalConfigurationCreateRequest.model_validate(configuration_payload())
    patch = RagEvalConfigurationUpdateRequest.model_validate(
        {"metrics": {**current.metrics.model_dump(), "k": 4}}
    )

    with pytest.raises(ValidationError, match="metrics.k"):
        apply_rag_eval_configuration_patch(current, patch)


def test_internal_patch_audit_metadata_does_not_leak_into_configuration():
    current = RagEvalConfigurationCreateRequest.model_validate(configuration_payload())
    patch = RagEvalConfigurationUpdate(
        name="renamed evaluation",
        last_edit_by_user_id=11,
    )

    updated = apply_rag_eval_configuration_patch(current, patch)

    assert updated.name == "renamed evaluation"
    assert "last_edit_by_user_id" not in updated.model_dump()


def test_snapshot_dump_is_normalized_stable_and_excludes_read_metadata():
    read = RagEvalConfigurationRead(
        **configuration_payload(),
        id=7,
        created_by_user_id=9,
        last_edit_by_user_id=None,
        created_at=datetime(2025, 1, 1),
        last_updated=datetime(2025, 1, 2),
    )

    first = dump_rag_eval_configuration_snapshot(read)
    second = dump_rag_eval_configuration_snapshot(
        RagEvalConfigurationCreateRequest.model_validate(first)
    )

    assert first == second
    assert first["rag"]["document_grader"] == {
        "provider": "openai",
        "model": "gpt-4o-mini",
    }
    assert set(first) == {"name", "chunking", "rag", "metrics"}


def test_snapshot_dump_revalidates_an_existing_mutated_configuration_instance():
    config = RagEvalConfigurationCreateRequest.model_validate(configuration_payload())
    config.metrics.k = config.rag.top_n + 1

    with pytest.raises(ValidationError, match="metrics.k"):
        dump_rag_eval_configuration_snapshot(config)

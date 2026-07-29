import inspect
import math

import pytest

from app.airag.rag_profiles.definitions import (
    get_crag_retrieval_mode,
    normalize_rag_profile_config,
)
from app.airag.retrieval.retrievers import make_dense_retriever


def test_crag_retrieval_contract_defaults_are_unambiguous():
    config = normalize_rag_profile_config("crag", {})

    assert config["bm25_weight"] == 0.0
    assert config["dense_k"] == 4
    assert config["bm25_k"] == 4
    assert config["final_top_k"] == 4
    assert get_crag_retrieval_mode(config["bm25_weight"]) == "dense"


@pytest.mark.parametrize("bm25_weight", [0.0, 1.0])
@pytest.mark.parametrize("candidate_k", [1, 20])
def test_crag_retrieval_contract_accepts_inclusive_bounds(
    bm25_weight,
    candidate_k,
):
    config = normalize_rag_profile_config(
        "crag",
        {
            "bm25_weight": bm25_weight,
            "dense_k": candidate_k,
            "bm25_k": candidate_k,
            "final_top_k": candidate_k,
            "top_n": candidate_k,
        },
    )

    assert config["bm25_weight"] == bm25_weight
    assert config["dense_k"] == candidate_k
    assert config["bm25_k"] == candidate_k
    assert config["final_top_k"] == candidate_k


@pytest.mark.parametrize(
    ("field_name", "invalid_value"),
    [
        ("bm25_weight", -0.01),
        ("bm25_weight", 1.01),
        ("bm25_weight", math.nan),
        ("dense_k", 0),
        ("dense_k", 21),
        ("bm25_k", 0),
        ("bm25_k", 21),
        ("final_top_k", 0),
        ("final_top_k", 21),
    ],
)
def test_crag_retrieval_contract_rejects_values_outside_bounds(
    field_name,
    invalid_value,
):
    with pytest.raises(ValueError, match=field_name):
        normalize_rag_profile_config("crag", {field_name: invalid_value})


def test_crag_retrieval_contract_rejects_final_k_above_both_candidate_limits():
    with pytest.raises(
        ValueError,
        match=r"final_top_k must be <= max\(dense_k, bm25_k\)",
    ):
        normalize_rag_profile_config(
            "crag",
            {
                "dense_k": 2,
                "bm25_k": 3,
                "final_top_k": 4,
            },
        )


def test_crag_retrieval_contract_keeps_reranking_below_effective_retrieval_limit():
    with pytest.raises(ValueError, match="top_n must be <= effective retrieval capacity"):
        normalize_rag_profile_config(
            "crag",
            {
                "bm25_weight": 0.5,
                "final_top_k": 2,
                "top_n": 3,
            },
        )


@pytest.mark.parametrize(
    ("field_name", "invalid_value"),
    [
        ("bm25_weight", True),
        ("bm25_weight", "0.5"),
        ("bm25_weight", None),
        ("dense_k", True),
        ("dense_k", 1.5),
        ("dense_k", "4"),
        ("bm25_k", False),
        ("bm25_k", 2.5),
        ("bm25_k", "4"),
        ("final_top_k", True),
        ("final_top_k", 3.5),
        ("final_top_k", "4"),
    ],
)
def test_crag_retrieval_contract_rejects_non_numeric_or_non_integer_values(
    field_name,
    invalid_value,
):
    with pytest.raises(ValueError, match=field_name):
        normalize_rag_profile_config("crag", {field_name: invalid_value})


def test_crag_retrieval_contract_rejects_removed_top_k_field():
    with pytest.raises(ValueError, match="top_k"):
        normalize_rag_profile_config("crag", {"top_k": 4})


@pytest.mark.parametrize(
    ("bm25_weight", "dense_k", "bm25_k", "final_top_k", "effective_capacity"),
    [
        (0.0, 2, 5, 4, 2),
        (1.0, 5, 2, 4, 2),
        (0.5, 2, 5, 4, 4),
    ],
)
def test_crag_retrieval_contract_uses_mode_specific_capacity_with_reranker(
    bm25_weight,
    dense_k,
    bm25_k,
    final_top_k,
    effective_capacity,
):
    config = normalize_rag_profile_config(
        "crag",
        {
            "bm25_weight": bm25_weight,
            "dense_k": dense_k,
            "bm25_k": bm25_k,
            "final_top_k": final_top_k,
            "top_n": effective_capacity,
        },
    )

    assert config["top_n"] == effective_capacity

    with pytest.raises(ValueError, match="top_n must be <= effective retrieval capacity"):
        normalize_rag_profile_config(
            "crag",
            {
                "bm25_weight": bm25_weight,
                "dense_k": dense_k,
                "bm25_k": bm25_k,
                "final_top_k": final_top_k,
                "top_n": effective_capacity + 1,
            },
        )


@pytest.mark.parametrize(
    ("bm25_weight", "dense_k", "bm25_k", "final_top_k", "effective_capacity"),
    [
        (0.0, 2, 5, 4, 2),
        (1.0, 5, 2, 4, 2),
        (0.5, 2, 5, 4, 4),
    ],
)
def test_crag_retrieval_contract_none_reranker_normalizes_to_mode_capacity(
    bm25_weight,
    dense_k,
    bm25_k,
    final_top_k,
    effective_capacity,
):
    config = normalize_rag_profile_config(
        "crag",
        {
            "bm25_weight": bm25_weight,
            "dense_k": dense_k,
            "bm25_k": bm25_k,
            "final_top_k": final_top_k,
            "reranker": "none",
            "top_n": 1,
        },
    )

    assert config["top_n"] == effective_capacity


def test_crag_retrieval_contract_rejects_concrete_artifact_identity():
    with pytest.raises(ValueError, match="bm25_artifact_id"):
        normalize_rag_profile_config("crag", {"bm25_artifact_id": 123})


@pytest.mark.parametrize(
    ("bm25_weight", "expected_mode"),
    [
        (0.0, "dense"),
        (0.25, "hybrid"),
        (1.0, "bm25"),
    ],
)
def test_crag_retrieval_weight_defines_three_modes(
    bm25_weight,
    expected_mode,
):
    config = normalize_rag_profile_config(
        "crag",
        {"bm25_weight": bm25_weight},
    )

    assert get_crag_retrieval_mode(config["bm25_weight"]) == expected_mode


def test_make_dense_retriever_signature_is_unchanged():
    assert tuple(inspect.signature(make_dense_retriever).parameters) == (
        "vector_store",
        "k",
        "metadata_filter",
    )
    assert inspect.signature(make_dense_retriever).parameters["k"].default == 4
    assert (
        inspect.signature(make_dense_retriever)
        .parameters["metadata_filter"]
        .default
        is None
    )


def test_make_dense_retriever_passes_search_kwargs_to_vector_store_adapter():
    calls = []
    expected_retriever = object()

    class FakeVectorStore:
        def as_retriever(self, *, search_kwargs):
            calls.append(search_kwargs)
            return expected_retriever

    result = make_dense_retriever(
        FakeVectorStore(),
        k=7,
        metadata_filter={"corpus_index_id": 42},
    )

    assert result is expected_retriever
    assert calls == [{"k": 7, "filter": {"corpus_index_id": 42}}]

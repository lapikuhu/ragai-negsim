from __future__ import annotations

import logging

import pytest

from app.airag.evaluation.embedding_cache import (
    RedisCachedEmbeddings,
    build_embedding_cache_key,
    decode_embedding_vector,
    encode_embedding_vector,
)


class FakePipeline:
    def __init__(self, values: dict[str, bytes]) -> None:
        self.values = values
        self.pending: list[tuple[str, bytes, int]] = []
        self.executions = 0

    def set(self, key: str, value: bytes, *, ex: int):
        self.pending.append((key, value, ex))
        return self

    def execute(self):
        self.executions += 1
        for key, value, _ttl in self.pending:
            self.values[key] = value
        return [True] * len(self.pending)


class FakeRedis:
    def __init__(self) -> None:
        self.values: dict[str, bytes] = {}
        self.mget_calls: list[list[str]] = []
        self.pipelines: list[FakePipeline] = []
        self.error: Exception | None = None

    def mget(self, keys: list[str]):
        if self.error is not None:
            raise self.error
        self.mget_calls.append(list(keys))
        return [self.values.get(key) for key in keys]

    def pipeline(self, *, transaction: bool):
        assert transaction is False
        pipeline = FakePipeline(self.values)
        self.pipelines.append(pipeline)
        return pipeline


class FakeEmbeddings:
    def __init__(self) -> None:
        self.document_calls: list[list[str]] = []
        self.query_calls: list[str] = []

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        self.document_calls.append(list(texts))
        return [[float(len(text)), float(sum(text.encode("utf-8")))] for text in texts]

    def embed_query(self, text: str) -> list[float]:
        self.query_calls.append(text)
        return [float(len(text)), -1.0]


def make_wrapper(redis_client: FakeRedis, embeddings: FakeEmbeddings):
    return RedisCachedEmbeddings(
        embeddings,
        redis_client=redis_client,
        suite_content_hash="suite-hash",
        provider="openai",
        model="text-embedding-3-small",
        dimensions=2,
        ttl_seconds=600,
    )


def test_cache_key_is_versioned_content_addressed_and_operation_specific():
    common = {
        "suite_content_hash": "suite-hash",
        "provider": "openai",
        "model": "text-embedding-3-small",
        "dimensions": 2,
        "text": "Exact text ",
    }

    document_key = build_embedding_cache_key(operation="document", **common)
    query_key = build_embedding_cache_key(operation="query", **common)

    assert document_key.startswith("rag-eval:embedding:v1:")
    assert document_key != query_key
    assert "Exact text" not in document_key
    assert document_key != build_embedding_cache_key(
        operation="document",
        **{**common, "text": "Exact text"},
    )
    assert document_key != build_embedding_cache_key(
        operation="document",
        **{**common, "model": "different-model"},
    )


def test_binary_vector_round_trip_validates_dimensions_and_payload():
    payload = encode_embedding_vector([1.25, -2.5])

    assert decode_embedding_vector(payload, expected_dimensions=2) == pytest.approx(
        [1.25, -2.5]
    )
    with pytest.raises(ValueError, match="dimensions"):
        decode_embedding_vector(payload, expected_dimensions=3)
    with pytest.raises(ValueError, match="payload"):
        decode_embedding_vector(payload[:-1], expected_dimensions=2)
    with pytest.raises(ValueError, match="finite"):
        encode_embedding_vector([float("nan")])


def test_document_cache_handles_cold_warm_mixed_and_duplicate_batches():
    redis_client = FakeRedis()
    embeddings = FakeEmbeddings()
    wrapper = make_wrapper(redis_client, embeddings)

    cold = wrapper.embed_documents(["alpha", "beta", "alpha"])
    warm = wrapper.embed_documents(["beta", "gamma", "alpha"])

    assert cold == [cold[0], cold[1], cold[0]]
    assert warm[0] == cold[1]
    assert warm[2] == cold[0]
    assert embeddings.document_calls == [["alpha", "beta"], ["gamma"]]
    assert len(redis_client.mget_calls) == 2
    assert all(pipeline.executions == 1 for pipeline in redis_client.pipelines)
    assert {
        ttl
        for pipeline in redis_client.pipelines
        for _key, _value, ttl in pipeline.pending
    } == {600}
    assert wrapper.metrics["hits"] == 2
    assert wrapper.metrics["misses"] == 4
    assert wrapper.metrics["writes"] == 3
    assert wrapper.metrics["provider_vectors_requested"] == 3


def test_query_cache_uses_separate_key_space():
    redis_client = FakeRedis()
    embeddings = FakeEmbeddings()
    wrapper = make_wrapper(redis_client, embeddings)

    document = wrapper.embed_documents(["same"])[0]
    first_query = wrapper.embed_query("same")
    second_query = wrapper.embed_query("same")

    assert first_query == second_query
    assert first_query != document
    assert embeddings.query_calls == ["same"]


def test_cold_and_warm_paths_return_the_same_float32_values():
    class PreciseEmbeddings(FakeEmbeddings):
        def embed_documents(self, texts: list[str]) -> list[list[float]]:
            self.document_calls.append(list(texts))
            return [[0.123456789, -0.987654321] for _text in texts]

    redis_client = FakeRedis()
    wrapper = make_wrapper(redis_client, PreciseEmbeddings())

    cold = wrapper.embed_documents(["alpha"])
    warm = wrapper.embed_documents(["alpha"])

    assert cold == warm


def test_corrupt_value_is_recomputed_and_overwritten():
    redis_client = FakeRedis()
    embeddings = FakeEmbeddings()
    wrapper = make_wrapper(redis_client, embeddings)
    key = build_embedding_cache_key(
        suite_content_hash="suite-hash",
        provider="openai",
        model="text-embedding-3-small",
        dimensions=2,
        operation="document",
        text="alpha",
    )
    redis_client.values[key] = b"broken"

    result = wrapper.embed_documents(["alpha"])

    assert result[0] == pytest.approx([5.0, 518.0])
    assert decode_embedding_vector(
        redis_client.values[key], expected_dimensions=2
    ) == pytest.approx(result[0])
    assert wrapper.metrics["corrupt_entries"] == 1


def test_redis_failure_disables_cache_for_run_and_falls_back_once(caplog):
    redis_client = FakeRedis()
    redis_client.error = ConnectionError("redis unavailable")
    embeddings = FakeEmbeddings()
    wrapper = make_wrapper(redis_client, embeddings)

    with caplog.at_level(logging.WARNING):
        first = wrapper.embed_documents(["alpha"])
        second = wrapper.embed_documents(["alpha"])

    assert first == second
    assert embeddings.document_calls == [["alpha"], ["alpha"]]
    assert wrapper.metrics["active"] is False
    assert wrapper.metrics["backend_errors"] == 1
    assert sum("embedding cache disabled" in record.message for record in caplog.records) == 1


def test_provider_error_is_not_hidden():
    class BrokenEmbeddings(FakeEmbeddings):
        def embed_documents(self, texts: list[str]) -> list[list[float]]:
            raise RuntimeError("provider failed")

    wrapper = make_wrapper(FakeRedis(), BrokenEmbeddings())

    with pytest.raises(RuntimeError, match="provider failed"):
        wrapper.embed_documents(["alpha"])
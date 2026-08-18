from __future__ import annotations

import os
from uuid import uuid4

import pytest
from redis import Redis
from redis.exceptions import RedisError

from app.airag.evaluation.embedding_cache import (
    RedisCachedEmbeddings,
    build_embedding_cache_key,
    decode_embedding_vector,
)


class RecordingEmbeddings:
    def __init__(self) -> None:
        self.document_calls = 0

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        self.document_calls += 1
        return [[float(len(text)), 1.25] for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return [float(len(text)), -1.25]


@pytest.mark.integration
def test_real_redis_reuses_binary_embedding_with_ttl_across_wrappers():
    redis_url = os.getenv("RAG_EVAL_REDIS_TEST_URL", "redis://localhost:6379/15")
    client = Redis.from_url(
        redis_url,
        decode_responses=False,
        socket_connect_timeout=0.5,
        socket_timeout=0.5,
    )
    try:
        client.ping()
    except RedisError as exc:
        pytest.skip(f"Redis integration service unavailable: {type(exc).__name__}")

    suite_hash = f"integration-{uuid4().hex}"
    text = "integration cache text"
    key = build_embedding_cache_key(
        suite_content_hash=suite_hash,
        provider="fake",
        model="fake-embedding",
        dimensions=2,
        operation="document",
        text=text,
    )
    first_provider = RecordingEmbeddings()
    second_provider = RecordingEmbeddings()
    try:
        first = RedisCachedEmbeddings(
            first_provider,
            redis_client=client,
            suite_content_hash=suite_hash,
            provider="fake",
            model="fake-embedding",
            dimensions=2,
            ttl_seconds=60,
        ).embed_documents([text])
        second = RedisCachedEmbeddings(
            second_provider,
            redis_client=client,
            suite_content_hash=suite_hash,
            provider="fake",
            model="fake-embedding",
            dimensions=2,
            ttl_seconds=60,
        ).embed_documents([text])

        payload = client.get(key)
        assert payload is not None
        assert decode_embedding_vector(payload, expected_dimensions=2) == first[0]
        assert second == first
        assert first_provider.document_calls == 1
        assert second_provider.document_calls == 0
        assert 0 < client.ttl(key) <= 60
    finally:
        client.delete(key)
        client.close()

"""
Optional Redis cache for deterministic RAG-evaluation embeddings.
The evaluation suite remains the same, so for the same vectors, the same
embedding provider, and the same embedding model, the cache can be used to
avoid repeated calls to the embedding provider. The cache is keyed by a
hash of the suite content, the embedding provider, the embedding model, the
embedding dimensions, the embedding operation (document or query), and a
hash of the source text. The cache is versioned to allow for future changes
to the encoding format. The cache is implemented using Redis.
"""

from __future__ import annotations

import hashlib
import logging
import math
import struct
import threading
from time import perf_counter
from typing import Any, Literal


logger = logging.getLogger(__name__)

# Redis options
EMBEDDING_CACHE_SCHEMA_VERSION = 1
EMBEDDING_CACHE_NAMESPACE = "rag-eval:embedding:v1"
_VECTOR_MAGIC = b"REMB"
_VECTOR_HEADER = struct.Struct("<4sBI")
_REDIS_CLIENT: Any | None = None
_REDIS_CLIENT_URL: str | None = None
_REDIS_CLIENT_LOCK = threading.Lock() # Keep single threaded Redis client

EmbeddingOperation = Literal["document", "query"]


def build_embedding_cache_key(
    *,
    suite_content_hash: str,
    provider: str,
    model: str,
    dimensions: int,
    operation: EmbeddingOperation,
    text: str,
) -> str:
    """
    Build a versioned key without exposing source text.

    Args:
        suite_content_hash: Hash of the suite content.
        provider: Embedding provider name.
        model: Embedding model name.
        dimensions: Number of embedding dimensions.
        operation: Type of embedding operation ("document" or "query").
        text: Source text to be embedded.
    Returns:
        A versioned cache key string.
    Raises:
        ValueError: If dimensions is not positive or operation is invalid.
    """
    if dimensions < 1:
        raise ValueError("embedding dimensions must be positive")
    if operation not in {"document", "query"}:
        raise ValueError("embedding operation must be document or query")
    # Hash the text to avoid exposing it in the cache key
    text_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
    identity = "|".join(
        (
            suite_content_hash,
            provider.strip().lower(),
            model.strip(),
            str(dimensions),
            operation,
        )
    )
    # Hash the identity
    identity_hash = hashlib.sha256(identity.encode("utf-8")).hexdigest()
    return f"{EMBEDDING_CACHE_NAMESPACE}:{identity_hash}:{text_hash}"


def encode_embedding_vector(vector: list[float]) -> bytes:
    """
    Encode one finite vector as a versioned little-endian float32 payload.
    Args:
        vector (list[float]): The embedding vector to encode.
    Returns:
        bytes: The encoded embedding vector as a byte string.
    Raises:
        ValueError: If the vector is empty or contains non-finite values.
    """
    if not vector:
        raise ValueError("embedding vector must not be empty")
    values = [float(value) for value in vector]
    if not all(math.isfinite(value) for value in values):
        raise ValueError("embedding vector values must be finite")
    return _VECTOR_HEADER.pack(
        _VECTOR_MAGIC,
        EMBEDDING_CACHE_SCHEMA_VERSION,
        len(values),
    ) + struct.pack(f"<{len(values)}f", *values)


def decode_embedding_vector(
    payload: bytes,
    *,
    expected_dimensions: int,
) -> list[float]:
    """
    Decode and validate one cached embedding vector.

    Args:
        payload (bytes): The encoded embedding vector payload.
        expected_dimensions (int): The expected number of embedding dimensions.

    Returns:
        list[float]: The decoded embedding vector.

    Raises:
        ValueError: If the payload is truncated, has an unsupported format,
                    has mismatched dimensions, or contains non-finite values.
    """
    if len(payload) < _VECTOR_HEADER.size:
        raise ValueError("embedding payload is truncated")
    magic, version, dimensions = _VECTOR_HEADER.unpack_from(payload)
    if magic != _VECTOR_MAGIC or version != EMBEDDING_CACHE_SCHEMA_VERSION:
        raise ValueError("embedding payload has an unsupported format")
    if dimensions != expected_dimensions:
        raise ValueError("embedding dimensions do not match cache identity")
    expected_size = _VECTOR_HEADER.size + dimensions * 4
    if len(payload) != expected_size:
        raise ValueError("embedding payload length is invalid")
    values = list(struct.unpack_from(f"<{dimensions}f", payload, _VECTOR_HEADER.size))
    if not all(math.isfinite(value) for value in values):
        raise ValueError("cached embedding values must be finite")
    return values


def get_redis_client(redis_url: str) -> Any:
    """
    Return a lazy process-wide synchronous Redis client.
    Args:
        redis_url (str): The Redis connection URL.
    Returns:
        Any: A Redis client instance.
    """
    global _REDIS_CLIENT, _REDIS_CLIENT_URL
    with _REDIS_CLIENT_LOCK:
        if _REDIS_CLIENT is None or _REDIS_CLIENT_URL != redis_url:
            if _REDIS_CLIENT is not None:
                _REDIS_CLIENT.close()
            from redis import Redis

            _REDIS_CLIENT = Redis.from_url(
                redis_url,
                decode_responses=False,
                socket_connect_timeout=1.0,
                socket_timeout=1.0,
            )
            _REDIS_CLIENT_URL = redis_url
        return _REDIS_CLIENT


def close_redis_client() -> None:
    """
    Close and clear the lazy Redis client.
    Args: 
        None
    Returns: 
        None
    """
    global _REDIS_CLIENT, _REDIS_CLIENT_URL
    with _REDIS_CLIENT_LOCK:
        if _REDIS_CLIENT is not None:
            _REDIS_CLIENT.close()
        _REDIS_CLIENT = None
        _REDIS_CLIENT_URL = None


def new_embedding_cache_metrics(*, enabled: bool) -> dict[str, Any]:
    """
    Create JSON-safe mutable telemetry for one cache wrapper.
    """
    return {
        "enabled": enabled,
        "active": enabled,
        "backend": "redis" if enabled else None,
        "schema_version": EMBEDDING_CACHE_SCHEMA_VERSION,
        "hits": 0,
        "misses": 0,
        "writes": 0,
        "corrupt_entries": 0,
        "backend_errors": 0,
        "provider_vectors_requested": 0,
        "redis_elapsed_ms": 0.0,
        "provider_elapsed_ms": 0.0,
    }


class RedisCachedEmbeddings:
    """Cache a LangChain-style embedding model while preserving its interface."""

    def __init__(
        self,
        embeddings: Any,
        *,
        redis_client: Any,
        suite_content_hash: str,
        provider: str,
        model: str,
        dimensions: int,
        ttl_seconds: int,
        metrics: dict[str, Any] | None = None,
    ) -> None:
        if dimensions < 1:
            raise ValueError("embedding dimensions must be positive")
        if ttl_seconds < 1:
            raise ValueError("embedding cache TTL must be positive")
        self._embeddings = embeddings
        self._redis = redis_client
        self._suite_content_hash = suite_content_hash
        self._provider = provider
        self._model = model
        self._dimensions = dimensions
        self._ttl_seconds = ttl_seconds
        self.metrics = metrics or new_embedding_cache_metrics(enabled=True)

    def _key(self, operation: EmbeddingOperation, text: str) -> str:
        return build_embedding_cache_key(
            suite_content_hash=self._suite_content_hash,
            provider=self._provider,
            model=self._model,
            dimensions=self._dimensions,
            operation=operation,
            text=text,
        )

    def _disable_cache(self, exc: Exception) -> None:
        """
        Disable the cache for the current run due to an exception.
        Args:
            exc (Exception): The exception that caused the cache to be 
                disabled.
        Returns:
            None
        """
        if not self.metrics["active"]:
            return
        self.metrics["active"] = False
        self.metrics["backend_errors"] += 1
        logger.warning(
            "RAG-evaluation embedding cache disabled for this run: %s",
            type(exc).__name__,
        )

    def _provider_documents(self, texts: list[str]) -> list[list[float]]:
        """
        Get embedding vectors for a list of documents from the provider.

        Args:
            texts (list[str]): The list of document texts to embed.
        Returns:
            list[list[float]]: The list of embedding vectors.
        Raises:
            ValueError: If the provider returns vectors with unexpected 
            dimensions, or if the number of vectors does not match the 
            number of texts.
        """
        started = perf_counter()
        vectors = self._embeddings.embed_documents(texts)
        self.metrics["provider_elapsed_ms"] += round(
            (perf_counter() - started) * 1000,
            3,
        )
        self.metrics["provider_vectors_requested"] += len(texts)
        if len(vectors) != len(texts):
            raise ValueError("embedding provider returned an unexpected vector count")
        for vector in vectors:
            if len(vector) != self._dimensions:
                raise ValueError("embedding provider returned unexpected dimensions")
            # Encode-decode pair ensuring same-float32 representation as Redis payloads.
        return [
            decode_embedding_vector(
                encode_embedding_vector(vector),
                expected_dimensions=self._dimensions,
            )
            for vector in vectors
        ]

    def _provider_query(self, text: str) -> list[float]:
        """
        Get the embedding vector for a query from the provider.

        Args:
            text (str): The query text to embed.
        Returns:
            list[float]: The embedding vector.
        Raises:
            ValueError: If the embedding provider returns unexpected 
            dimensions.
        """
        started = perf_counter()
        vector = self._embeddings.embed_query(text)
        self.metrics["provider_elapsed_ms"] += round(
            (perf_counter() - started) * 1000,
            3,
        )
        self.metrics["provider_vectors_requested"] += 1
        if len(vector) != self._dimensions:
            raise ValueError("embedding provider returned unexpected dimensions")
        # Again the encode-decode pair pattern
        return decode_embedding_vector(
            encode_embedding_vector(vector),
            expected_dimensions=self._dimensions,
        )

    def _read(self, keys: list[str]) -> list[bytes | None] | None:
        """
        Read multiple embedding vectors from Redis in a single MGET operation.
        Args:
            keys (list[str]): The list of Redis keys to read.
        Returns:
            list[bytes | None] | None: The list of embedding vector payloads, 
                or None if the cache is disabled or an error occurred.
        """
        if not self.metrics["active"]:
            return None
        started = perf_counter()
        try:
            return self._redis.mget(keys)
        except Exception as exc:
            self._disable_cache(exc)
            return None
        finally:
            self.metrics["redis_elapsed_ms"] += round(
                (perf_counter() - started) * 1000,
                3,
            )

    def _write(self, entries: list[tuple[str, list[float]]]) -> None:
        """
        Write multiple embedding vectors to Redis in a single pipeline 
        operation.

        Args:
            entries (list[tuple[str, list[float]]]): The list of key-vector 
            pairs to write.
        """
        if not entries or not self.metrics["active"]:
            # Gracefully fail
            return
        started = perf_counter()
        try:
            pipeline = self._redis.pipeline(transaction=False)
            for key, vector in entries:
                pipeline.set(
                    key,
                    encode_embedding_vector(vector),
                    ex=self._ttl_seconds,
                )
            pipeline.execute()
            self.metrics["writes"] += len(entries)
        except Exception as exc:
            self._disable_cache(exc)
        finally:
            self.metrics["redis_elapsed_ms"] += round(
                (perf_counter() - started) * 1000,
                3,
            )

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """
        Embed documents using bulk Redis reads and deduplicated provider 
        misses.
        Args:
            texts (list[str]): The list of document texts to embed.
        Returns:
            list[list[float]]: The list of embedding vectors.
        Raises:
            ValueError: If the provider returns the wrong number of vectors.
            RuntimeError: If the cache fails to resolve all vectors.
        """
        if not texts:
            return []
        keys = [self._key("document", text) for text in texts]
        payloads = self._read(keys)
        if payloads is None:
            return self._provider_documents(texts)
        if len(payloads) != len(texts):
            self._disable_cache(ValueError("Redis MGET returned unexpected item count"))
            return self._provider_documents(texts)

        results: list[list[float] | None] = [None] * len(texts)
        missing_texts: list[str] = []
        missing_positions: dict[str, list[int]] = {}
        for index, (text, payload) in enumerate(zip(texts, payloads, strict=True)):
            if payload is not None:
                try:
                    results[index] = decode_embedding_vector(
                        payload,
                        expected_dimensions=self._dimensions,
                    )
                    self.metrics["hits"] += 1
                    continue
                except ValueError:
                    self.metrics["corrupt_entries"] += 1
            self.metrics["misses"] += 1
            if text not in missing_positions:
                missing_texts.append(text)
                missing_positions[text] = []
            missing_positions[text].append(index)

        if missing_texts:
            vectors = self._provider_documents(missing_texts)
            writes: list[tuple[str, list[float]]] = []
            for text, vector in zip(missing_texts, vectors, strict=True):
                for index in missing_positions[text]:
                    results[index] = vector
                writes.append((self._key("document", text), vector))
            self._write(writes)
        if any(result is None for result in results):
            raise RuntimeError("embedding cache failed to resolve all document vectors")
        return [result for result in results if result is not None]

    def embed_query(self, text: str) -> list[float]:
        """
        Embed one query in a key space separate from documents.

        Args:
            text (str): The query text to embed.
        Returns:
            list[float]: The embedding vector for the query.
        Raises:
            ValueError: If an issue occurs when decoding the vector
        """
        key = self._key("query", text)
        payloads = self._read([key])
        if payloads is not None and len(payloads) == 1 and payloads[0] is not None:
            try:
                vector = decode_embedding_vector(
                    payloads[0],
                    expected_dimensions=self._dimensions,
                )
                self.metrics["hits"] += 1
                return vector
            except ValueError:
                self.metrics["corrupt_entries"] += 1
        if payloads is not None:
            self.metrics["misses"] += 1
        vector = self._provider_query(text)
        self._write([(key, vector)])
        return vector

    def __getattr__(self, name: str) -> Any:
        """
        Override getattr to delegate attribute access to the underlying 
        embeddings object.
        Args:
            name (str): The attribute name to access.
        Returns:
            Any: The attribute value from the underlying embeddings object.
        """
        return getattr(self._embeddings, name)
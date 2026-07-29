"""Build persisted BM25 artifacts independently from dense corpus indexes."""

import asyncio
import pickle
import zlib
from collections.abc import Awaitable, Callable
from typing import TypeVar

from langchain_community.retrievers import BM25Retriever
from sqlmodel.ext.asyncio.session import AsyncSession

from app.repositories import corpus_bm25_indices_repo
from app.repositories.document_chunks_repo import list_corpus_document_chunks_for_profile
from app.schemas.corpus_bm25_indices_schemas import (
    CorpusBm25IndexCreate,
    CorpusBm25IndexMetadata,
)
from app.services.corpus_index_build_service import documents_from_persisted_chunks
from app.services.helpers import _persisted_id


BM25_ARTIFACT_FORMAT_VERSION = "pickle-zlib-v1"
_T = TypeVar("_T")


def _short_error(exc: BaseException, max_length: int = 500) -> str:
    message = str(exc).strip() or exc.__class__.__name__
    if len(message) <= max_length:
        return message
    return f"{message[: max_length - 3]}..."


def load_validated_bm25_artifact(
    artifact: bytes,
    *,
    expected_document_count: int,
) -> BM25Retriever:
    """Load trusted bytes and verify the persisted BM25 runtime shape."""
    try:
        retriever = pickle.loads(zlib.decompress(artifact))
    except (
        pickle.PickleError,
        AttributeError,
        EOFError,
        ImportError,
        IndexError,
        TypeError,
        ValueError,
        zlib.error,
    ) as exc:
        raise ValueError("BM25 artifact cannot be loaded") from exc

    if not isinstance(retriever, BM25Retriever):
        raise ValueError("BM25 artifact has an unexpected retriever type")
    if len(retriever.docs) != expected_document_count:
        raise ValueError("BM25 artifact document count does not match the chunk snapshot")
    if any(
        type(document.metadata.get("document_chunk_id")) is not int
        for document in retriever.docs
    ):
        raise ValueError("BM25 artifact documents require integer document_chunk_id metadata")
    return retriever


def _build_serialize_and_validate_bm25(documents) -> bytes:
    """Keep the Plan 4 serialization/load-validation boundary isolated here."""
    retriever = BM25Retriever.from_documents(documents=documents)
    artifact = zlib.compress(pickle.dumps(retriever, protocol=5))
    load_validated_bm25_artifact(
        artifact,
        expected_document_count=len(documents),
    )
    return artifact


async def _await_durable(operation: Awaitable[_T]) -> _T:
    """Let a database operation settle despite repeated task cancellation."""
    operation_task = asyncio.ensure_future(operation)
    cancellation: asyncio.CancelledError | None = None

    while not operation_task.done():
        try:
            result = await asyncio.shield(operation_task)
        except asyncio.CancelledError as exc:
            if cancellation is None:
                cancellation = exc
            continue
        except Exception:
            if cancellation is not None:
                raise cancellation
            raise
        else:
            if cancellation is not None:
                raise cancellation
            return result

    if cancellation is not None:
        try:
            operation_task.result()
        except BaseException:
            pass
        raise cancellation
    return operation_task.result()


async def _mark_build_failed(
    index_id: int,
    build_error: str,
    session: AsyncSession,
) -> None:
    await _await_durable(
        corpus_bm25_indices_repo.fail_corpus_bm25_index_build(
            index_id,
            build_error,
            session,
        )
    )


async def _mark_build_cancelled(
    index_id: int,
    build_error: str,
    session: AsyncSession,
) -> None:
    await _await_durable(
        corpus_bm25_indices_repo.cancel_corpus_bm25_index_build(
            index_id,
            build_error,
            session,
        )
    )


async def build_corpus_bm25_index_srvc(
    *,
    name: str,
    corpus_id: int,
    chunking_profile_id: int,
    session: AsyncSession,
    run_in_thread: Callable[..., Awaitable[bytes]] = asyncio.to_thread,
) -> CorpusBm25IndexMetadata:
    """Create, validate, and atomically persist one BM25 artifact snapshot."""
    chunks = await list_corpus_document_chunks_for_profile(
        corpus_id=corpus_id,
        chunking_profile_id=chunking_profile_id,
        session=session,
    )
    if not chunks:
        raise ValueError(
            "No document chunks found for this corpus and chunking profile. "
            "Chunk the corpus first."
        )

    document_chunk_ids = [
        _persisted_id(chunk.id, "Document chunk") for chunk in chunks
    ]
    documents = documents_from_persisted_chunks(
        chunks,
        corpus_id=corpus_id,
        chunking_profile_id=chunking_profile_id,
    )

    index_in = CorpusBm25IndexCreate(
        name=name,
        corpus_id=corpus_id,
        chunking_profile_id=chunking_profile_id,
        document_chunk_ids=document_chunk_ids,
        format_version=BM25_ARTIFACT_FORMAT_VERSION,
    )
    prepared_index = corpus_bm25_indices_repo.prepare_corpus_bm25_index(index_in)
    index_id: int | None = None

    async def create_index() -> None:
        nonlocal index_id
        # TODO: Reuse an existing compatible BM25 artifact instead of rebuilding one for every corpus index.
        index = await corpus_bm25_indices_repo.create_corpus_bm25_index(
            index_in,
            session,
            prepared_index=prepared_index,
        )
        index_id = _persisted_id(index.id, "Corpus BM25 index")

    def recover_index_id() -> int | None:
        nonlocal index_id
        if index_id is None and isinstance(prepared_index.id, int):
            index_id = prepared_index.id
        return index_id

    try:
        await _await_durable(create_index())
        await _await_durable(
            corpus_bm25_indices_repo.mark_corpus_bm25_index_building(
                index_id,
                session,
            )
        )
        artifact = await run_in_thread(_build_serialize_and_validate_bm25, documents)
        return await _await_durable(
            corpus_bm25_indices_repo.mark_corpus_bm25_index_built(
                index_id,
                artifact=artifact,
                document_chunk_ids=document_chunk_ids,
                session=session,
            )
        )
    except asyncio.CancelledError as exc:
        if recover_index_id() is None:
            raise
        try:
            await _mark_build_cancelled(index_id, _short_error(exc), session)
        except (asyncio.CancelledError, Exception):
            pass
        raise exc
    except Exception as exc:
        if recover_index_id() is not None:
            try:
                await _mark_build_failed(index_id, _short_error(exc), session)
            except asyncio.CancelledError:
                raise
            except Exception:
                pass
        raise

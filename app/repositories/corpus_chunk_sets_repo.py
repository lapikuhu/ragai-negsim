import hashlib
from collections.abc import Sequence

from sqlalchemy import delete
from sqlmodel import func, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.corpus_chunk_sets import (
    CorpusChunkSet,
    CorpusChunkSetDocumentChunkLink,
)
from app.models.document_chunks import DocumentChunk


def document_chunk_ids_checksum(document_chunk_ids: Sequence[int]) -> str:
    """
    Calculate the SHA-256 checksum of the given list of document chunk IDs.

    Args:
        document_chunk_ids: A sequence of document chunk IDs.
    Returns:
        str: The SHA-256 checksum of the sorted document chunk IDs.
    """
    canonical = ",".join(str(value) for value in sorted(document_chunk_ids))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


async def get_corpus_chunk_set_by_id(
    chunk_set_id: int,
    session: AsyncSession,
) -> CorpusChunkSet | None:
    """
    Retrieve a corpus chunk set by its ID.

    Args:
        chunk_set_id: The ID of the corpus chunk set.
    Returns:
        CorpusChunkSet | None: The corpus chunk set if found, otherwise None.
    """
    return await session.get(CorpusChunkSet, chunk_set_id)


async def get_corpus_chunk_set_by_name(
    corpus_id: int,
    name: str,
    session: AsyncSession,
) -> CorpusChunkSet | None:
    """
    Get a corpus chunk set by its name within a specific corpus.

    Args:
        corpus_id: The ID of the corpus.
        name: The name of the corpus chunk set.
    Returns:
        CorpusChunkSet | None: The corpus chunk set if found, otherwise None.
    """
    result = await session.exec(
        select(CorpusChunkSet).where(
            CorpusChunkSet.corpus_id == corpus_id,
            CorpusChunkSet.name == name,
        )
    )
    return result.first()


async def list_corpus_chunk_sets(
    corpus_id: int,
    session: AsyncSession,
) -> list[CorpusChunkSet]:
    """
    List all corpus chunk sets within a specific corpus.

    Args:
        corpus_id: The ID of the corpus.
    Returns:
        list[CorpusChunkSet]: A list of corpus chunk sets belonging to the 
        corpus.
    """
    result = await session.exec(
        select(CorpusChunkSet)
        .where(CorpusChunkSet.corpus_id == corpus_id)
        .order_by(CorpusChunkSet.name, CorpusChunkSet.id)
    )
    return list(result.all())


async def get_corpus_chunk_set_document_chunks(
    chunk_set_id: int,
    session: AsyncSession,
) -> list[DocumentChunk]:
    """
    List all document chunks associated with a specific corpus chunk set.

    Args:
        chunk_set_id: The ID of the corpus chunk set.
        session: The SQLAlchemy AsyncSession to use for the query.
    Returns:
        list[DocumentChunk]: A list of document chunks belonging to the 
        corpus chunk set.
    """
    result = await session.exec(
        select(DocumentChunk)
        .join(
            CorpusChunkSetDocumentChunkLink,
            CorpusChunkSetDocumentChunkLink.document_chunk_id == DocumentChunk.id,
        )
        .where(CorpusChunkSetDocumentChunkLink.corpus_chunk_set_id == chunk_set_id)
        .order_by(DocumentChunk.raw_document_id, DocumentChunk.chunk_index, DocumentChunk.id)
    )
    return list(result.all())


async def create_corpus_chunk_set(
    set_row: CorpusChunkSet,
    chunk_ids: Sequence[int],
    session: AsyncSession,
    *,
    commit: bool = True,
) -> CorpusChunkSet:
    """
    Create a new corpus chunk set and associate it with the given document 
    chunk IDs.

    Args:
        set_row: The CorpusChunkSet object to create.
        chunk_ids: A sequence of document chunk IDs to associate with the set.
        session: The SQLAlchemy AsyncSession to use for the query.
        commit: Whether to commit the transaction after creation.
    Returns:
        CorpusChunkSet: The created CorpusChunkSet object.
    """
    try:
        session.add(set_row)
        await session.flush()
        if set_row.id is None:
            raise ValueError("Corpus chunk set was not persisted")
        session.add_all(
            CorpusChunkSetDocumentChunkLink(
                corpus_chunk_set_id=set_row.id,
                document_chunk_id=chunk_id,
            )
            for chunk_id in chunk_ids
        )
        if commit:
            await session.commit()
        else:
            await session.flush()
        await session.refresh(set_row)
        return set_row
    except Exception:
        await session.rollback()
        raise


async def replace_corpus_chunk_set_members(
    chunk_set: CorpusChunkSet,
    chunk_ids: Sequence[int],
    session: AsyncSession,
) -> CorpusChunkSet:
    """
    Replace the members of a corpus chunk set with the given chunk IDs.

    Args:
        chunk_set: The corpus chunk set to update.
        chunk_ids: The new list of document chunk IDs to associate with the set.
        session: The SQLAlchemy AsyncSession to use for the query.
    Returns:
        The updated CorpusChunkSet object.
    """
    if chunk_set.id is None:
        raise ValueError("Corpus chunk set must be persisted")
    try:
        await session.exec(
            delete(CorpusChunkSetDocumentChunkLink).where(
                CorpusChunkSetDocumentChunkLink.corpus_chunk_set_id == chunk_set.id
            )
        )
        session.add_all(
            CorpusChunkSetDocumentChunkLink(
                corpus_chunk_set_id=chunk_set.id,
                document_chunk_id=chunk_id,
            )
            for chunk_id in chunk_ids
        )
        session.add(chunk_set)
        await session.commit()
        await session.refresh(chunk_set)
        return chunk_set
    except Exception:
        await session.rollback()
        raise


async def count_other_chunk_set_references(
    chunk_ids: Sequence[int],
    excluding_set_id: int,
    session: AsyncSession,
) -> dict[int, int]:
    """
    Count references to the given document chunk IDs in other corpus chunk 
    sets.

    Args:
        chunk_ids: A sequence of document chunk IDs to check.
        excluding_set_id: The ID of the corpus chunk set to exclude from the count.
        session: The SQLAlchemy AsyncSession to use for the query.
    Returns:
        A dictionary mapping each document chunk ID to the number of references
        in other corpus chunk sets.
    """
    if not chunk_ids:
        return {}
    result = await session.exec(
        select(
            CorpusChunkSetDocumentChunkLink.document_chunk_id,
            func.count(CorpusChunkSetDocumentChunkLink.corpus_chunk_set_id),
        )
        .where(
            CorpusChunkSetDocumentChunkLink.document_chunk_id.in_(chunk_ids),
            CorpusChunkSetDocumentChunkLink.corpus_chunk_set_id != excluding_set_id,
        )
        .group_by(CorpusChunkSetDocumentChunkLink.document_chunk_id)
    )
    return {chunk_id: count for chunk_id, count in result.all()}


async def corpus_chunk_set_has_index_references(
    chunk_set_id: int,
    session: AsyncSession,
) -> bool:
    """
    Check if a corpus chunk set has any references in corpus indices or 
    BM25 indices.
    
    Args:
        chunk_set_id: The ID of the corpus chunk set to check.
        session: The SQLAlchemy AsyncSession to use for the query.
    Returns:
        True if there are references in any indices, False otherwise.
    """
    from app.models.corpus_bm25_indices import CorpusBm25Index
    from app.models.corpus_indices import CorpusIndex

    for model in (CorpusIndex, CorpusBm25Index):
        field = getattr(model, "corpus_chunk_set_id", None)
        if field is None:
            continue
        result = await session.exec(select(model.id).where(field == chunk_set_id).limit(1))
        if result.first() is not None:
            return True
    return False


async def corpus_chunk_set_has_active_job_references(
    chunk_set_id: int,
    session: AsyncSession,
) -> bool:
    """
    Check if a corpus chunk set has any active job references.

    Args:
        chunk_set_id: The ID of the corpus chunk set to check.
        session: The SQLAlchemy AsyncSession to use for the query.

    Returns:
        True if there are active jobs referencing the corpus chunk set, False otherwise.
    """
    from app.models.corpus_bm25_build_jobs import CorpusBm25BuildJob
    from app.models.full_corpus_index_pipe_jobs import FullCorpusIndexPipeJob

    for model in (CorpusBm25BuildJob, FullCorpusIndexPipeJob):
        field = getattr(model, "corpus_chunk_set_id", None)
        if field is None:
            continue
        result = await session.exec(
            select(model.id)
            .where(field == chunk_set_id, model.status.in_(("queued", "running")))
            .limit(1)
        )
        if result.first() is not None:
            return True
    return False


async def delete_corpus_chunk_set(
    chunk_set: CorpusChunkSet,
    session: AsyncSession,
) -> None:
    """
    Delete a corpus chunk set and its associated document chunk links.

    Args:
        chunk_set: The corpus chunk set to delete.
        session: The SQLAlchemy AsyncSession to use for the operation.
    Raises:
        Exception: If the deletion fails, the transaction will be rolled 
        back and the exception will be raised.
    """
    try:
        await session.delete(chunk_set)
        await session.commit()
    except Exception:
        await session.rollback()
        raise

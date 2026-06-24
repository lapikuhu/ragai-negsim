from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.document_chunks import DocumentChunk
from app.repositories import document_chunks_repo
from app.schemas.document_chunks_schemas import DocumentChunkAdminRead, DocumentChunkListResponse


def _related_name(chunk: DocumentChunk, relation_name: str, field_name: str) -> str | None:
    """
    Get the value of a related field from a document chunk.
        Args:
            chunk: The DocumentChunk instance.
            relation_name: The name of the related attribute.
            field_name: The name of the field in the related attribute.
        Returns:
            The value of the related field if it exists and is a string, 
            otherwise None.
    """
    relation = getattr(chunk, relation_name, None)
    value = getattr(relation, field_name, None)
    return value if isinstance(value, str) else None


def _chunk_payload(chunk: DocumentChunk) -> dict:
    return {
        "id": chunk.id,
        "raw_document_id": chunk.raw_document_id,
        "chunking_profile_id": chunk.chunking_profile_id,
        "indexing_job_id": chunk.indexing_job_id,
        "chunk_index": chunk.chunk_index,
        "chunk_metadata": chunk.chunk_metadata,
        "created_at": chunk.created_at,
        "last_updated": chunk.last_updated,
    }


async def _to_document_chunk_admin_read(
    chunk: DocumentChunk,
    session: AsyncSession,
) -> DocumentChunkAdminRead:
    """
    Convert a DocumentChunk instance to a DocumentChunkAdminRead instance.
        Args:
            chunk: The DocumentChunk instance.
            session: The database session.
        Returns:
            A DocumentChunkAdminRead instance.
        Raises:
            ValueError: If the DocumentChunk instance has not been 
            persisted (i.e., its id is None).
    """
    if chunk.id is None:
        raise ValueError("Document chunk must be persisted before it can be listed")

    corpus_index_ids = await document_chunks_repo.get_document_chunk_corpus_index_ids(
        chunk.id,
        session,
    )
    return DocumentChunkAdminRead(
        **_chunk_payload(chunk),
        raw_document_name=_related_name(chunk, "raw_document", "name"),
        chunking_profile_name=_related_name(chunk, "chunking_profile", "name"),
        chunking_strategy=_related_name(chunk, "chunking_profile", "strategy"),
        corpus_index_ids=corpus_index_ids,
        indexed_count=len(corpus_index_ids),
        is_indexed=bool(corpus_index_ids),
    )


async def list_document_chunks_srvc(
    session: AsyncSession,
    skip: int = 0,
    limit: int = 20,
    raw_document_id: int | None = None,
    chunking_profile_id: int | None = None,
    has_indexed_chunks: bool | None = None,
) -> DocumentChunkListResponse:
    """
    List document chunks with optional filters and pagination.
        Args:
            session: The database session.
            skip: The number of records to skip.
            limit: The maximum number of records to return.
            raw_document_id: Optional filter by raw document ID.
            chunking_profile_id: Optional filter by chunking profile ID.
            has_indexed_chunks: Optional filter by whether the chunk has 
                indexed chunks.
        Returns:
            A list of DocumentChunkAdminRead instances.
    """
    chunks = await document_chunks_repo.list_document_chunks(
        session=session,
        skip=skip,
        limit=limit,
        raw_document_id=raw_document_id,
        chunking_profile_id=chunking_profile_id,
        has_indexed_chunks=has_indexed_chunks,
    )
    items = [
        await _to_document_chunk_admin_read(chunk, session)
        for chunk in chunks
    ]
    total = await document_chunks_repo.count_document_chunks(
        session=session,
        raw_document_id=raw_document_id,
        chunking_profile_id=chunking_profile_id,
        has_indexed_chunks=has_indexed_chunks,
    )
    return DocumentChunkListResponse(
        items=items,
        skip=skip,
        limit=limit,
        total=total,
        has_more=skip + limit < total,
    )

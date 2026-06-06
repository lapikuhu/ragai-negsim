from typing import Protocol

from app.models.chunking_profiles import ChunkingProfile
from app.models.corpus import Corpus
from app.models.raw_documents import RawDocument
from app.repositories import corpus_repo, raw_documents_repo
from app.repositories.document_chunks_repo import (
    bulk_create_document_chunks,
    list_document_chunks,
)
from app.schemas.chunking_schemas import (
    ChunkPreview,
    CorpusChunkResult,
    RawDocumentChunkResult,
)
from app.schemas.document_chunks_schemas import DocumentChunkCreate
from app.services.helpers import _persisted_id
from app.services.raw_documents_service import (
    RAW_DOCUMENT_SOURCE_STATUS_AVAILABLE,
    verify_raw_document_source_srvc,
)
from langchain_core.documents import Document
from sqlmodel.ext.asyncio.session import AsyncSession


class ChunkingOptionsLike(Protocol):
    chunker: str
    chunk_size: int
    chunk_overlap: int
    separators: list[str] | None
    breakpoint_threshold_type: str
    breakpoint_threshold_amount: int
    buffer_size: int
    preview: bool


def _load_parsed_document(raw_document: RawDocument) -> Document:
    """
    Load the parsed content of a raw document and return a Document object.
    Args:
        raw_document (RawDocument): The raw document whose parsed content
            is to be loaded.
    Returns:
        Document: A Document object containing the parsed content and
            associated metadata.
    Raises:
        ValueError: If the raw document has no parsed content or if the
            parsed content is empty
    """
    content = raw_document.parsed_content
    if content is None:
        raise ValueError("Raw document has no parsed content. Ingest and parse it before chunking.")

    if not content.strip():
        raise ValueError("Raw document parsed content is empty")

    return Document(
        page_content=content,
        metadata={
            "source": raw_document.source_path,
            "raw_document_id": raw_document.id,
        },
    )


def _chunk_documents(documents: list[Document], options: ChunkingOptionsLike) -> list[Document]:
    """
    Chunk a list of documents based on the provided chunking options.
    Args:
        documents (list[Document]): The list of documents to be chunked.
        options (ChunkingOptionsLike): The chunking options to use.
    Returns:
        list[Document]: The list of chunked documents.
    Raises:
        ValueError: If the chunker type is unsupported.
    """
    if options.chunker == "recursive":
        from app.airag.chunking.chunkers import chunk_document_list_recursive

        return chunk_document_list_recursive(
            documents,
            chunk_size=options.chunk_size,
            chunk_overlap=options.chunk_overlap,
            separators=options.separators,
        )

    if options.chunker == "semantic":
        from app.airag.chunking.chunkers import chunk_document_list_semantic

        return chunk_document_list_semantic(
            documents,
            breakpoint_threshold_type=options.breakpoint_threshold_type,
            breakpoint_threshold_amount=options.breakpoint_threshold_amount,
            buffer_size=options.buffer_size,
        )

    raise ValueError("Unsupported chunker")


def _to_chunk_inputs(
    chunks: list[Document],
    raw_document_id: int,
    chunking_profile_id: int,
    source: str,
) -> list[DocumentChunkCreate]:
    """
    Convert a list of chunked documents into a list of DocumentChunkCreate objects.
    Args:
        chunks (list[Document]): The list of chunked documents.
        raw_document_id (int): The ID of the raw document.
        chunking_profile_id (int): The ID of the chunking profile.
        source (str): The source of the raw document.
    Returns:
        list[DocumentChunkCreate]: The list of DocumentChunkCreate objects.
    """
    chunks_in = []
    for chunk_index, chunk in enumerate(chunks):
        chunk_metadata = dict(chunk.metadata)
        chunk_metadata.update(
            {
                "source": source,
                "raw_document_id": raw_document_id,
                "chunking_profile_id": chunking_profile_id,
            }
        )
        chunks_in.append(
            DocumentChunkCreate(
                raw_document_id=raw_document_id,
                chunking_profile_id=chunking_profile_id,
                chunk_index=chunk_index,
                content=chunk.page_content,
                chunk_metadata=chunk_metadata,
            )
        )
    return chunks_in


def _to_previews(chunks_in: list[DocumentChunkCreate]) -> list[ChunkPreview]:
    """
    Convert a list of DocumentChunkCreate objects into a list of
    ChunkPreview objects.
    Args:
        chunks_in (list[DocumentChunkCreate]): The list of
            DocumentChunkCreate objects.
    Returns:
        list[ChunkPreview]: The list of ChunkPreview objects.
    """
    return [
        ChunkPreview(
            chunk_index=chunk.chunk_index,
            content=chunk.content,
            chunk_metadata=chunk.chunk_metadata,
        )
        for chunk in chunks_in
    ]


async def chunk_raw_document_srvc(
    raw_document: RawDocument,
    chunking_profile: ChunkingProfile,
    session: AsyncSession,
    options: ChunkingOptionsLike,
) -> RawDocumentChunkResult:
    """
    Chunk a raw document based on the provided chunking options.
    Args:
        raw_document (RawDocument): The raw document to be chunked.
        chunking_profile (ChunkingProfile): The chunking profile to use.
        session (AsyncSession): The database session.
        options (ChunkingOptionsLike): The chunking options to use.
    Returns:
        RawDocumentChunkResult: The result of the chunking operation.
    Raises:
        ValueError: If the raw document or chunking profile is not found.
    """
    raw_document_id = _persisted_id(raw_document.id, "Raw document")
    chunking_profile_id = _persisted_id(chunking_profile.id, "Chunking profile")
    raw_document = await verify_raw_document_source_srvc(raw_document, session)
    if raw_document.source_status != RAW_DOCUMENT_SOURCE_STATUS_AVAILABLE:
        raise ValueError(
            f"Raw document source is {raw_document.source_status}. Restore or re-upload the stored file before chunking."
        )

    existing_chunks = await list_document_chunks(
        session=session,
        raw_document_id=raw_document_id,
        chunking_profile_id=chunking_profile_id,
        limit=1,
    )
    if existing_chunks and not options.preview:
        raise ValueError(
            "Document chunks already exist for this raw document and chunking profile. "
            "Create a new chunking profile to re-chunk."
        )

    parsed_document = _load_parsed_document(raw_document)
    chunked_documents = _chunk_documents([parsed_document], options)
    chunks_in = _to_chunk_inputs(
        chunked_documents,
        raw_document_id=raw_document_id,
        chunking_profile_id=chunking_profile_id,
        source=raw_document.source_path,
    )

    if options.preview:
        return RawDocumentChunkResult(
            raw_document_id=raw_document_id,
            chunking_profile_id=chunking_profile_id,
            chunker=options.chunker,
            preview=True,
            chunks_created=len(chunks_in),
            chunks=_to_previews(chunks_in),
        )

    created_chunks = await bulk_create_document_chunks(chunks_in, session)
    chunk_ids = [chunk.id for chunk in created_chunks if chunk.id is not None]
    return RawDocumentChunkResult(
        raw_document_id=raw_document_id,
        chunking_profile_id=chunking_profile_id,
        chunker=options.chunker,
        chunks_created=len(created_chunks),
        chunk_ids=chunk_ids,
    )


async def chunk_corpus_srvc(
    corpus: Corpus,
    chunking_profile: ChunkingProfile,
    session: AsyncSession,
    options: ChunkingOptionsLike,
) -> CorpusChunkResult:
    """
    Chunk a corpus based on the provided chunking options.
    Args:
        corpus (Corpus): The corpus to be chunked.
        chunking_profile (ChunkingProfile): The chunking profile to use.
        session (AsyncSession): The database session.
        options (ChunkingOptionsLike): The chunking options to use.
    Returns:
        CorpusChunkResult: The result of the chunking operation.
    Raises:
        ValueError: If the corpus or chunking profile is not found.
    """
    corpus_id = _persisted_id(corpus.id, "Corpus")
    chunking_profile_id = _persisted_id(chunking_profile.id, "Chunking profile")
    raw_document_ids = await corpus_repo.get_corpus_raw_document_ids(corpus_id, session)

    raw_document_results = []
    for raw_document_id in raw_document_ids:
        raw_document = await raw_documents_repo.get_raw_document_by_id(raw_document_id, session)
        if raw_document is None:
            raise ValueError(f"Raw document {raw_document_id} linked to corpus was not found")

        raw_document_results.append(
            await chunk_raw_document_srvc(
                raw_document=raw_document,
                chunking_profile=chunking_profile,
                session=session,
                options=options,
            )
        )

    return CorpusChunkResult(
        corpus_id=corpus_id,
        chunking_profile_id=chunking_profile_id,
        chunker=options.chunker,
        preview=options.preview,
        raw_documents=raw_document_results,
        chunks_created=sum(result.chunks_created for result in raw_document_results),
    )

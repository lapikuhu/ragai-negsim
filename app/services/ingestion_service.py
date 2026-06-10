from pathlib import Path
from typing import TYPE_CHECKING, Protocol

from app.services.helpers import _persisted_id
from app.services.chunking_profile_runtime import resolve_ingestion_profile_options
from app.models.chunking_profiles import ChunkingProfile
from app.models.corpus import Corpus
from app.models.raw_documents import RawDocument
from app.repositories import corpus_repo, raw_documents_repo
from app.repositories.document_chunks_repo import bulk_create_document_chunks
from app.schemas.document_chunks_schemas import DocumentChunkCreate
from app.schemas.ingestion_schemas import CorpusIngestResult, RawDocumentIngestResult
from app.services.raw_documents_service import (
    RAW_DOCUMENT_SOURCE_STATUS_AVAILABLE,
    verify_raw_document_source_srvc,
)
from sqlmodel.ext.asyncio.session import AsyncSession

if TYPE_CHECKING:
    from langchain_core.embeddings import Embeddings


class IngestionExecutionOptionsLike(Protocol):
    header_depth: int
    dynamic_header_depth: bool


class ResolvedIngestionOptionsLike(Protocol):
    header_depth: int
    dynamic_header_depth: bool
    chunk_size: int
    chunk_overlap: int
    separators: list[str] | None
    breakpoint_threshold_type: str
    breakpoint_threshold_amount: int
    buffer_size: int
    chunker: str


def _parse_raw_document(
    path: str,
    options: ResolvedIngestionOptionsLike,
    embeddings: "Embeddings | None" = None,
) -> tuple[str, list]:
    """
    Processes the raw document at the given path using the specified options. 
    Currently supports PDF documents with recursive, semantic, or hybrid chunking.
    Args:
        path (str): The file path to the raw document to be ingested.
        options (IngestionOptionsLike): An object containing ingestion 
            options such as header depth, chunk size, and chunker type.
    Returns:
        List[DocumentChunkCreate]: A list of DocumentChunkCreate objects 
        representing the parsed chunks of the document.
    """
    from app.airag.chunking.chunkers import (
        chunk_document_list_hybrid,
        chunk_document_list_recursive,
        chunk_document_list_semantic,
    )
    from app.airag.ingestion.ingestion import clean_markdown, split_md_on_headers
    from app.airag.ingestion.loaders import convert_to_markdown, ingest_single_pdf

    raw_document_path = Path(path)
    if raw_document_path.suffix.lower() != ".pdf":
        raise ValueError("Only PDF raw document ingestion is currently supported")

    if options.chunker == "semantic" and embeddings is None:
        raise ValueError("Semantic chunking requires an embedding model")
    if options.chunker == "hybrid" and embeddings is None:
        raise ValueError("Hybrid chunking requires an embedding model")

    docling_document = ingest_single_pdf(raw_document_path)
    markdown = convert_to_markdown(docling_document)
    cleaned_markdown = clean_markdown(
        markdown,
        convert_to_langDoc=False,
        source=str(raw_document_path),
    )
    cleaned_document = clean_markdown(
        markdown,
        convert_to_langDoc=True,
        source=str(raw_document_path),
    )
    sections = split_md_on_headers(
        cleaned_document,
        header_depth=options.header_depth,
        dynamic_length=options.dynamic_header_depth,
    )
    if options.chunker == "recursive":
        chunks = chunk_document_list_recursive(
            sections,
            chunk_size=options.chunk_size,
            chunk_overlap=options.chunk_overlap,
            separators=options.separators,
        )
    elif options.chunker == "semantic":
        chunks = chunk_document_list_semantic(
            sections,
            embeddings=embeddings,
            breakpoint_threshold_type=options.breakpoint_threshold_type,
            breakpoint_threshold_amount=options.breakpoint_threshold_amount,
            buffer_size=options.buffer_size,
        )
    elif options.chunker == "hybrid":
        chunks = chunk_document_list_hybrid(
            sections,
            embeddings=embeddings,
            breakpoint_threshold_type=options.breakpoint_threshold_type,
            breakpoint_threshold_amount=options.breakpoint_threshold_amount,
            buffer_size=options.buffer_size,
            chunk_size=options.chunk_size,
            chunk_overlap=options.chunk_overlap,
            separators=options.separators,
        )
    else:
        raise ValueError(f"Unsupported chunking strategy: {options.chunker}")

    return (cleaned_markdown, chunks)


async def ingest_raw_document_srvc(
    raw_document: RawDocument,
    chunking_profile: ChunkingProfile,
    session: AsyncSession,
    options: IngestionExecutionOptionsLike,
    indexing_job_id: int | None = None,
    embeddings: "Embeddings | None" = None,
) -> RawDocumentIngestResult:
    """
    Ingests a raw document using the specified chunking profile and ingestion 
    options.
    Args:
        raw_document (RawDocument): The raw document to be ingested.
        chunking_profile (ChunkingProfile): The chunking profile to use for 
            ingestion.
        session (AsyncSession): The database session to use for persistence.
        options (IngestionOptionsLike): An object containing ingestion 
            options such as header depth, chunk size, and chunker type.
    Returns:
        RawDocumentIngestResult: The result of the ingestion, including the 
        IDs of the created chunks.
    """
    raw_document_id = _persisted_id(raw_document.id, "Raw document")
    chunking_profile_id = _persisted_id(chunking_profile.id, "Chunking profile")
    resolved_options = resolve_ingestion_profile_options(
        chunking_profile,
        header_depth=options.header_depth,
        dynamic_header_depth=options.dynamic_header_depth,
    )

    raw_document = await verify_raw_document_source_srvc(raw_document, session)
    if raw_document.source_status != RAW_DOCUMENT_SOURCE_STATUS_AVAILABLE:
        raise ValueError(
            f"Raw document source is {raw_document.source_status}. Restore or re-upload the stored file before ingesting."
        )

    if embeddings is None:
        parsed_content, parsed_chunks = _parse_raw_document(
            raw_document.source_path,
            resolved_options,
        )
    else:
        parsed_content, parsed_chunks = _parse_raw_document(
            raw_document.source_path,
            resolved_options,
            embeddings=embeddings,
        )
    await raw_documents_repo.update_raw_document_parsed_content(
        raw_document=raw_document,
        parsed_content=parsed_content,
        session=session,
    )
    chunks_in = []
    for chunk_index, chunk in enumerate(parsed_chunks):
        chunk_metadata = dict(chunk.metadata)
        chunk_metadata.update(
            {
                "source": raw_document.source_path,
                "raw_document_id": raw_document_id,
                "chunking_profile_id": chunking_profile_id,
            }
        )
        chunks_in.append(
            DocumentChunkCreate(
                raw_document_id=raw_document_id,
                chunking_profile_id=chunking_profile_id,
                indexing_job_id=indexing_job_id,
                chunk_index=chunk_index,
                content=chunk.page_content,
                chunk_metadata=chunk_metadata,
            )
        )

    created_chunks = await bulk_create_document_chunks(chunks_in, session)
    chunk_ids = [chunk.id for chunk in created_chunks if chunk.id is not None]
    return RawDocumentIngestResult(
        raw_document_id=raw_document_id,
        chunking_profile_id=chunking_profile_id,
        chunks_created=len(created_chunks),
        chunk_ids=chunk_ids,
    )


async def ingest_corpus_srvc(
    corpus: Corpus,
    chunking_profile: ChunkingProfile,
    session: AsyncSession,
    options: IngestionExecutionOptionsLike,
    embeddings: "Embeddings | None" = None,
) -> CorpusIngestResult:
    """
    Ingests a corpus by processing all its associated raw documents using the
    specified chunking profile and ingestion options.
    Args:
        corpus (Corpus): The corpus to be ingested.
        chunking_profile (ChunkingProfile): The chunking profile to use 
            for ingestion.
        session (AsyncSession): The database session to use for persistence.
        options (IngestionOptionsLike): An object containing ingestion 
            options such as header depth, chunk size, and chunker type.
    Returns:
        CorpusIngestResult: The result of the ingestion, including the 
        IDs of the created chunks.
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
            await ingest_raw_document_srvc(
                raw_document=raw_document,
                chunking_profile=chunking_profile,
                session=session,
                options=options,
                embeddings=embeddings,
            )
            if embeddings is not None
            else await ingest_raw_document_srvc(
                raw_document=raw_document,
                chunking_profile=chunking_profile,
                session=session,
                options=options,
            )
        )

    return CorpusIngestResult(
        corpus_id=corpus_id,
        chunking_profile_id=chunking_profile_id,
        raw_documents=raw_document_results,
        chunks_created=sum(result.chunks_created for result in raw_document_results),
    )

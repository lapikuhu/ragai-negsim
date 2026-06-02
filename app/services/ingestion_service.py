from pathlib import Path
from typing import Protocol

from models.chunking_profiles import ChunkingProfile
from models.corpus import Corpus
from models.raw_documents import RawDocument
from repositories import corpus_repo, raw_documents_repo
from repositories.document_chunks_repo import bulk_create_document_chunks
from schemas.document_chunks_schemas import DocumentChunkCreate
from schemas.ingestion_schemas import CorpusIngestResult, RawDocumentIngestResult
from sqlmodel.ext.asyncio.session import AsyncSession


class IngestionOptionsLike(Protocol):
    header_depth: int
    dynamic_header_depth: bool
    chunk_size: int
    chunk_overlap: int
    chunker: str


def _persisted_id(value: int | None, label: str) -> int:
    if value is None:
        raise ValueError(f"{label} must be persisted before ingestion")
    return value


def _parse_raw_document(path: str, options: IngestionOptionsLike):
    from airag.chunking.chunkers import chunk_document_list_recursive
    from airag.ingestion.ingestion import clean_markdown, split_md_on_headers
    from airag.ingestion.loaders import convert_to_markdown, ingest_single_pdf

    raw_document_path = Path(path)
    if raw_document_path.suffix.lower() != ".pdf":
        raise ValueError("Only PDF raw document ingestion is currently supported")

    if options.chunker != "recursive":
        raise ValueError("Only recursive chunking is currently supported by this ingestion service")

    docling_document = ingest_single_pdf(raw_document_path)
    markdown = convert_to_markdown(docling_document)
    cleaned_document = clean_markdown(markdown, source=str(raw_document_path))
    sections = split_md_on_headers(
        cleaned_document,
        header_depth=options.header_depth,
        dynamic_length=options.dynamic_header_depth,
    )
    return chunk_document_list_recursive(
        sections,
        chunk_size=options.chunk_size,
        chunk_overlap=options.chunk_overlap,
    )


async def ingest_raw_document_srvc(
    raw_document: RawDocument,
    chunking_profile: ChunkingProfile,
    session: AsyncSession,
    options: IngestionOptionsLike,
) -> RawDocumentIngestResult:
    raw_document_id = _persisted_id(raw_document.id, "Raw document")
    chunking_profile_id = _persisted_id(chunking_profile.id, "Chunking profile")

    parsed_chunks = _parse_raw_document(raw_document.path, options)
    chunks_in = []
    for chunk_index, chunk in enumerate(parsed_chunks):
        chunk_metadata = dict(chunk.metadata)
        chunk_metadata.update(
            {
                "source": raw_document.path,
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
    options: IngestionOptionsLike,
) -> CorpusIngestResult:
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
            )
        )

    return CorpusIngestResult(
        corpus_id=corpus_id,
        chunking_profile_id=chunking_profile_id,
        raw_documents=raw_document_results,
        chunks_created=sum(result.chunks_created for result in raw_document_results),
    )

from typing import Protocol

from langchain_core.documents import Document
from models.chunking_profiles import ChunkingProfile
from models.corpus import Corpus
from models.raw_documents import RawDocument
from repositories import corpus_repo, raw_documents_repo
from repositories.document_chunks_repo import (
    bulk_create_document_chunks,
    list_document_chunks,
)
from schemas.chunking_schemas import (
    ChunkPreview,
    CorpusChunkResult,
    RawDocumentChunkResult,
)
from schemas.document_chunks_schemas import DocumentChunkCreate
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


def _persisted_id(value: int | None, label: str) -> int:
    if value is None:
        raise ValueError(f"{label} must be persisted before chunking")
    return value


def _load_parsed_document(raw_document: RawDocument) -> Document:
    content = raw_document.parsed_content
    if content is None:
        raise ValueError("Raw document has no parsed content. Ingest and parse it before chunking.")

    if not content.strip():
        raise ValueError("Raw document parsed content is empty")

    return Document(
        page_content=content,
        metadata={
            "source": raw_document.path,
            "raw_document_id": raw_document.id,
        },
    )


def _chunk_documents(documents: list[Document], options: ChunkingOptionsLike) -> list[Document]:
    if options.chunker == "recursive":
        from airag.chunking.chunkers import chunk_document_list_recursive

        return chunk_document_list_recursive(
            documents,
            chunk_size=options.chunk_size,
            chunk_overlap=options.chunk_overlap,
            separators=options.separators,
        )

    if options.chunker == "semantic":
        from airag.chunking.chunkers import chunk_document_list_semantic

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
    raw_document_id = _persisted_id(raw_document.id, "Raw document")
    chunking_profile_id = _persisted_id(chunking_profile.id, "Chunking profile")

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
        source=raw_document.path,
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

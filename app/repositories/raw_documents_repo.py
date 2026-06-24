from datetime import datetime, timezone

from app.models.document_chunks import DocumentChunk
from app.models.raw_documents import CorpusRawDocumentLink, RawDocument
from app.repositories.helpers import commit_and_refresh
from app.schemas.raw_documents_schemas import (
    CorpusRawDocumentLinkCreate,
    CorpusRawDocumentLinkDelete,
    RawDocumentCreateDb,
    RawDocumentUpdate,
)
from sqlalchemy.orm import selectinload
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession


async def get_raw_document_by_id(
    raw_document_id: int,
    session: AsyncSession,
) -> RawDocument | None:
    """
    Get a raw document by its ID.
        Args:
            raw_document_id: The ID of the raw document.
            session: The database session.
        Returns:
            The RawDocument instance if found, else None.
    """
    result = await session.exec(
        select(RawDocument)
        .options(selectinload(RawDocument.uploaded_by))
        .where(RawDocument.id == raw_document_id)
    )
    return result.first()


async def get_raw_document_by_source_path(
    source_path: str,
    session: AsyncSession,
) -> RawDocument | None:
    """
    Get a raw document by its canonical source path.
        Args:
            source_path: The source path of the raw document.
            session: The database session.
        Returns:
            The RawDocument instance if found, else None.
    """
    result = await session.exec(select(RawDocument).where(RawDocument.source_path == source_path))
    return result.first()


async def get_raw_document_by_name(
    name: str,
    session: AsyncSession,
) -> RawDocument | None:
    """
    Get a raw document by its name.
        Args:
            name: The name of the raw document.
            session: The database session.
        Returns:
            The RawDocument instance if found, else None.
    """
    result = await session.exec(select(RawDocument).where(RawDocument.name == name))
    return result.first()


async def list_raw_documents(
    session: AsyncSession,
    skip: int = 0,
    limit: int = 10,
    uploaded_by_user_id: int | None = None,
    corpus_id: int | None = None,
    name_contains: str | None = None,
) -> list[RawDocument]:
    """
    List raw documents with optional filters.
        Args:
            session: The database session.
            skip: The number of records to skip.
            limit: The maximum number of records to return.
            uploaded_by_user_id: Filter by the ID of the user who uploaded
                the document.
            corpus_id: Filter by the ID of the corpus.
            name_contains: Filter by a substring in the document name.
        Returns:
            A list of RawDocument instances.
    """
    statement = select(RawDocument).options(selectinload(RawDocument.uploaded_by))

    if corpus_id is not None:
        statement = statement.join(
            CorpusRawDocumentLink,
            RawDocument.id == CorpusRawDocumentLink.raw_document_id,
        ).where(CorpusRawDocumentLink.corpus_id == corpus_id)
    if uploaded_by_user_id is not None:
        statement = statement.where(RawDocument.uploaded_by_user_id == uploaded_by_user_id)
    if name_contains is not None:
        statement = statement.where(RawDocument.name.contains(name_contains))

    statement = statement.offset(skip).limit(limit)
    result = await session.exec(statement)
    return list(result.all())


async def get_raw_document_corpus_ids(
    raw_document_id: int,
    session: AsyncSession,
) -> list[int]:
    """
    Get the IDs of corpora associated with a raw document.
        Args:
            raw_document_id: The ID of the raw document.
            session: The database session.
        Returns:
            A list of corpus IDs.
    """
    result = await session.exec(
        select(CorpusRawDocumentLink.corpus_id).where(
            CorpusRawDocumentLink.raw_document_id == raw_document_id
        )
    )
    return [corpus_id for corpus_id in result.all() if corpus_id is not None]


async def get_raw_document_document_chunk_ids(
    raw_document_id: int,
    session: AsyncSession,
) -> list[int]:
    """
    Get the IDs of document chunks associated with a raw document.
        Args:
            raw_document_id: The ID of the raw document.
            session: The database session.
        Returns:
            A list of document chunk IDs.
    """
    result = await session.exec(
        select(DocumentChunk.id).where(DocumentChunk.raw_document_id == raw_document_id)
    )
    return [chunk_id for chunk_id in result.all() if chunk_id is not None]


async def create_raw_document(
    raw_document_in: RawDocumentCreateDb,
    session: AsyncSession,
) -> RawDocument:
    """
    Create a new raw document.
        Args:
            raw_document_in: The RawDocumentCreate instance containing raw
                document data.
            session: The database session.
        Returns:
            The created RawDocument instance.
        Raises:
            Exception: If an error occurs during creation.
    """
    raw_document_data = raw_document_in.model_dump(exclude={"corpus_ids"})
    raw_document = RawDocument(**raw_document_data)

    try:
        session.add(raw_document)
        await session.flush()

        for corpus_id in dict.fromkeys(raw_document_in.corpus_ids):
            session.add(
                CorpusRawDocumentLink(
                    corpus_id=corpus_id,
                    raw_document_id=raw_document.id,
                )
            )

        await session.commit()
        await session.refresh(raw_document)
        return raw_document
    except Exception:
        await session.rollback()
        raise


async def update_raw_document(
    raw_document: RawDocument,
    raw_document_in: RawDocumentUpdate,
    session: AsyncSession,
) -> RawDocument:
    """
    Update an existing raw document.
        Args:
            raw_document: The RawDocument instance to update.
            raw_document_in: The RawDocumentUpdate instance containing updated data.
            session: The database session.
        Returns:
            The updated RawDocument instance.
        Raises:
            Exception: If an error occurs during the update.
    """
    update_data = raw_document_in.model_dump(exclude_unset=True)

    for field_name, value in update_data.items():
        setattr(raw_document, field_name, value)

    return await commit_and_refresh(session, raw_document)


async def update_raw_document_parsed_content(
    raw_document: RawDocument,
    parsed_content: str,
    session: AsyncSession,
) -> RawDocument:
    """
    Store parsed markdown/text content for a raw document.
        Args:
            raw_document: The RawDocument instance to update.
            parsed_content: Parsed markdown/text extracted from the source document.
            session: The database session.
        Returns:
            The updated RawDocument instance.
    """
    raw_document.parsed_content = parsed_content
    raw_document.parsed_at = datetime.now(timezone.utc)
    return await commit_and_refresh(session, raw_document)


async def get_corpus_raw_document_link(
    corpus_id: int,
    raw_document_id: int,
    session: AsyncSession,
) -> CorpusRawDocumentLink | None:
    """
    Get the link between a corpus and a raw document.
        Args:
            corpus_id: The ID of the corpus.
            raw_document_id: The ID of the raw document.
            session: The database session.
        Returns:
            The CorpusRawDocumentLink instance if it exists, otherwise None.
    """
    result = await session.exec(
        select(CorpusRawDocumentLink).where(
            CorpusRawDocumentLink.corpus_id == corpus_id,
            CorpusRawDocumentLink.raw_document_id == raw_document_id,
        )
    )
    return result.first()


async def link_raw_document_to_corpus(
    link_in: CorpusRawDocumentLinkCreate,
    session: AsyncSession,
) -> CorpusRawDocumentLink:
    """
    Link a raw document to a corpus.
        Args:
            link_in: The CorpusRawDocumentLinkCreate instance containing link data.
            session: The database session.
        Returns:
            The CorpusRawDocumentLink instance.
        Raises:
            Exception: If an error occurs during the linking process.
    """
    existing_link = await get_corpus_raw_document_link(
        link_in.corpus_id,
        link_in.raw_document_id,
        session,
    )
    if existing_link is not None:
        return existing_link

    link = CorpusRawDocumentLink(
        corpus_id=link_in.corpus_id,
        raw_document_id=link_in.raw_document_id,
    )

    try:
        session.add(link)
        await session.commit()
        await session.refresh(link)
        return link
    except Exception:
        await session.rollback()
        raise


async def unlink_raw_document_from_corpus(
    link_in: CorpusRawDocumentLinkDelete,
    session: AsyncSession,
) -> None:
    """
    Unlink a raw document from a corpus.
        Args:
            link_in: The CorpusRawDocumentLinkDelete instance containing link
                data.
            session: The database session.
        Raises:
            Exception: If an error occurs during the unlinking process.
    """
    link = await get_corpus_raw_document_link(
        link_in.corpus_id,
        link_in.raw_document_id,
        session,
    )
    if link is None:
        return

    try:
        await session.delete(link)
        await session.commit()
    except Exception:
        await session.rollback()
        raise


async def replace_raw_document_corpus_links(
    raw_document: RawDocument,
    corpus_ids: list[int],
    session: AsyncSession,
) -> RawDocument:
    """
    Replace the links between a raw document and corpora.
        Args:
            raw_document: The RawDocument instance.
            corpus_ids: A list of corpus IDs to link to the raw document.
            session: The database session.
        Returns:
            The updated RawDocument instance.
        Raises:
            Exception: If an error occurs during the replacement process.
    """
    try:
        existing_links_result = await session.exec(
            select(CorpusRawDocumentLink).where(
                CorpusRawDocumentLink.raw_document_id == raw_document.id
            )
        )
        for link in existing_links_result.all():
            await session.delete(link)

        for corpus_id in dict.fromkeys(corpus_ids):
            session.add(
                CorpusRawDocumentLink(
                    corpus_id=corpus_id,
                    raw_document_id=raw_document.id,
                )
            )

        await session.commit()
        await session.refresh(raw_document)
        return raw_document
    except Exception:
        await session.rollback()
        raise


async def raw_document_has_chunks(
    raw_document_id: int,
    session: AsyncSession,
) -> bool:
    """
    Check if a raw document has any associated chunks.
        Args:
            raw_document_id: The ID of the raw document.
            session: The database session.
        Returns:
            True if the raw document has chunks, False otherwise.
    """
    result = await session.exec(
        select(DocumentChunk.id).where(DocumentChunk.raw_document_id == raw_document_id).limit(1)
    )
    return result.first() is not None


async def delete_raw_document(
    raw_document: RawDocument,
    session: AsyncSession,
) -> None:
    """
    Delete a raw document from the database.
        Args:
            raw_document: The RawDocument instance to be deleted.
            session: The database session.
        Raises:
            ValueError: If the raw document is not persisted or has existing chunks.
            Exception: If an error occurs during the deletion process.
    """
    if raw_document.id is None:
        raise ValueError("Raw document must be persisted before it can be deleted")

    if await raw_document_has_chunks(raw_document.id, session):
        raise ValueError("Cannot delete raw document with existing chunks")

    try:
        existing_links_result = await session.exec(
            select(CorpusRawDocumentLink).where(
                CorpusRawDocumentLink.raw_document_id == raw_document.id
            )
        )
        for link in existing_links_result.all():
            await session.delete(link)

        await session.delete(raw_document)
        await session.commit()
    except Exception:
        await session.rollback()
        raise

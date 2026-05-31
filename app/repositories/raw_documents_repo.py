from models.document_chunks import DocumentChunk
from models.raw_documents import CorpusRawDocumentLink, RawDocument
from repositories.helpers import commit_and_refresh
from schemas.raw_documents_schemas import (
    CorpusRawDocumentLinkCreate,
    CorpusRawDocumentLinkDelete,
    RawDocumentCreate,
    RawDocumentUpdate,
)
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession


async def get_raw_document_by_id(
    raw_document_id: int,
    session: AsyncSession,
) -> RawDocument | None:
    return await session.get(RawDocument, raw_document_id)


async def get_raw_document_by_path(
    path: str,
    session: AsyncSession,
) -> RawDocument | None:
    result = await session.exec(select(RawDocument).where(RawDocument.path == path))
    return result.first()


async def get_raw_document_by_name(
    name: str,
    session: AsyncSession,
) -> RawDocument | None:
    result = await session.exec(select(RawDocument).where(RawDocument.name == name))
    return result.first()


async def list_raw_documents(
    session: AsyncSession,
    skip: int = 0,
    limit: int = 20,
    uploaded_by_user_id: int | None = None,
    corpus_id: int | None = None,
    name_contains: str | None = None,
) -> list[RawDocument]:
    statement = select(RawDocument)

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
    result = await session.exec(
        select(DocumentChunk.id).where(DocumentChunk.raw_document_id == raw_document_id)
    )
    return [chunk_id for chunk_id in result.all() if chunk_id is not None]


async def create_raw_document(
    raw_document_in: RawDocumentCreate,
    session: AsyncSession,
) -> RawDocument:
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
    update_data = raw_document_in.model_dump(exclude_unset=True)

    for field_name, value in update_data.items():
        setattr(raw_document, field_name, value)

    return await commit_and_refresh(session, raw_document)


async def get_corpus_raw_document_link(
    corpus_id: int,
    raw_document_id: int,
    session: AsyncSession,
) -> CorpusRawDocumentLink | None:
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
    result = await session.exec(
        select(DocumentChunk.id).where(DocumentChunk.raw_document_id == raw_document_id).limit(1)
    )
    return result.first() is not None


async def delete_raw_document(
    raw_document: RawDocument,
    session: AsyncSession,
) -> None:
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
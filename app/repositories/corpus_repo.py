from models.corpus import Corpus
from models.corpus_indices import CorpusIndex
from models.raw_documents import CorpusRawDocumentLink
from models.simulations import Simulation
from repositories.helpers import commit_and_refresh
from schemas.corpus_schemas import CorpusCreate, CorpusReadWithIds, CorpusUpdate
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession


ACTIVE_INDEX_STATUSES = {"created", "building", "built"}
TERMINAL_SIMULATION_STATUSES = {"completed", "cancelled", "failed"}


async def has_active_indexes(corpus_id: int, session: AsyncSession) -> bool:
    result = await session.exec(
        select(CorpusIndex.id)
        .where(
            CorpusIndex.corpus_id == corpus_id,
            CorpusIndex.status.in_(ACTIVE_INDEX_STATUSES),
        )
        .limit(1)
    )
    return result.first() is not None


async def has_any_indexes(corpus_id: int, session: AsyncSession) -> bool:
    result = await session.exec(
        select(CorpusIndex.id).where(CorpusIndex.corpus_id == corpus_id).limit(1)
    )
    return result.first() is not None


async def has_non_terminal_simulations(corpus_id: int, session: AsyncSession) -> bool:
    result = await session.exec(
        select(Simulation.id)
        .where(
            Simulation.corpus_id == corpus_id,
            Simulation.status.not_in(TERMINAL_SIMULATION_STATUSES),
        )
        .limit(1)
    )
    return result.first() is not None


async def ensure_corpus_editable(corpus: Corpus, session: AsyncSession) -> None:
    if corpus.id is None:
        raise ValueError("Corpus must be persisted before it can be edited")

    if await has_active_indexes(corpus.id, session):
        raise ValueError("Cannot edit corpus with active indexes")

    if await has_non_terminal_simulations(corpus.id, session):
        raise ValueError("Cannot edit corpus used by non-terminal simulations")


async def ensure_corpus_deletable(corpus: Corpus, session: AsyncSession) -> None:
    if corpus.id is None:
        raise ValueError("Corpus must be persisted before it can be deleted")

    if await has_any_indexes(corpus.id, session):
        raise ValueError("Cannot delete corpus with existing indexes")

    if await has_non_terminal_simulations(corpus.id, session):
        raise ValueError("Cannot delete corpus used by non-terminal simulations")


async def get_corpus_by_id(corpus_id: int, session: AsyncSession) -> Corpus | None:
    return await session.get(Corpus, corpus_id)


async def get_corpus_by_name(name: str, session: AsyncSession) -> Corpus | None:
    result = await session.exec(select(Corpus).where(Corpus.name == name))
    return result.first()


async def list_corpora(
    session: AsyncSession,
    skip: int = 0,
    limit: int = 20,
    created_by_user_id: int | None = None,
    raw_document_id: int | None = None,
    has_indexes: bool | None = None,
) -> list[Corpus]:
    statement = select(Corpus)

    if raw_document_id is not None:
        statement = statement.join(
            CorpusRawDocumentLink,
            Corpus.id == CorpusRawDocumentLink.corpus_id,
        ).where(CorpusRawDocumentLink.raw_document_id == raw_document_id)
    if created_by_user_id is not None:
        statement = statement.where(Corpus.created_by_user_id == created_by_user_id)
    if has_indexes is not None:
        index_subquery = select(CorpusIndex.corpus_id).distinct()
        if has_indexes:
            statement = statement.where(Corpus.id.in_(index_subquery))
        else:
            statement = statement.where(Corpus.id.not_in(index_subquery))

    statement = statement.offset(skip).limit(limit)
    result = await session.exec(statement)
    return list(result.all())


async def list_student_accessible_corpora(
    user_id: int,
    session: AsyncSession,
    skip: int = 0,
    limit: int = 20,
) -> list[Corpus]:
    statement = (
        select(Corpus)
        .join(Simulation, Corpus.id == Simulation.corpus_id)
        .where(
            (Simulation.user_id_owner == user_id)
            | (Simulation.user_id_participant == user_id)
        )
        .distinct()
        .offset(skip)
        .limit(limit)
    )
    result = await session.exec(statement)
    return list(result.all())


async def user_has_simulation_access_to_corpus(
    corpus_id: int,
    user_id: int,
    session: AsyncSession,
) -> bool:
    result = await session.exec(
        select(Simulation.id)
        .where(
            Simulation.corpus_id == corpus_id,
            (Simulation.user_id_owner == user_id)
            | (Simulation.user_id_participant == user_id),
        )
        .limit(1)
    )
    return result.first() is not None


async def get_corpus_raw_document_ids(
    corpus_id: int,
    session: AsyncSession,
) -> list[int]:
    result = await session.exec(
        select(CorpusRawDocumentLink.raw_document_id).where(
            CorpusRawDocumentLink.corpus_id == corpus_id
        )
    )
    return [raw_document_id for raw_document_id in result.all() if raw_document_id is not None]


async def get_corpus_index_ids(corpus_id: int, session: AsyncSession) -> list[int]:
    result = await session.exec(select(CorpusIndex.id).where(CorpusIndex.corpus_id == corpus_id))
    return [corpus_index_id for corpus_index_id in result.all() if corpus_index_id is not None]


async def get_corpus_simulation_ids(corpus_id: int, session: AsyncSession) -> list[int]:
    result = await session.exec(select(Simulation.id).where(Simulation.corpus_id == corpus_id))
    return [simulation_id for simulation_id in result.all() if simulation_id is not None]


async def to_corpus_read_with_ids(
    corpus: Corpus,
    session: AsyncSession,
) -> CorpusReadWithIds:
    return CorpusReadWithIds(
        **corpus.model_dump(),
        raw_document_ids=await get_corpus_raw_document_ids(corpus.id, session),
        corpus_index_ids=await get_corpus_index_ids(corpus.id, session),
        simulation_ids=await get_corpus_simulation_ids(corpus.id, session),
    )


async def create_corpus(
    corpus_in: CorpusCreate,
    raw_document_ids: list[int],
    session: AsyncSession,
) -> Corpus:
    corpus = Corpus(**corpus_in.model_dump())

    try:
        session.add(corpus)
        await session.flush()

        for raw_document_id in dict.fromkeys(raw_document_ids):
            session.add(
                CorpusRawDocumentLink(
                    corpus_id=corpus.id,
                    raw_document_id=raw_document_id,
                )
            )

        await session.commit()
        await session.refresh(corpus)
        return corpus
    except Exception:
        await session.rollback()
        raise


async def update_corpus(
    corpus: Corpus,
    corpus_in: CorpusUpdate,
    session: AsyncSession,
) -> Corpus:
    await ensure_corpus_editable(corpus, session)
    update_data = corpus_in.model_dump(exclude_unset=True)

    for field_name, value in update_data.items():
        setattr(corpus, field_name, value)

    return await commit_and_refresh(session, corpus)


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
    corpus: Corpus,
    raw_document_id: int,
    session: AsyncSession,
) -> CorpusRawDocumentLink:
    await ensure_corpus_editable(corpus, session)

    existing_link = await get_corpus_raw_document_link(corpus.id, raw_document_id, session)
    if existing_link is not None:
        return existing_link

    link = CorpusRawDocumentLink(corpus_id=corpus.id, raw_document_id=raw_document_id)

    try:
        session.add(link)
        await session.commit()
        await session.refresh(link)
        return link
    except Exception:
        await session.rollback()
        raise


async def unlink_raw_document_from_corpus(
    corpus: Corpus,
    raw_document_id: int,
    session: AsyncSession,
) -> None:
    await ensure_corpus_editable(corpus, session)

    link = await get_corpus_raw_document_link(corpus.id, raw_document_id, session)
    if link is None:
        return

    try:
        await session.delete(link)
        await session.commit()
    except Exception:
        await session.rollback()
        raise


async def replace_corpus_raw_documents(
    corpus: Corpus,
    raw_document_ids: list[int],
    session: AsyncSession,
) -> Corpus:
    await ensure_corpus_editable(corpus, session)

    try:
        existing_links_result = await session.exec(
            select(CorpusRawDocumentLink).where(CorpusRawDocumentLink.corpus_id == corpus.id)
        )
        for link in existing_links_result.all():
            await session.delete(link)

        for raw_document_id in dict.fromkeys(raw_document_ids):
            session.add(
                CorpusRawDocumentLink(
                    corpus_id=corpus.id,
                    raw_document_id=raw_document_id,
                )
            )

        await session.commit()
        await session.refresh(corpus)
        return corpus
    except Exception:
        await session.rollback()
        raise


async def delete_corpus(corpus: Corpus, session: AsyncSession) -> None:
    await ensure_corpus_deletable(corpus, session)

    try:
        existing_links_result = await session.exec(
            select(CorpusRawDocumentLink).where(CorpusRawDocumentLink.corpus_id == corpus.id)
        )
        for link in existing_links_result.all():
            await session.delete(link)

        await session.delete(corpus)
        await session.commit()
    except Exception:
        await session.rollback()
        raise
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
    """
    Check if a corpus has any active indexes.
    Args:
        corpus_id (int): The ID of the corpus to check.
        session (AsyncSession): The database session to use for the query.
    Returns:
        bool: True if the corpus has active indexes, False otherwise.
    """
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
    """
    Check if a corpus has any indexes.
    Args:
        corpus_id (int): The ID of the corpus to check.
        session (AsyncSession): The database session to use for the query.
    Returns:
        bool: True if the corpus has any indexes, False otherwise.
    """
    result = await session.exec(
        select(CorpusIndex.id).where(CorpusIndex.corpus_id == corpus_id).limit(1)
    )
    return result.first() is not None


async def has_non_terminal_simulations(corpus_id: int, session: AsyncSession) -> bool:
    """
    Check if a corpus has any non-terminal simulations.
    Args:
        corpus_id (int): The ID of the corpus to check.
        session (AsyncSession): The database session to use for the query.
    Returns:
        bool: True if the corpus has any non-terminal simulations, False otherwise.
    """
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
    """
    Ensure that a corpus can be edited.
    Args:
        corpus (Corpus): The corpus to check.
        session (AsyncSession): The database session to use for the query.
    Raises:
        ValueError: If the corpus cannot be edited.
    """
    if corpus.id is None:
        raise ValueError("Corpus must be persisted before it can be edited")

    if await has_active_indexes(corpus.id, session):
        raise ValueError("Cannot edit corpus with active indexes")

    if await has_non_terminal_simulations(corpus.id, session):
        raise ValueError("Cannot edit corpus used by non-terminal simulations")


async def ensure_corpus_deletable(corpus: Corpus, session: AsyncSession) -> None:
    """
    Ensure that a corpus can be deleted.
    Args:
        corpus (Corpus): The corpus to check.
        session (AsyncSession): The database session to use for the query.
    Raises:
        ValueError: If the corpus cannot be deleted.
    """
    if corpus.id is None:
        raise ValueError("Corpus must be persisted before it can be deleted")

    if await has_any_indexes(corpus.id, session):
        raise ValueError("Cannot delete corpus with existing indexes")

    if await has_non_terminal_simulations(corpus.id, session):
        raise ValueError("Cannot delete corpus used by non-terminal simulations")


async def get_corpus_by_id(corpus_id: int, session: AsyncSession) -> Corpus | None:
    """
    Get a corpus by its ID.
    Args:
        corpus_id (int): The ID of the corpus to retrieve.
        session (AsyncSession): The database session to use for the query.
    Returns:
        Corpus | None: The corpus if found, None otherwise.
    """
    return await session.get(Corpus, corpus_id)


async def get_corpus_by_name(name: str, session: AsyncSession) -> Corpus | None:
    """
    Get a corpus by its name.
    Args:
        name (str): The name of the corpus to retrieve.
        session (AsyncSession): The database session to use for the query.
    Returns:
        Corpus | None: The corpus if found, None otherwise.
    """
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
    """
    List corpora with optional filtering by creator, associated raw document, 
    and index presence.
    Args:
        session (AsyncSession): The database session to use for the query.
        skip (int): The number of records to skip for pagination.
        limit (int): The maximum number of records to return for pagination.
        created_by_user_id (int | None): If provided, only return corpora 
            created by this user ID.
        raw_document_id (int | None): If provided, only return corpora 
            associated with this raw document ID.
        has_indexes (bool | None): If True, only return corpora that have 
            indexes. If False, only return corpora that do not have indexes. 
            If None, do not filter by index presence.
    Returns:
        list[Corpus]: A list of corpora matching the specified criteria.
    """
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
    """List corpora that a student has access to through their simulations.
    Args:
        user_id (int): The ID of the student.
        session (AsyncSession): The database session to use for the query.
        skip (int): The number of records to skip for pagination.
        limit (int): The maximum number of records to return for pagination.
    Returns:
        list[Corpus]: A list of corpora that the student has access to.
    """
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
    """
    Check if a user has access to a corpus through their simulations.
    Args:
        corpus_id (int): The ID of the corpus.
        user_id (int): The ID of the user.
        session (AsyncSession): The database session to use for the query.
    Returns:
        bool: True if the user has access to the corpus, False otherwise.
    """
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
    """
    Get the IDs of raw documents associated with a corpus.
    Args:
        corpus_id (int): The ID of the corpus.
        session (AsyncSession): The database session to use for the query.
    Returns:
        list[int]: A list of raw document IDs associated with the corpus.
    """
    result = await session.exec(
        select(CorpusRawDocumentLink.raw_document_id).where(
            CorpusRawDocumentLink.corpus_id == corpus_id
        )
    )
    return [raw_document_id for raw_document_id in result.all() if raw_document_id is not None]


async def get_corpus_index_ids(corpus_id: int, session: AsyncSession) -> list[int]:
    """
    Get the IDs of corpus indexes associated with a corpus.
    Args:
        corpus_id (int): The ID of the corpus.
        session (AsyncSession): The database session to use for the query.
    Returns:
        list[int]: A list of corpus index IDs associated with the corpus.
    """
    result = await session.exec(select(CorpusIndex.id).where(CorpusIndex.corpus_id == corpus_id))
    return [corpus_index_id for corpus_index_id in result.all() if corpus_index_id is not None]


async def get_corpus_simulation_ids(corpus_id: int, session: AsyncSession) -> list[int]:
    """
    Get the IDs of simulations associated with a corpus.
    Args:
        corpus_id (int): The ID of the corpus.
        session (AsyncSession): The database session to use for the query.
    Returns:
        list[int]: A list of simulation IDs associated with the corpus.
    """
    result = await session.exec(select(Simulation.id).where(Simulation.corpus_id == corpus_id))
    return [simulation_id for simulation_id in result.all() if simulation_id is not None]


async def to_corpus_read_with_ids(
    corpus: Corpus,
    session: AsyncSession,
) -> CorpusReadWithIds:
    """Convert a Corpus model instance to a CorpusReadWithIds schema 
    instance, including associated raw document IDs, corpus index IDs, 
    and simulation IDs.
    Args:
        corpus (Corpus): The Corpus model instance to convert.
        session (AsyncSession): The database session to use for the queries.
    Returns:
        CorpusReadWithIds: The converted CorpusReadWithIds schema instance.
    """
    return CorpusReadWithIds(
        **corpus.model_dump(),
        raw_document_ids=await get_corpus_raw_document_ids(corpus.id, session),
        corpus_index_ids=await get_corpus_index_ids(corpus.id, session),
        simulation_ids=await get_corpus_simulation_ids(corpus.id, session),
    )


async def create_corpus(
    corpus_data: CorpusCreate, # has the raw_document_ids field
    created_by_user_id: int,
    session: AsyncSession,
) -> Corpus:
    """
    Create a new corpus and associate it with the given raw documents.
    Args:
        corpus_data (CorpusCreate): The data for the new corpus 
            Contains name, description, and raw_document_ids
        created_by_user_id (int): The ID of the user creating the corpus.
        session (AsyncSession): The database session to use for the queries.
    Returns:
        Corpus: The created Corpus model instance.
    """
    corpus_data_without_links = corpus_data.model_dump(exclude={"raw_document_ids"})
    corpus = Corpus(
        **corpus_data_without_links,
        created_by_user_id=created_by_user_id,
    )

    try:
        session.add(corpus)
        await session.flush()

        for raw_document_id in dict.fromkeys(corpus_data.raw_document_ids):
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
    """
    Update an existing corpus with new data.
    Args:
        corpus (Corpus): The Corpus model instance to update.
        corpus_in (CorpusUpdate): The data to update the corpus with.
        session (AsyncSession): The database session to use for the queries.
    Returns:
        Corpus: The updated Corpus model instance.
    """
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
    """
    Get the link between a corpus and a raw document.
    Args:
        corpus_id (int): The ID of the corpus.
        raw_document_id (int): The ID of the raw document.
        session (AsyncSession): The database session to use for the query.
    Returns:
        CorpusRawDocumentLink | None: The link between the corpus and the 
        raw document, or None if it doesn't exist.
    """
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
    """Link a raw document to a corpus.
    Args:
        corpus (Corpus): The corpus to link the raw document to.
        raw_document_id (int): The ID of the raw document to link.
        session (AsyncSession): The database session to use for the queries.
    Returns:
        CorpusRawDocumentLink: The created link between the corpus and the raw document.
    """
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
    """
    Unlink a raw document from a corpus.
    Args:
        corpus (Corpus): The corpus to unlink the raw document from.
        raw_document_id (int): The ID of the raw document to unlink.
        session (AsyncSession): The database session to use for the queries.
    Returns:
        None
    """
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
    """
    Replace the raw documents linked to a corpus with a new set of raw 
    documents.
    Args:
        corpus (Corpus): The corpus to update the raw documents for.
        raw_document_ids (list[int]): The IDs of the new raw documents to link.
        session (AsyncSession): The database session to use for the queries.
    Returns:
        Corpus: The updated corpus with the new raw document links.
    """
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
    """
    Delete a corpus from the database.
    Args:
        corpus (Corpus): The corpus to delete.
        session (AsyncSession): The database session to use for the queries.
    Returns:
        None
    """
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

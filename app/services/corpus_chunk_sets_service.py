from collections.abc import Sequence

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.chunking_profiles import ChunkingProfile
from app.models.corpus import Corpus
from app.models.corpus_chunk_sets import CorpusChunkSet
from app.models.document_chunks import DocumentChunk
from app.models.full_corpus_index_pipe_jobs import FullCorpusIndexPipeJob
from app.models.raw_documents import CorpusRawDocumentLink
from app.repositories import corpus_chunk_sets_repo as repo
from app.repositories.helpers import utc_now
from app.schemas.corpus_chunk_sets_schemas import (
    CorpusChunkSetCreate,
    CorpusChunkSetRead,
    CorpusChunkSetSnapshot,
    CorpusChunkSetUpdate,
)

# Helper candidate
def _persisted_id(value: int | None, label: str) -> int:
    """
    Get the persisted ID of a value.

    Args:
        value: The value to check.
        label: The label for the value, used in the error message.
    Returns:
        The persisted ID.
    Raises:
        ValueError: If the value is None.
    """
    if value is None:
        raise ValueError(f"{label} must be persisted")
    return value


async def _load_valid_members(
    *,
    corpus_id: int,
    chunking_profile_id: int,
    document_chunk_ids: Sequence[int],
    session: AsyncSession,
) -> list[DocumentChunk]:
    """
    Load and validate the document chunks for a corpus chunk set.

    Args:
        corpus_id: The ID of the corpus.
        chunking_profile_id: The ID of the chunking profile.
        document_chunk_ids: The IDs of the document chunks to validate.
        session: The database session to use.
    Returns:
        A list of valid DocumentChunk objects.
    Raises:
        ValueError: If any validation checks fail.
    """
    if not document_chunk_ids:
        raise ValueError("Corpus chunk set must contain at least one document chunk")
    if len(set(document_chunk_ids)) != len(document_chunk_ids):
        raise ValueError("Corpus chunk set contains duplicate document chunk IDs")

    result = await session.exec(
        select(DocumentChunk).where(DocumentChunk.id.in_(document_chunk_ids))
    )
    chunks = list(result.all())
    found_ids = {_persisted_id(chunk.id, "Document chunk") for chunk in chunks}
    if found_ids != set(document_chunk_ids):
        raise ValueError("One or more document chunks do not exist")
    if any(chunk.chunking_profile_id != chunking_profile_id for chunk in chunks):
        raise ValueError("All document chunks must use the selected chunking profile")

    links = await session.exec(
        select(CorpusRawDocumentLink.raw_document_id).where(
            CorpusRawDocumentLink.corpus_id == corpus_id
        )
    )
    corpus_document_ids = set(links.all())
    if any(chunk.raw_document_id not in corpus_document_ids for chunk in chunks):
        raise ValueError("A document chunk is not associated with corpus")
    return chunks


async def _to_read(
    chunk_set: CorpusChunkSet,
    session: AsyncSession,
) -> CorpusChunkSetRead:
    """
    Convert a CorpusChunkSet to its read representation.

    Args:
        chunk_set: The corpus chunk set to convert.
        session: The database session to use.
    Returns:
        The CorpusChunkSetRead representation of the chunk set.
    """
    chunk_set_id = _persisted_id(chunk_set.id, "Corpus chunk set")
    chunks = await repo.get_corpus_chunk_set_document_chunks(chunk_set_id, session)
    return CorpusChunkSetRead(
        **chunk_set.model_dump(exclude={"id"}),
        id=chunk_set_id,
        distinct_document_count=len({chunk.raw_document_id for chunk in chunks}),
        chunk_count=len(chunks),
    )


async def create_corpus_chunk_set_srvc(
    data: CorpusChunkSetCreate,
    session: AsyncSession,
    *,
    commit: bool = True,
) -> CorpusChunkSetRead:
    """
    Create a new corpus chunk set with the provided data.

    Args:
        data: The data for the new corpus chunk set.
        session: The database session to use.
        commit: Whether to commit the transaction after creation.
    Returns:
        The created CorpusChunkSetRead representation.
    Raises:
        ValueError: If any validation checks fail.
    """
    name = data.name.strip()
    if len(name) < 3:
        raise ValueError("Corpus chunk set name must be at least 3 characters")
    if await session.get(Corpus, data.corpus_id) is None:
        raise ValueError("Corpus not found")
    profile = await session.get(ChunkingProfile, data.chunking_profile_id)
    if profile is None:
        raise ValueError("Chunking profile not found")
    if await repo.get_corpus_chunk_set_by_name(data.corpus_id, name, session) is not None:
        raise ValueError("Corpus chunk set name already exists")
    await _load_valid_members(
        corpus_id=data.corpus_id,
        chunking_profile_id=data.chunking_profile_id,
        document_chunk_ids=data.document_chunk_ids,
        session=session,
    )
    # Prepare the CorpusChunkSet row for creation
    row = CorpusChunkSet(
        corpus_id=data.corpus_id,
        name=name,
        chunking_profile_id=data.chunking_profile_id,
        chunking_profile_name=profile.name,
        chunking_strategy=profile.strategy,
        chunking_config=dict(profile.config),
        document_chunk_ids_checksum=repo.document_chunk_ids_checksum(
            data.document_chunk_ids
        ),
    )
    # Persist the CorpusChunkSet and its members
    created = await repo.create_corpus_chunk_set(
        row,
        data.document_chunk_ids,
        session,
        commit=commit,
    )
    return await _to_read(created, session)


async def get_corpus_chunk_set_snapshot_srvc(
    chunk_set_id: int,
    session: AsyncSession,
) -> CorpusChunkSetSnapshot:
    """
    Get a snapshot of a corpus chunk set, including its document chunk IDs.

    Args:
        chunk_set_id: The ID of the corpus chunk set.
        session: The database session.
    Returns:
        CorpusChunkSetSnapshot: The snapshot of the corpus chunk set.
    Raises:
        ValueError: If the corpus chunk set is not found.
    """
    chunk_set = await repo.get_corpus_chunk_set_by_id(chunk_set_id, session)
    if chunk_set is None:
        raise ValueError("Corpus chunk set not found")
    chunks = await repo.get_corpus_chunk_set_document_chunks(chunk_set_id, session)
    return CorpusChunkSetSnapshot(
        chunk_set=await _to_read(chunk_set, session),
        document_chunk_ids=[_persisted_id(chunk.id, "Document chunk") for chunk in chunks],
    )


async def list_corpus_chunk_sets_srvc(
    corpus_id: int,
    session: AsyncSession,
) -> list[CorpusChunkSetRead]:
    """
    Service call to list all corpus chunk sets for a given corpus.

    Args:
        corpus_id: The ID of the corpus.
        session: The database session.
    Returns:
        list[CorpusChunkSetRead]: A list of corpus chunk sets.
    Raises:
        ValueError: If the corpus is not found.
    """
    rows = await repo.list_corpus_chunk_sets(corpus_id, session)
    return [await _to_read(row, session) for row in rows]


async def update_corpus_chunk_set_srvc(
    chunk_set_id: int,
    data: CorpusChunkSetUpdate,
    session: AsyncSession,
) -> CorpusChunkSetRead:
    """
    Update a corpus chunk set, including its name, membership, and chunking 
    configuration.

    Args:
        chunk_set_id: The ID of the corpus chunk set to update.
        data: The update data containing the new values.
        session: The database session.
    Returns:
        CorpusChunkSetRead: The updated corpus chunk set.
    Raises:
        ValueError: If the corpus chunk set is not found or any validation 
        checks fail.
    """
    chunk_set = await repo.get_corpus_chunk_set_by_id(chunk_set_id, session)
    if chunk_set is None:
        raise ValueError("Corpus chunk set not found")
    changes = data.model_dump(exclude_unset=True)
    if "name" in changes:
        name = changes.pop("name")
        if name is not None:
            name = name.strip()
            if len(name) < 3:
                raise ValueError("Corpus chunk set name must be at least 3 characters")
            existing = await repo.get_corpus_chunk_set_by_name(
                chunk_set.corpus_id, name, session
            )
            if existing is not None and existing.id != chunk_set.id:
                raise ValueError("Corpus chunk set name already exists")
            chunk_set.name = name

    member_ids = changes.pop("document_chunk_ids", None)
    revision_changed = member_ids is not None
    if member_ids is not None:
        if chunk_set.chunking_profile_id is None:
            raise ValueError("Cannot change membership after the chunking profile is deleted")
        await _load_valid_members(
            corpus_id=chunk_set.corpus_id,
            chunking_profile_id=chunk_set.chunking_profile_id,
            document_chunk_ids=member_ids,
            session=session,
        )
        chunk_set.document_chunk_ids_checksum = repo.document_chunk_ids_checksum(member_ids)

    for field_name in ("chunking_profile_name", "chunking_strategy", "chunking_config"):
        if field_name in changes and changes[field_name] is not None:
            value = changes[field_name]
            if field_name == "chunking_config":
                value = dict(value)
            if getattr(chunk_set, field_name) != value:
                setattr(chunk_set, field_name, value)
                revision_changed = True
    if revision_changed:
        chunk_set.revision += 1
    chunk_set.last_updated = utc_now()
    if member_ids is None:
        session.add(chunk_set)
        await session.commit()
        await session.refresh(chunk_set)
    else:
        chunk_set = await repo.replace_corpus_chunk_set_members(
            chunk_set, member_ids, session
        )
    return await _to_read(chunk_set, session)


async def delete_corpus_chunk_set_srvc(
    chunk_set_id: int,
    session: AsyncSession,
) -> None:
    """
    Delete a corpus chunk set.

    Args:
        chunk_set_id: The ID of the corpus chunk set to delete.
        session: The database session.
    Raises:
        ValueError: If the corpus chunk set is not found or is referenced 
        by an index or active job.
    """
    chunk_set = await repo.get_corpus_chunk_set_by_id(chunk_set_id, session)
    if chunk_set is None:
        raise ValueError("Corpus chunk set not found")
    if (
        await repo.corpus_chunk_set_has_index_references(chunk_set_id, session)
        or await repo.corpus_chunk_set_has_active_job_references(chunk_set_id, session)
    ):
        raise ValueError("Corpus chunk set is referenced by an index or active job")
    await repo.delete_corpus_chunk_set(chunk_set, session)


async def delete_owned_corpus_chunk_set_srvc(
    chunk_set_id: int,
    owner_job_id: int,
    session: AsyncSession,
) -> list[int]:
    """
    Delete a corpus chunk set owned by a specific full corpus index pipe job.

    Args:
        chunk_set_id: The ID of the corpus chunk set to delete.
        owner_job_id: The ID of the owning full corpus index pipe job.
        session: The database session.
    Returns:
        list[int]: A list of document chunk IDs that are no longer referenced by 
        any other chunk set.
    Raises:
        ValueError: If the corpus chunk set is not owned by the specified full 
        corpus index pipe job.
    """
    chunk_set = await repo.get_corpus_chunk_set_by_id(chunk_set_id, session)
    if chunk_set is None:
        return []
    owner = await session.get(FullCorpusIndexPipeJob, owner_job_id)
    if owner is None or getattr(owner, "corpus_chunk_set_id", None) != chunk_set_id:
        raise ValueError("Corpus chunk set is not owned by the full corpus index pipe job")
    chunks = await repo.get_corpus_chunk_set_document_chunks(chunk_set_id, session)
    member_ids = [_persisted_id(chunk.id, "Document chunk") for chunk in chunks]
    remaining = await repo.count_other_chunk_set_references(
        member_ids, chunk_set_id, session
    )
    await repo.delete_corpus_chunk_set(chunk_set, session)
    return [chunk_id for chunk_id in member_ids if remaining.get(chunk_id, 0) == 0]

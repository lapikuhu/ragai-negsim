from app.models.corpus import Corpus
from app.models.users import User
from app.schemas.corpus_schemas import CorpusCreate
from app.schemas.corpus_bm25_build_jobs_schemas import CorpusChunkSetSummary
from app.repositories import chunking_profiles_repo, document_chunks_repo
from app.repositories.corpus_bm25_indices_repo import document_chunk_ids_checksum
from app.services.helpers import _persisted_id

from app.repositories.corpus_repo import(AsyncSession, 
                                     create_corpus, 
                                     list_corpora)

async def create_corpus_srvc(
    corpus_data: CorpusCreate,
    session: AsyncSession,
    current_user: User,
) -> Corpus:
    """Service function to create a new corpus in the database. Repo
    function takes care of creating the corpus and linking it to the raw 
    documents.
    Args:
        corpus_data (CorpusCreate): The data for the corpus to be created.
        session (AsyncSession): The database session to use for the operation.
        current_user (User): The user creating the corpus.
    Returns:
        Corpus: The created Corpus model instance.
    """
    return await create_corpus(
        corpus_data=corpus_data,
        created_by_user_id=current_user.id,
        session=session,
    )

async def list_corpora_srvc(session: AsyncSession,
                            skip: int = 0,
                            limit: int = 20,
                            created_by_user_id: int | None = None,
                            raw_document_id: int | None = None,
                            has_indices: bool | None = None) -> list[Corpus]:
    """
    Service function to list all corpora from the database.
    Args:
        session (AsyncSession): Database session for querying corpora.
        skip (int): Number of records to skip for pagination.
        limit (int): Maximum number of records to return for pagination.
        created_by_user_id (int | None): Filter by the user ID who created the corpus.
        raw_document_id (int | None): Filter by the raw document ID associated with the corpus.
        has_indices (bool | None): Filter by whether the corpus has indices.
    Returns:
        A list of Corpus objects representing all corpora in the database.
    """
    corpora = await list_corpora(
                                 session=session,
                                 skip=skip,
                                 limit=limit,
                                 created_by_user_id=created_by_user_id,
                                 raw_document_id=raw_document_id,
                                 has_indexes=has_indices)
    return corpora


async def list_corpus_chunk_set_summaries_srvc(
    corpus_id: int,
    session: AsyncSession,
) -> list[CorpusChunkSetSummary]:
    """
    Group a corpus's persisted chunks by chunking profile.

    Args:
        corpus_id: The ID of the corpus.
        session: The database session.
    Returns:
        A list of CorpusChunkSetSummary objects, each representing a group 
        of chunks associated with a specific chunking profile.
    """
    chunks = await document_chunks_repo.list_corpus_document_chunks(corpus_id, session)
    if not chunks:
        return []

    grouped: dict[int, list] = {}
    for chunk in chunks:
        grouped.setdefault(chunk.chunking_profile_id, []).append(chunk)
    names = await chunking_profiles_repo.get_chunking_profile_names_by_ids(
        set(grouped), session
    )
    summaries = []
    for profile_id, profile_chunks in grouped.items():
        chunk_ids = sorted(
            _persisted_id(chunk.id, "Document chunk") for chunk in profile_chunks
        )
        summaries.append(
            CorpusChunkSetSummary(
                chunking_profile_id=profile_id,
                chunking_profile_name=names.get(profile_id, f"Profile {profile_id}"),
                distinct_document_count=len(
                    {chunk.raw_document_id for chunk in profile_chunks}
                ),
                chunk_count=len(chunk_ids),
                document_chunk_ids_checksum=document_chunk_ids_checksum(chunk_ids),
            )
        )
    return sorted(
        summaries,
        key=lambda item: (item.chunking_profile_name.lower(), item.chunking_profile_id),
    )

from app.models.corpus import Corpus
from app.models.users import User
from app.schemas.corpus_schemas import CorpusCreate

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

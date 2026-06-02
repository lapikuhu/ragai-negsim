from core.dependencies import (
    ChunkingProfileDep,
    ChunkingOptionsDep,
    CorpusCreatorDep,
    IngestionOptionsDep,
    SessionDep,
    WritableCorpusDep,
)
from schemas.corpus_schemas import CorpusCreate, CorpusRead
from schemas.chunking_schemas import CorpusChunkResult
from schemas.ingestion_schemas import CorpusIngestResult
from services.corpus_service import (create_corpus_srvc, 
                                     list_corpora_srvc)
from services.chunking_service import chunk_corpus_srvc
from services.ingestion_service import ingest_corpus_srvc
from fastapi import APIRouter, HTTPException


router = APIRouter(prefix="/corpora", tags=["corpora"])

### ------------------------ CREATE CORPUS ------------------------- ###
@router.post("/", 
             response_model=CorpusRead,
             status_code=201)
async def create_corpus(
    corpus_data: CorpusCreate,
    session: SessionDep,
    current_user: CorpusCreatorDep,
) -> CorpusRead:
    """
    Endpoint to create a new corpus.
    Args:
        corpus_data: The data for the corpus to be created.
        session: The database session to use for the operation.
        current_user: The user creating the corpus.
    Returns:
        The created CorpusRead instance.
    """
    corpus = await create_corpus_srvc(corpus_data, session, current_user)
    return CorpusRead.model_validate(corpus)

### ------------------------ LIST CORPORA -------------------------- ###
@router.get("/", 
            response_model=list[CorpusRead],
            status_code=200)
async def list_corpora(
    session: SessionDep,
    skip: int = 0,
    limit: int = 20,
    created_by_user_id: int | None = None,
    raw_document_id: int | None = None,
    has_indices: bool | None = None
) -> list[CorpusRead]:
    """
    Endpoint to list all corpora.
    Args:
        session: The database session to use for the operation.
        skip: The number of records to skip for pagination.
        limit: The maximum number of records to return.
        created_by_user_id: Optional filter to return corpora created by a 
            specific user.
        raw_document_id: Optional filter to return corpora associated with a 
            specific raw document.
        has_indices: Optional filter to return corpora that have indices.
    Returns:
        A list of CorpusRead instances representing all corpora.
    """
    corpora = await list_corpora_srvc(session,
                                      skip=skip,
                                      limit=limit,
                                      created_by_user_id=created_by_user_id,
                                      raw_document_id=raw_document_id,
                                      has_indices=has_indices)
    return [CorpusRead.model_validate(corpus) for corpus in corpora]


### ------------------------ INGEST CORPUS -------------------------- ###
@router.post(
    "/{corpus_id}/chunking-profiles/{profile_id}/ingest",
    response_model=CorpusIngestResult,
    status_code=201,
)
async def ingest_corpus(
    corpus: WritableCorpusDep,
    chunking_profile: ChunkingProfileDep,
    session: SessionDep,
    options: IngestionOptionsDep,
) -> CorpusIngestResult:
    """
    Endpoint to ingest and parse all raw documents linked to a corpus.
    Args:
        corpus: The writable corpus to ingest.
        chunking_profile: The chunking profile to associate with created chunks.
        session: The database session to use for persistence.
        options: Query options controlling parsing and chunking.
    Returns:
        A summary of created chunks per raw document.
    """
    try:
        return await ingest_corpus_srvc(
            corpus=corpus,
            chunking_profile=chunking_profile,
            session=session,
            options=options,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


### ------------------------ CHUNK CORPUS -------------------------- ###
@router.post(
    "/{corpus_id}/chunking-profiles/{profile_id}/chunk",
    response_model=CorpusChunkResult,
    status_code=201,
)
async def chunk_corpus(
    corpus: WritableCorpusDep,
    chunking_profile: ChunkingProfileDep,
    session: SessionDep,
    options: ChunkingOptionsDep,
) -> CorpusChunkResult:
    """
    Endpoint to chunk already parsed raw documents linked to a corpus.
    Args:
        corpus: The writable corpus to chunk.
        chunking_profile: The chunking profile to associate with created chunks.
        session: The database session to use for persistence.
        options: Query options controlling chunking behavior.
    Returns:
        A summary of created or previewed chunks per raw document.
    """
    try:
        return await chunk_corpus_srvc(
            corpus=corpus,
            chunking_profile=chunking_profile,
            session=session,
            options=options,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

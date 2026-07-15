from fastapi import APIRouter, HTTPException, status

from app.core.dependencies import AdminDep, Page, SessionDep
from app.schemas.rag_eval_schemas import (
    RagEvalPairProfileCreateRequest,
    RagEvalPairProfileRead,
    RagEvalPairProfileUpdateRequest,
    RagEvalRunDetailRead,
    RagEvalRunRead,
    RagEvalRunStartRequest,
)
from app.services import rag_eval_service

# Declare the routers for RAG evaluation pair profiles and runs
pair_router = APIRouter(prefix="/rag-eval-pair-profiles", tags=["rag-eval"])
run_router = APIRouter(prefix="/rag-eval-runs", tags=["rag-eval"])

# Helper Candidate
def _service_error(exc: ValueError) -> None:
    detail = str(exc)
    code = 404 if detail.endswith("not found") else 409
    raise HTTPException(status_code=code, detail=detail) from exc

### ---------------- RAG EVAL PAIR PROFILE CREATE ------------------ ###
@pair_router.post("/", response_model=RagEvalPairProfileRead, status_code=status.HTTP_201_CREATED)
async def create_pair(data: RagEvalPairProfileCreateRequest, 
                      session: SessionDep, 
                      admin: AdminDep) -> RagEvalPairProfileRead | None:
    """
    Create a new RAG evaluation pair profile.
    Args:
        data (RagEvalPairProfileCreateRequest): The data for the new RAG 
            evaluation pair profile.
        session (SessionDep): The database session.
        admin (AdminDep): The current admin user performing the creation.
    Returns:
        RagEvalPairProfileRead: The created RAG evaluation pair profile read model.
    """
    try:
        return await rag_eval_service.create_rag_eval_pair_profile_srvc(data, session, admin)
    except ValueError as exc:
        _service_error(exc)

### ------------------ RAG EVAL PAIR PROFILE LIST ------------------ ###
@pair_router.get("/", response_model=list[RagEvalPairProfileRead], status_code=status.HTTP_200_OK)
async def list_pairs(session: SessionDep, 
                     _admin: AdminDep, 
                     page: Page) -> list[RagEvalPairProfileRead]:
    """
    List RAG evaluation pair profiles with pagination.
    Args:
        session (SessionDep): The database session.
        _admin (AdminDep): The current admin user.
        page (Page): Pagination information.
    Returns:
        list[RagEvalPairProfileRead]: A list of RAG evaluation pair profiles.
    """
    return await rag_eval_service.list_rag_eval_pair_profiles_srvc(session, 
                                                                   skip=page["skip"], 
                                                                   limit=page["limit"])

### --------------- RAG EVAL PAIR PROFILE GET BY ID----------------- ###
@pair_router.get("/{pair_id}", response_model=RagEvalPairProfileRead, status_code=status.HTTP_200_OK)
async def get_pair(pair_id: int, 
                   session: SessionDep, 
                   _admin: AdminDep) -> RagEvalPairProfileRead:
    """
    Get a specific RAG evaluation pair profile by its ID.
    Args:
        pair_id (int): The ID of the RAG evaluation pair profile.
        session (SessionDep): The database session.
        _admin (AdminDep): The current admin user.
    Returns:
        RagEvalPairProfileRead: The RAG evaluation pair profile read model.
    Raises:
        HTTPException: If the RAG evaluation pair profile is not found.
    """
    try:
        return await rag_eval_service.get_rag_eval_pair_profile_srvc(pair_id, session)
    except ValueError as exc:
        _service_error(exc)

### ----------------- RAG EVAL PAIR PROFILE PATCH ------------------ ###
@pair_router.patch("/{pair_id}", response_model=RagEvalPairProfileRead, status_code=status.HTTP_200_OK)
async def update_pair(pair_id: int, 
                      data: RagEvalPairProfileUpdateRequest, 
                      session: SessionDep, 
                      admin: AdminDep) -> RagEvalPairProfileRead:
    """
    Update a specific RAG evaluation pair profile by its ID.
    Args:
        pair_id (int): The ID of the RAG evaluation pair profile.
        data (RagEvalPairProfileUpdateRequest): The update request data.
        session (SessionDep): The database session.
        admin (AdminDep): The current admin user.
    Returns:
        RagEvalPairProfileRead: The updated RAG evaluation pair profile read model.
    Raises:
        HTTPException: If the RAG evaluation pair profile is not found.
    """
    try:
        return await rag_eval_service.update_rag_eval_pair_profile_srvc(pair_id, 
                                                                        data, 
                                                                        session, 
                                                                        admin)
    except ValueError as exc:
        _service_error(exc)

### ----------------- RAG EVAL PAIR PROFILE DELETE ----------------- ###
@pair_router.delete("/{pair_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_pair(pair_id: int, 
                      session: SessionDep, 
                      _admin: AdminDep) -> None:
    """
    Delete a specific RAG evaluation pair profile by its ID.
    Args:
        pair_id (int): The ID of the RAG evaluation pair profile.
        session (SessionDep): The database session.
        _admin (AdminDep): The current admin user.
    Raises:
        HTTPException: If the RAG evaluation pair profile is not found.
    """
    try:
        await rag_eval_service.delete_rag_eval_pair_profile_srvc(pair_id, 
                                                                 session)
    except ValueError as exc:
        _service_error(exc)

### ---------------------- RAG EVAL RUN START ---------------------- ###
@pair_router.post("/{pair_id}/runs", response_model=RagEvalRunRead, status_code=status.HTTP_202_ACCEPTED)
async def start_run(pair_id: int, 
                    data: RagEvalRunStartRequest, 
                    session: SessionDep, 
                    _admin: AdminDep) -> RagEvalRunRead:
    """
    Start a new RAG evaluation run for a specific pair profile.
    Args:
        pair_id (int): The ID of the RAG evaluation pair profile.
        data (RagEvalRunStartRequest): The start request data.
        session (SessionDep): The database session.
        _admin (AdminDep): The current admin user.
    Returns:
        RagEvalRunRead: The created RAG evaluation run read model.
    Raises:
        HTTPException: If the RAG evaluation pair profile is not found.
    """
    try:
        return await rag_eval_service.start_rag_eval_run_srvc(pair_id, 
                                                              data, 
                                                              session)
    except ValueError as exc:
        _service_error(exc)

### ---------------------- RAG EVAL RUN LIST ----------------------- ###
@run_router.get("/", response_model=list[RagEvalRunRead])
async def list_runs(session: SessionDep, _admin: AdminDep, page: Page, 
                    pair_profile_id: int | None = None, 
                    status_filter: str | None = None) -> list[RagEvalRunRead]:
    """
    List RAG evaluation runs with optional filtering by pair profile ID and status.
    Args:
        session (SessionDep): The database session.
        _admin (AdminDep): The current admin user.
        page (Page): Pagination information.
        pair_profile_id (int | None): Optional ID of the RAG evaluation pair profile to filter by.
        status_filter (str | None): Optional status to filter by.
    Returns:
        list[RagEvalRunRead]: A list of RAG evaluation run read models.
    """
    return await rag_eval_service.list_rag_eval_runs_srvc(session, 
                                                          skip=page["skip"], 
                                                          limit=page["limit"], 
                                                          pair_profile_id=pair_profile_id, 
                                                          status=status_filter)

### ---------------------- RAG EVAL RUN GET ------------------------ ###
@run_router.get("/{run_id}", response_model=RagEvalRunDetailRead)
async def get_run(run_id: int, session: SessionDep, _admin: AdminDep) -> RagEvalRunDetailRead | None:
    """
    Get the details of a specific RAG evaluation run by its ID.
    Args:
        run_id (int): The ID of the RAG evaluation run.
        session (SessionDep): The database session.
        _admin (AdminDep): The current admin user.
    Returns:
        RagEvalRunDetailRead: The detailed RAG evaluation run read model.
    Raises:
        HTTPException: If the RAG evaluation run is not found.
    """
    try:
        return await rag_eval_service.get_rag_eval_run_srvc(run_id, session)
    except ValueError as exc:
        _service_error(exc)

### ---------------------- RAG EVAL RUN CANCEL --------------------- ###
@run_router.post("/{run_id}/cancel", response_model=RagEvalRunRead)
async def cancel_run(run_id: int, session: SessionDep, _admin: AdminDep) -> RagEvalRunRead | None:
    """
    Cancel a specific RAG evaluation run by its ID.
    Args:
        run_id (int): The ID of the RAG evaluation run.
        session (SessionDep): The database session.
        _admin (AdminDep): The current admin user.
    Returns:
        RagEvalRunRead: The canceled RAG evaluation run read model.
    Raises:
        HTTPException: If the RAG evaluation run is not found.
    """
    try:
        return await rag_eval_service.cancel_rag_eval_run_srvc(run_id, 
                                                               session)
    except ValueError as exc:
        _service_error(exc)

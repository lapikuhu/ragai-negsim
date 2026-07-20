"""Admin-only HTTP API for RAG evaluation configurations and runs."""

from typing import Literal, NoReturn
from fastapi import APIRouter, HTTPException, status
from pydantic import ValidationError

# local imports
from app.core.dependencies import AdminDep, Page, SessionDep
from app.schemas.rag_eval_schemas import (
    RagEvalConfigurationCreateRequest,
    RagEvalConfigurationRead,
    RagEvalConfigurationUpdateRequest,
    RagEvalRunEnqueueRequest,
    RagEvalRunDetailRead,
    RagEvalRunRead,
)
from app.services import rag_eval_service

# Allowed rag-eval run statuses for filtering and validation
RagEvalRunStatus = Literal[
    "queued",
    "running",
    "completed",
    "failed",
    "cancelled",
]

# Instantiate the config router
configuration_router = APIRouter(
    prefix="/rag-eval-configurations",
    tags=["rag-eval"],
)
# Instantiate the run router
run_router = APIRouter(prefix="/rag-eval-runs", tags=["rag-eval"])

# Configure safe service error mappings and validation messages
_SAFE_SERVICE_ERRORS = {
    "RAG evaluation configuration not found": status.HTTP_404_NOT_FOUND,
    "RAG evaluation run not found": status.HTTP_404_NOT_FOUND,
    "RAG evaluation configuration name already exists": status.HTTP_409_CONFLICT,
    (
        "Cannot delete RAG evaluation configuration referenced by evaluation runs"
    ): status.HTTP_409_CONFLICT,
    "Cannot cancel a finished RAG evaluation run": status.HTTP_409_CONFLICT,
}
_SAFE_CONFIGURATION_VALIDATION_MESSAGES = {
    "Value error, metrics.k must be less than or equal to rag.top_n",
    "Value error, metrics.k must be less than or equal to rag.evidence_limit",
}

### ----------------------- RAG-EVAL HELPERS ----------------------- ###

def _safe_validation_details(exc: ValidationError) -> list[dict[str, object]]:
    """
    Return JSON-safe validation details without inputs or exception contexts.
    Args:
        exc: The Pydantic ValidationError to process.
    Returns:
        A list of dictionaries containing safe validation error details."""
    details: list[dict[str, object]] = []
    for error in exc.errors(
        include_url=False,
        include_context=False,
        include_input=False,
    ):
        raw_message = str(error.get("msg", "Invalid value"))
        message = (
            raw_message
            if raw_message in _SAFE_CONFIGURATION_VALIDATION_MESSAGES
            else "Invalid RAG evaluation configuration"
        )
        details.append(
            {
                "type": str(error.get("type", "value_error")),
                "loc": ["body", *error.get("loc", ())],
                "msg": message,
            }
        )
    return details


def _raise_service_error(exc: ValueError) -> NoReturn:
    """
    Map known service-domain failures without exposing implementation errors.
    Args:
        exc: The ValueError raised by the service layer.
    Raises:
        HTTPException: A FastAPI HTTPException with a safe status code and 
        message.
    """
    if isinstance(exc, ValidationError):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=_safe_validation_details(exc),
        ) from exc

    raw_detail = str(exc)
    status_code = _SAFE_SERVICE_ERRORS.get(raw_detail)
    if status_code is not None:
        detail = raw_detail
    elif raw_detail.endswith("not found"):
        status_code = status.HTTP_404_NOT_FOUND
        detail = "RAG evaluation resource not found"
    else:
        status_code = status.HTTP_409_CONFLICT
        detail = "RAG evaluation operation conflicts with current state"
    raise HTTPException(status_code=status_code, detail=detail) from exc

### ------------------ RAG-EVAL CONFIGURATION POST ----------------- ###
@configuration_router.post(
    "/",
    response_model=RagEvalConfigurationRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_configuration(
    data: RagEvalConfigurationCreateRequest,
    session: SessionDep,
    admin: AdminDep,
) -> RagEvalConfigurationRead:
    """
    Create a new RAG evaluation configuration.
    Args:
        data: The configuration data to create.
        session: The database session.
        admin: The admin performing the action.
    Returns:
        The newly created RAG evaluation configuration.
    Raises:
        HTTPException: If the configuration name already exists or if there are
        validation errors in the input data.
    """
    try:
        return await rag_eval_service.create_rag_eval_configuration_srvc(
            data,
            session,
            admin,
        )
    except ValueError as exc:
        _raise_service_error(exc)

### ---------------- RAG-EVAL CONFIGURATION LIST GET --------------- ###
@configuration_router.get(
    "/",
    response_model=list[RagEvalConfigurationRead],
)
async def list_configurations(
    session: SessionDep,
    _admin: AdminDep,
    page: Page,
) -> list[RagEvalConfigurationRead]:
    """
    List all RAG evaluation configurations.
    Args:
        session: The database session.
        _admin: The admin performing the action.
        page: Pagination information.
    Returns:
        A list of RAG evaluation configurations.
    """
    return await rag_eval_service.list_rag_eval_configurations_srvc(
        session,
        skip=page["skip"],
        limit=page["limit"],
    )

### ---------------- RAG-EVAL CONFIGURATION GET BY ID -------------- ###
@configuration_router.get(
    "/{id}",
    response_model=RagEvalConfigurationRead,
)
async def get_configuration(
    id: int,
    session: SessionDep,
    _admin: AdminDep,
) -> RagEvalConfigurationRead:
    """
    Get a RAG evaluation configuration by its ID.
    Args:
        id: The ID of the configuration to retrieve.
        session: The database session.
        _admin: The admin performing the action.
    Returns:
        The RAG evaluation configuration with the specified ID.
    Raises:
        HTTPException: If the configuration is not found.
    """
    try:
        return await rag_eval_service.get_rag_eval_configuration_srvc(id, session)
    except ValueError as exc:
        _raise_service_error(exc)

### ----------------- RAG-EVAL CONFIGURATION UPDATE ---------------- ###
@configuration_router.patch(
    "/{id}",
    response_model=RagEvalConfigurationRead,
)
async def update_configuration(
    id: int,
    data: RagEvalConfigurationUpdateRequest,
    session: SessionDep,
    admin: AdminDep,
) -> RagEvalConfigurationRead:
    """
    Update a RAG evaluation configuration by its ID.
    Args:
        id: The ID of the configuration to update.
        data: The update data for the configuration.
        session: The database session.
        admin: The admin performing the action.
    Returns:
        The updated RAG evaluation configuration.
    Raises:
        HTTPException: If the configuration is not found or if there are
        validation errors in the input data.
    """
    try:
        return await rag_eval_service.update_rag_eval_configuration_srvc(
            id,
            data,
            session,
            admin,
        )
    except ValueError as exc:
        _raise_service_error(exc)

### ----------------- RAG-EVAL CONFIGURATION DELETE ---------------- ###
@configuration_router.delete(
    "/{id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_configuration(
    id: int,
    session: SessionDep,
    _admin: AdminDep,
) -> None:
    """
    Delete a RAG evaluation configuration by its ID.
    Args:
        id: The ID of the configuration to delete.
        session: The database session.
        _admin: The admin performing the action.
    Returns:
        None
    Raises:
        HTTPException: If the configuration is not found or if it cannot 
        be deleted.
    """
    try:
        await rag_eval_service.delete_rag_eval_configuration_srvc(id, session)
    except ValueError as exc:
        _raise_service_error(exc)

### ------------------------- RAG-RUN POST ------------------------- ###
@run_router.post(
    "/",
    response_model=RagEvalRunRead,
    status_code=status.HTTP_202_ACCEPTED,
)
async def enqueue_run(
    data: RagEvalRunEnqueueRequest, #has the config id
    session: SessionDep,
    _admin: AdminDep,
) -> RagEvalRunRead:
    """
    Enqueue a RAG evaluation run for the specified configuration ID to the 
    RAG evaluation coordinator.
    Args:
        data: The request containing the configuration ID to enqueue.
        session: The database session.
        _admin: The admin performing the action.
    Returns:
        The enqueued RAG evaluation run.
    Raises:
        HTTPException: If the configuration is not found or if there are
        validation errors in the input data.
    """
    try:
        return await rag_eval_service.enqueue_rag_eval_run_srvc(
            data.configuration_id,
            session,
        )
    except ValueError as exc:
        _raise_service_error(exc)

### ------------------------- RAG-RUN LIST ------------------------- ###
@run_router.get("/", response_model=list[RagEvalRunRead])
async def list_runs(
    session: SessionDep,
    _admin: AdminDep,
    page: Page,
    configuration_id: int | None = None,
    status: RagEvalRunStatus | None = None,
) -> list[RagEvalRunRead]:
    """
    List RAG evaluation runs with optional filtering by configuration 
    ID and status.
    Args:
        session: The database session.
        _admin: The admin performing the action.
        page: Pagination information.
        configuration_id: Optional; filter runs by this configuration ID.
        status: Optional; filter runs by this status.
    Returns:
        A list of RAG evaluation runs matching the specified filters.
    Raises:
        HTTPException: If there are validation errors in the input data.
    """
    return await rag_eval_service.list_rag_eval_runs_srvc(
        session,
        skip=page["skip"],
        limit=page["limit"],
        configuration_id=configuration_id,
        status=status,
    )

### ------------------------- RAG-RUN GET BY ID -------------------- ###
# (carries the results of the run, if completed)
@run_router.get("/{id}", response_model=RagEvalRunDetailRead)
async def get_run(
    id: int,
    session: SessionDep,
    _admin: AdminDep,
) -> RagEvalRunDetailRead:
    """
    Get a RAG evaluation run by its ID.
    Args:
        id: The ID of the run to retrieve.
        session: The database session.
        _admin: The admin performing the action.
    Returns:
        The RAG evaluation run with the specified ID.
    Raises:
        HTTPException: If the run is not found.
    """
    try:
        return await rag_eval_service.get_rag_eval_run_srvc(id, session)
    except ValueError as exc:
        _raise_service_error(exc)

### ----------------------- RAG-RUN CANCEL POST -------------------- ###
@run_router.post("/{id}/cancel", response_model=RagEvalRunRead)
async def cancel_run(
    id: int,
    session: SessionDep,
    _admin: AdminDep,
) -> RagEvalRunRead:
    """
    Cancel a RAG evaluation run by its ID.
    Args:
        id: The ID of the run to cancel.
        session: The database session.
        _admin: The admin performing the action.
    Returns:
        The RAG evaluation run after the cancellation request has been
        processed.
    """
    try:
        return await rag_eval_service.cancel_rag_eval_run_srvc(id, session)
    except ValueError as exc:
        _raise_service_error(exc)

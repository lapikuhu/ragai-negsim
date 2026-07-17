"""Admin-only HTTP API for RAG evaluation configurations and runs."""

from typing import Literal, NoReturn

from fastapi import APIRouter, HTTPException, status
from pydantic import ValidationError

from app.core.dependencies import AdminDep, Page, SessionDep
from app.schemas.rag_eval_schemas import (
    RagEvalConfigurationCreateRequest,
    RagEvalConfigurationRead,
    RagEvalConfigurationUpdateRequest,
    RagEvalRunDetailRead,
    RagEvalRunRead,
)
from app.services import rag_eval_service


RagEvalRunStatus = Literal[
    "queued",
    "running",
    "completed",
    "failed",
    "cancelled",
]

configuration_router = APIRouter(
    prefix="/rag-eval-configurations",
    tags=["rag-eval"],
)
run_router = APIRouter(prefix="/rag-eval-runs", tags=["rag-eval"])

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


def _safe_validation_details(exc: ValidationError) -> list[dict[str, object]]:
    """Return JSON-safe validation details without inputs or exception contexts."""
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
    """Map known service-domain failures without exposing implementation errors."""
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
    try:
        return await rag_eval_service.create_rag_eval_configuration_srvc(
            data,
            session,
            admin,
        )
    except ValueError as exc:
        _raise_service_error(exc)


@configuration_router.get(
    "/",
    response_model=list[RagEvalConfigurationRead],
)
async def list_configurations(
    session: SessionDep,
    _admin: AdminDep,
    page: Page,
) -> list[RagEvalConfigurationRead]:
    return await rag_eval_service.list_rag_eval_configurations_srvc(
        session,
        skip=page["skip"],
        limit=page["limit"],
    )


@configuration_router.get(
    "/{id}",
    response_model=RagEvalConfigurationRead,
)
async def get_configuration(
    id: int,
    session: SessionDep,
    _admin: AdminDep,
) -> RagEvalConfigurationRead:
    try:
        return await rag_eval_service.get_rag_eval_configuration_srvc(id, session)
    except ValueError as exc:
        _raise_service_error(exc)


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
    try:
        return await rag_eval_service.update_rag_eval_configuration_srvc(
            id,
            data,
            session,
            admin,
        )
    except ValueError as exc:
        _raise_service_error(exc)


@configuration_router.delete(
    "/{id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_configuration(
    id: int,
    session: SessionDep,
    _admin: AdminDep,
) -> None:
    try:
        await rag_eval_service.delete_rag_eval_configuration_srvc(id, session)
    except ValueError as exc:
        _raise_service_error(exc)


@configuration_router.post(
    "/{id}/runs",
    response_model=RagEvalRunRead,
    status_code=status.HTTP_202_ACCEPTED,
)
async def enqueue_run(
    id: int,
    session: SessionDep,
    _admin: AdminDep,
) -> RagEvalRunRead:
    try:
        return await rag_eval_service.enqueue_rag_eval_run_srvc(id, session)
    except ValueError as exc:
        _raise_service_error(exc)


@run_router.get("/", response_model=list[RagEvalRunRead])
async def list_runs(
    session: SessionDep,
    _admin: AdminDep,
    page: Page,
    configuration_id: int | None = None,
    status: RagEvalRunStatus | None = None,
) -> list[RagEvalRunRead]:
    return await rag_eval_service.list_rag_eval_runs_srvc(
        session,
        skip=page["skip"],
        limit=page["limit"],
        configuration_id=configuration_id,
        status=status,
    )


@run_router.get("/{id}", response_model=RagEvalRunDetailRead)
async def get_run(
    id: int,
    session: SessionDep,
    _admin: AdminDep,
) -> RagEvalRunDetailRead:
    try:
        return await rag_eval_service.get_rag_eval_run_srvc(id, session)
    except ValueError as exc:
        _raise_service_error(exc)


@run_router.post("/{id}/cancel", response_model=RagEvalRunRead)
async def cancel_run(
    id: int,
    session: SessionDep,
    _admin: AdminDep,
) -> RagEvalRunRead:
    try:
        return await rag_eval_service.cancel_rag_eval_run_srvc(id, session)
    except ValueError as exc:
        _raise_service_error(exc)

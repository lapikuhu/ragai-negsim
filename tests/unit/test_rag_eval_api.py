from datetime import datetime, timezone

import pytest

from app.core import dependencies


def _configuration_payload() -> dict:
    return {
        "name": "evaluation baseline",
        "chunking": {
            "strategy": "recursive",
            "chunk_size": 1000,
            "chunk_overlap": 200,
        },
        "rag": {
            "strategy": "crag",
            "retrieval_embedding_model": "text-embedding-3-small",
            "top_k": 4,
            "reranker": "cross_encoder",
            "top_n": 3,
            "rewrite_limit": 2,
            **{
                name: {"provider": "openai", "model": "gpt-4o-mini"}
                for name in (
                    "document_grader",
                    "query_rewriter",
                    "answer_generator",
                    "hallucination_grader",
                    "answer_grader",
                    "fallback_generator",
                )
            },
        },
        "metrics": {
            "k": 3,
            "ragas_judge": {
                "provider": "openai",
                "model": "gpt-4o-mini",
            },
            "judge_embedding_model": "text-embedding-3-small",
        },
    }


def _configuration_read(configuration_id: int = 7) -> dict:
    now = datetime.now(timezone.utc)
    return {
        "id": configuration_id,
        "created_by_user_id": 1,
        "last_edit_by_user_id": None,
        "created_at": now,
        "last_updated": now,
        **_configuration_payload(),
    }


def _run_read(
    run_id: int = 11,
    *,
    configuration_id: int = 7,
    status: str = "queued",
) -> dict:
    now = datetime.now(timezone.utc)
    terminal = status in {"completed", "failed", "cancelled"}
    return {
        "id": run_id,
        "configuration_id": configuration_id,
        "status": status,
        "stage": "finished" if terminal else "queued",
        "progress": 100.0 if terminal else 0.0,
        "completed_examples": 80 if status == "completed" else 0,
        "total_examples": 80,
        "queued_at": now,
        "started_at": None,
        "completed_at": now if terminal else None,
        "cancel_requested": status == "cancelled",
        "cancellation_requested_at": now if status == "cancelled" else None,
        "failure_code": None,
        "failure_message": None,
        "configuration_snapshot": _configuration_payload(),
        "suite_version": "rag-eval-v1",
        "suite_content_hash": "abc123",
        "resolved_pipeline_snapshot": {},
        "overall_metrics": {},
        "category_metrics": {},
    }


def _authorize_admin(override_current_user, override_session, allow_roles):
    override_current_user(username="admin", roles=["admin"])
    override_session()
    allow_roles("admin")


def test_openapi_exposes_only_target_rag_eval_paths(api_client):
    paths = api_client.get("/openapi.json").json()["paths"]

    assert {
        "/rag-eval-configurations/",
        "/rag-eval-configurations/{id}",
        "/rag-eval-configurations/{id}/runs",
        "/rag-eval-runs/",
        "/rag-eval-runs/{id}",
        "/rag-eval-runs/{id}/cancel",
    }.issubset(paths)
    assert not any(path.startswith("/rag-eval-pair-profiles") for path in paths)
    assert paths["/rag-eval-configurations/"]["post"]["responses"]["201"]
    assert paths["/rag-eval-configurations/{id}/runs"]["post"][
        "responses"
    ]["202"]
    assert (
        "requestBody"
        not in paths["/rag-eval-configurations/{id}/runs"]["post"]
    )


def test_rag_eval_routes_require_admin(
    monkeypatch,
    api_client,
    override_current_user,
    override_session,
):
    from app.services import rag_eval_service

    async def fake_list(*_args, **_kwargs):
        pytest.fail("service must not run without admin authorization")

    override_current_user(username="teacher", roles=["teacher"])
    override_session()

    async def deny_admin(_user, _role, _session):
        return False

    monkeypatch.setattr(dependencies, "user_has_role", deny_admin)
    monkeypatch.setattr(
        rag_eval_service,
        "list_rag_eval_configurations_srvc",
        fake_list,
    )

    response = api_client.get("/rag-eval-configurations/")

    assert response.status_code == 403
    assert response.json()["detail"] == "Admin role required"


def test_configuration_create_uses_typed_request_and_returns_201(
    monkeypatch,
    api_client,
    override_current_user,
    override_session,
    allow_roles,
):
    from app.schemas.rag_eval_schemas import RagEvalConfigurationCreateRequest
    from app.services import rag_eval_service

    _authorize_admin(override_current_user, override_session, allow_roles)
    captured = []

    async def fake_create(data, _session, admin):
        captured.append((data, admin))
        return _configuration_read()

    monkeypatch.setattr(
        rag_eval_service,
        "create_rag_eval_configuration_srvc",
        fake_create,
    )

    response = api_client.post(
        "/rag-eval-configurations/",
        json=_configuration_payload(),
    )

    assert response.status_code == 201
    assert response.json()["id"] == 7
    assert isinstance(captured[0][0], RagEvalConfigurationCreateRequest)
    assert captured[0][0].rag.strategy == "crag"
    assert captured[0][1].username == "admin"


def test_configuration_create_rejects_invalid_discriminated_payload_before_service(
    monkeypatch,
    api_client,
    override_current_user,
    override_session,
    allow_roles,
):
    from app.services import rag_eval_service

    _authorize_admin(override_current_user, override_session, allow_roles)

    async def fake_create(*_args, **_kwargs):
        pytest.fail("invalid request must not reach service")

    monkeypatch.setattr(
        rag_eval_service,
        "create_rag_eval_configuration_srvc",
        fake_create,
    )
    payload = _configuration_payload()
    payload["rag"] = {
        "strategy": "graphrag",
        "retrieval_embedding_model": "text-embedding-3-small",
        "top_k": 4,
    }

    response = api_client.post("/rag-eval-configurations/", json=payload)

    assert response.status_code == 422


def test_configuration_patch_maps_merged_schema_validation_to_safe_422(
    monkeypatch,
    api_client,
    override_current_user,
    override_session,
    allow_roles,
):
    from app.schemas.rag_eval_schemas import (
        apply_rag_eval_configuration_patch,
    )
    from app.services import rag_eval_service

    _authorize_admin(override_current_user, override_session, allow_roles)

    async def fake_update(_configuration_id, data, _session, _admin):
        return apply_rag_eval_configuration_patch(
            _configuration_payload(),
            data,
        )

    monkeypatch.setattr(
        rag_eval_service,
        "update_rag_eval_configuration_srvc",
        fake_update,
    )
    patched_rag = _configuration_payload()["rag"]
    patched_rag["top_n"] = 2

    response = api_client.patch(
        "/rag-eval-configurations/7",
        json={"rag": patched_rag},
    )

    assert response.status_code == 422
    details = response.json()["detail"]
    assert details == [
        {
            "type": "value_error",
            "loc": ["body"],
            "msg": (
                "Value error, metrics.k must be less than or equal to rag.top_n"
            ),
        }
    ]
    assert "input" not in details[0]
    assert "ctx" not in details[0]
    assert "url" not in details[0]


def test_configuration_read_update_delete_and_pagination(
    monkeypatch,
    api_client,
    override_current_user,
    override_session,
    allow_roles,
):
    from app.schemas.rag_eval_schemas import RagEvalConfigurationUpdateRequest
    from app.services import rag_eval_service

    _authorize_admin(override_current_user, override_session, allow_roles)
    calls = []

    async def fake_list(_session, *, skip, limit):
        calls.append(("list", skip, limit))
        return [_configuration_read()]

    async def fake_get(configuration_id, _session):
        calls.append(("get", configuration_id))
        return _configuration_read(configuration_id)

    async def fake_update(configuration_id, data, _session, admin):
        calls.append(("update", configuration_id, data, admin.id))
        result = _configuration_read(configuration_id)
        result["name"] = data.name
        return result

    async def fake_delete(configuration_id, _session):
        calls.append(("delete", configuration_id))

    monkeypatch.setattr(
        rag_eval_service, "list_rag_eval_configurations_srvc", fake_list
    )
    monkeypatch.setattr(
        rag_eval_service, "get_rag_eval_configuration_srvc", fake_get
    )
    monkeypatch.setattr(
        rag_eval_service, "update_rag_eval_configuration_srvc", fake_update
    )
    monkeypatch.setattr(
        rag_eval_service, "delete_rag_eval_configuration_srvc", fake_delete
    )

    listed = api_client.get("/rag-eval-configurations/?skip=5&limit=2")
    fetched = api_client.get("/rag-eval-configurations/7")
    updated = api_client.patch(
        "/rag-eval-configurations/7",
        json={"name": "renamed evaluation"},
    )
    deleted = api_client.delete("/rag-eval-configurations/7")

    assert listed.status_code == 200
    assert [item["id"] for item in listed.json()] == [7]
    assert fetched.status_code == 200
    assert updated.status_code == 200
    assert updated.json()["name"] == "renamed evaluation"
    assert deleted.status_code == 204
    assert deleted.content == b""
    assert isinstance(calls[2][2], RagEvalConfigurationUpdateRequest)
    assert calls == [
        ("list", 5, 2),
        ("get", 7),
        calls[2],
        ("delete", 7),
    ]


def test_enqueue_has_no_body_and_returns_202(
    monkeypatch,
    api_client,
    override_current_user,
    override_session,
    allow_roles,
):
    from app.services import rag_eval_service

    _authorize_admin(override_current_user, override_session, allow_roles)
    calls = []

    async def fake_enqueue(configuration_id, _session):
        calls.append(configuration_id)
        return _run_read(configuration_id=configuration_id)

    monkeypatch.setattr(
        rag_eval_service,
        "enqueue_rag_eval_run_srvc",
        fake_enqueue,
    )

    response = api_client.post("/rag-eval-configurations/7/runs")

    assert response.status_code == 202
    assert response.json()["status"] == "queued"
    assert calls == [7]


def test_run_list_detail_cancel_filters_and_pagination(
    monkeypatch,
    api_client,
    override_current_user,
    override_session,
    allow_roles,
):
    from app.services import rag_eval_service

    _authorize_admin(override_current_user, override_session, allow_roles)
    calls = []

    async def fake_list(
        _session,
        *,
        skip,
        limit,
        configuration_id,
        status,
    ):
        calls.append(("list", skip, limit, configuration_id, status))
        return [_run_read(status=status)]

    async def fake_get(run_id, _session):
        calls.append(("get", run_id))
        return {**_run_read(run_id), "query_results": []}

    async def fake_cancel(run_id, _session):
        calls.append(("cancel", run_id))
        return _run_read(run_id, status="cancelled")

    monkeypatch.setattr(rag_eval_service, "list_rag_eval_runs_srvc", fake_list)
    monkeypatch.setattr(rag_eval_service, "get_rag_eval_run_srvc", fake_get)
    monkeypatch.setattr(rag_eval_service, "cancel_rag_eval_run_srvc", fake_cancel)

    listed = api_client.get(
        "/rag-eval-runs/?configuration_id=7&status=completed&skip=3&limit=4"
    )
    detailed = api_client.get("/rag-eval-runs/11")
    cancelled = api_client.post("/rag-eval-runs/11/cancel")

    assert listed.status_code == 200
    assert listed.json()[0]["status"] == "completed"
    assert detailed.status_code == 200
    assert detailed.json()["query_results"] == []
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "cancelled"
    assert calls == [
        ("list", 3, 4, 7, "completed"),
        ("get", 11),
        ("cancel", 11),
    ]


def test_run_list_rejects_illegal_status_before_service(
    monkeypatch,
    api_client,
    override_current_user,
    override_session,
    allow_roles,
):
    from app.services import rag_eval_service

    _authorize_admin(override_current_user, override_session, allow_roles)

    async def fake_list(*_args, **_kwargs):
        pytest.fail("invalid status must not reach service")

    monkeypatch.setattr(rag_eval_service, "list_rag_eval_runs_srvc", fake_list)

    response = api_client.get("/rag-eval-runs/?status=exploded")

    assert response.status_code == 422


@pytest.mark.parametrize(
    ("method", "path", "service_name", "message", "expected_status"),
    [
        (
            "get",
            "/rag-eval-configurations/404",
            "get_rag_eval_configuration_srvc",
            "RAG evaluation configuration not found",
            404,
        ),
        (
            "post",
            "/rag-eval-configurations/",
            "create_rag_eval_configuration_srvc",
            "RAG evaluation configuration name already exists",
            409,
        ),
        (
            "delete",
            "/rag-eval-configurations/7",
            "delete_rag_eval_configuration_srvc",
            "Cannot delete RAG evaluation configuration referenced by evaluation runs",
            409,
        ),
        (
            "post",
            "/rag-eval-runs/11/cancel",
            "cancel_rag_eval_run_srvc",
            "Cannot cancel a finished RAG evaluation run",
            409,
        ),
    ],
)
def test_service_domain_errors_map_to_404_or_409(
    monkeypatch,
    api_client,
    override_current_user,
    override_session,
    allow_roles,
    method,
    path,
    service_name,
    message,
    expected_status,
):
    from app.services import rag_eval_service

    _authorize_admin(override_current_user, override_session, allow_roles)

    async def fail(*_args, **_kwargs):
        raise ValueError(message)

    monkeypatch.setattr(rag_eval_service, service_name, fail)
    request = getattr(api_client, method)
    kwargs = {"json": _configuration_payload()} if service_name.startswith("create") else {}

    response = request(path, **kwargs)

    assert response.status_code == expected_status
    assert response.json()["detail"] == message


def test_unrecognized_service_error_is_sanitized(
    monkeypatch,
    api_client,
    override_current_user,
    override_session,
    allow_roles,
):
    from app.services import rag_eval_service

    _authorize_admin(override_current_user, override_session, allow_roles)

    async def fail(*_args, **_kwargs):
        raise ValueError(
            "postgresql://internal-user:secret@db/evals: duplicate key detail"
        )

    monkeypatch.setattr(
        rag_eval_service,
        "cancel_rag_eval_run_srvc",
        fail,
    )

    response = api_client.post("/rag-eval-runs/11/cancel")

    assert response.status_code == 409
    assert response.json()["detail"] == (
        "RAG evaluation operation conflicts with current state"
    )

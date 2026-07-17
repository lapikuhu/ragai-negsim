from copy import deepcopy
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest


@pytest.mark.asyncio
async def test_configuration_crud_uses_strict_schemas_and_user_audit_fields(monkeypatch):
    from app.schemas.rag_eval_schemas import (
        RagEvalConfigurationCreateRequest,
        RagEvalConfigurationUpdateRequest,
    )
    from app.services import rag_eval_service

    payload = {
        "name": " target ",
        "chunking": {"strategy": "recursive"},
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
            "ragas_judge": {"provider": "openai", "model": "gpt-4o-mini"},
            "judge_embedding_model": "text-embedding-3-small",
        },
    }
    created_inputs = []
    updated_inputs = []
    configuration = SimpleNamespace(
        id=3,
        created_by_user_id=11,
        last_edit_by_user_id=None,
        created_at=datetime.now(timezone.utc),
        last_updated=datetime.now(timezone.utc),
        **RagEvalConfigurationCreateRequest.model_validate(payload).model_dump(
            mode="json"
        ),
    )

    async def create(data, _session):
        created_inputs.append(data)
        return configuration

    async def get(_configuration_id, _session):
        return configuration

    async def update(active, data, _session):
        updated_inputs.append(data)
        active.name = data.name
        active.last_edit_by_user_id = data.last_edit_by_user_id
        return active

    monkeypatch.setattr(
        rag_eval_service.rag_eval_repo, "create_rag_eval_configuration", create
    )
    monkeypatch.setattr(
        rag_eval_service.rag_eval_repo, "get_rag_eval_configuration_by_id", get
    )
    monkeypatch.setattr(
        rag_eval_service.rag_eval_repo, "update_rag_eval_configuration", update
    )

    await rag_eval_service.create_rag_eval_configuration_srvc(
        RagEvalConfigurationCreateRequest.model_validate(payload),
        object(),
        SimpleNamespace(id=11),
    )
    await rag_eval_service.update_rag_eval_configuration_srvc(
        3,
        RagEvalConfigurationUpdateRequest(name="renamed"),
        object(),
        SimpleNamespace(id=12),
    )

    assert created_inputs[0].created_by_user_id == 11
    assert created_inputs[0].name == "target"
    assert updated_inputs[0].last_edit_by_user_id == 12
    assert updated_inputs[0].name == "renamed"


@pytest.mark.asyncio
async def test_configuration_read_list_and_delete_use_target_repository(monkeypatch):
    from app.services import rag_eval_service

    configurations = [
        SimpleNamespace(id=1, name="first"),
        SimpleNamespace(id=2, name="second"),
    ]
    deleted = []

    async def get(configuration_id, _session):
        return next(
            (item for item in configurations if item.id == configuration_id),
            None,
        )

    async def list_configurations(_session, **values):
        assert values == {"skip": 10, "limit": 2}
        return configurations

    async def delete(configuration, _session):
        deleted.append(configuration.id)

    monkeypatch.setattr(
        rag_eval_service.rag_eval_repo,
        "get_rag_eval_configuration_by_id",
        get,
    )
    monkeypatch.setattr(
        rag_eval_service.rag_eval_repo,
        "list_rag_eval_configurations",
        list_configurations,
    )
    monkeypatch.setattr(
        rag_eval_service.rag_eval_repo,
        "delete_rag_eval_configuration",
        delete,
    )
    monkeypatch.setattr(
        rag_eval_service,
        "_configuration_read",
        lambda value: value,
    )

    assert (
        await rag_eval_service.get_rag_eval_configuration_srvc(1, object())
    ).name == "first"
    assert [
        item.id
        for item in await rag_eval_service.list_rag_eval_configurations_srvc(
            object(), skip=10, limit=2
        )
    ] == [1, 2]
    await rag_eval_service.delete_rag_eval_configuration_srvc(2, object())

    assert deleted == [2]


@pytest.mark.asyncio
async def test_enqueue_snapshots_normalized_configuration_and_suite_then_wakes(monkeypatch):
    from app.services import rag_eval_service

    snapshot = {
        "name": "immutable",
        "chunking": {"strategy": "recursive"},
        "rag": {"strategy": "crag"},
        "metrics": {"k": 3},
    }
    configuration = SimpleNamespace(
        id=4,
        name="immutable",
        chunking=snapshot["chunking"],
        rag=snapshot["rag"],
        metrics=snapshot["metrics"],
    )
    corpus = SimpleNamespace(
        examples=tuple(range(80)),
        suite_version="rag-eval-v1",
        suite_content_hash="abc123",
    )
    captured = []

    async def get(_configuration_id, _session):
        return configuration

    async def enqueue(active, **values):
        captured.append(
            (
                deepcopy(active.chunking),
                deepcopy(active.rag),
                deepcopy(active.metrics),
                values,
            )
        )
        return SimpleNamespace(id=9, status="queued")

    class Coordinator:
        def __init__(self):
            self.wakes = 0

        def wake(self):
            self.wakes += 1

    coordinator = Coordinator()
    monkeypatch.setattr(
        rag_eval_service.rag_eval_repo, "get_rag_eval_configuration_by_id", get
    )
    monkeypatch.setattr(rag_eval_service.rag_eval_repo, "enqueue_rag_eval_run", enqueue)
    monkeypatch.setattr(rag_eval_service, "_run_read", lambda value: value)

    await rag_eval_service.enqueue_rag_eval_run_srvc(
        4,
        object(),
        coordinator=coordinator,
        corpus_factory=lambda: corpus,
    )
    configuration.rag["strategy"] = "graphrag"

    assert captured[0][1]["strategy"] == "crag"
    assert captured[0][3]["suite_version"] == "rag-eval-v1"
    assert captured[0][3]["suite_content_hash"] == "abc123"
    assert captured[0][3]["total_examples"] == 80
    assert coordinator.wakes == 1


@pytest.mark.asyncio
async def test_queued_cancellation_uses_repository_and_wakes_coordinator(monkeypatch):
    from app.services import rag_eval_service

    run = SimpleNamespace(id=5, status="queued")
    calls = []

    async def get(_run_id, _session):
        return run

    async def cancel(active, _session):
        calls.append(active.id)
        active.status = "cancelled"
        return active

    class Coordinator:
        def wake(self):
            calls.append("wake")

    monkeypatch.setattr(rag_eval_service.rag_eval_repo, "get_rag_eval_run_by_id", get)
    monkeypatch.setattr(
        rag_eval_service.rag_eval_repo, "request_rag_eval_run_cancel", cancel
    )
    monkeypatch.setattr(rag_eval_service, "_run_read", lambda value: value)

    result = await rag_eval_service.cancel_rag_eval_run_srvc(
        5, object(), coordinator=Coordinator()
    )

    assert result.status == "cancelled"
    assert calls == [5, "wake"]


@pytest.mark.asyncio
async def test_service_lifecycle_hooks_start_and_await_shutdown():
    from app.services import rag_eval_service

    events = []

    class Coordinator:
        async def start(self):
            events.append("start")

        async def stop(self):
            events.append("stop")

    coordinator = Coordinator()
    await rag_eval_service.startup_rag_eval_coordinator_srvc(coordinator)
    await rag_eval_service.shutdown_rag_eval_coordinator_srvc(coordinator)

    assert events == ["start", "stop"]

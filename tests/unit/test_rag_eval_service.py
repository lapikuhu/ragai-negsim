import pytest

from app.airag.evaluation.eval_models import EvalRunResult
from app.schemas.rag_eval_schemas import RagEvalRunStartRequest


def test_run_start_request_snapshots_model_selection():
    request = RagEvalRunStartRequest(
        k=3,
        answer_llm_provider="ollama",
        answer_llm_model="qwen2.5:3b",
        judge_llm_provider="openai",
        judge_llm_model="gpt-4o-mini",
        judge_embedding_model="text-embedding-3-small",
    )

    assert request.k == 3
    assert request.answer_llm_provider == "ollama"
    assert request.answer_llm_model == "qwen2.5:3b"
    assert request.judge_llm_provider == "openai"
    assert request.judge_llm_model == "gpt-4o-mini"
    assert request.judge_embedding_model == "text-embedding-3-small"


@pytest.mark.asyncio
async def test_interrupted_graphrag_run_deletes_its_temporary_scope_before_failing(monkeypatch):
    from app.services import rag_eval_service

    run = type(
        "Run",
        (),
        {"id": 42, "status": "running", "rag_profile_snapshot": {"strategy": "graphrag"}},
    )()
    events = []

    class Session:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return False

    async def fake_list(_session, **_kwargs):
        return [run]

    async def fake_cleanup(run_id):
        events.append(("cleanup", run_id))

    async def fake_mark_failed(failed_run, _detail, _session):
        events.append(("failed", failed_run.id))

    monkeypatch.setattr(rag_eval_service, "AsyncSessionLocal", lambda: Session())
    monkeypatch.setattr(rag_eval_service.rag_eval_repo, "list_rag_eval_runs", fake_list)
    monkeypatch.setattr(rag_eval_service, "cleanup_rag_eval_graph_scope", fake_cleanup)
    monkeypatch.setattr(rag_eval_service.rag_eval_repo, "mark_rag_eval_run_failed", fake_mark_failed)

    await rag_eval_service.fail_interrupted_rag_eval_runs_srvc()

    assert events == [("cleanup", 42), ("failed", 42)]


@pytest.mark.asyncio
async def test_interrupted_graphrag_run_stays_active_when_temporary_scope_cleanup_fails(monkeypatch):
    from app.services import rag_eval_service

    run = type(
        "Run",
        (),
        {"id": 42, "status": "running", "stage": "building_graph", "rag_profile_snapshot": {"strategy": "graphrag"}},
    )()
    events = []

    class Session:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return False

    async def fake_list(_session, **_kwargs):
        return [run]

    async def fail_cleanup(_run_id):
        raise RuntimeError("Neo4j unavailable")

    async def fake_update(active_run, _session, **values):
        events.append(("stage", values["stage"]))
        active_run.stage = values["stage"]
        return active_run

    async def fail_if_marked_failed(*_args):
        raise AssertionError("a graph scope that cannot be cleaned must remain retryable")

    monkeypatch.setattr(rag_eval_service, "AsyncSessionLocal", lambda: Session())
    monkeypatch.setattr(rag_eval_service.rag_eval_repo, "list_rag_eval_runs", fake_list)
    monkeypatch.setattr(rag_eval_service, "cleanup_rag_eval_graph_scope", fail_cleanup)
    monkeypatch.setattr(rag_eval_service.rag_eval_repo, "update_rag_eval_run", fake_update)
    monkeypatch.setattr(rag_eval_service.rag_eval_repo, "mark_rag_eval_run_failed", fail_if_marked_failed)

    await rag_eval_service.fail_interrupted_rag_eval_runs_srvc()

    assert events == [("stage", "cleanup_pending")]


@pytest.mark.asyncio
async def test_execute_run_persists_runtime_stages_then_judging(monkeypatch):
    from app.services import rag_eval_service

    run = type(
        "Run",
        (),
        {
            "id": 42,
            "status": "queued",
            "stage": "queued",
            "cancel_requested": False,
            "rag_profile_snapshot": {"strategy": "crag"},
            "chunking_profile_snapshot": {"strategy": "recursive"},
            "retrieval_config_snapshot": {"embedding_model": "text-embedding-3-small"},
            "answer_generation_model_snapshot": {
                "llm_provider": "ollama",
                "llm_model": "qwen2.5:3b",
                "temperature": 0,
                "prompt_version": "grounded_answer_v1",
            },
            "evaluation_model_snapshot": {
                "llm_provider": "openai",
                "llm_model": "gpt-4o-mini",
                "embedding_model": "text-embedding-3-small",
            },
            "k": 2,
        },
    )()
    stages = []

    class Session:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return False

        async def refresh(self, _run):
            return None

    class Runtime:
        async def run(self, *, stage_callback, **_kwargs):
            await stage_callback("chunking")
            await stage_callback("retrieving")
            return EvalRunResult(k=2, results=(), hit_rate_at_k=0.0, mrr_at_k=0.0)

    class Evaluator:
        async def evaluate(self, _result):
            return type("Ragas", (), {"results": (), "metric_means": {}})()

    async def fake_get_run(_run_id, _session):
        return run

    async def fake_mark_running(active_run, _session):
        active_run.status = "running"
        return active_run

    async def fake_update(active_run, _session, **values):
        active_run.stage = values["stage"]
        stages.append(active_run.stage)
        return active_run

    async def fake_mark_completed(active_run, _session, **_kwargs):
        active_run.status = "completed"
        active_run.stage = "finished"
        stages.append(active_run.stage)
        return active_run

    monkeypatch.setattr(rag_eval_service, "AsyncSessionLocal", lambda: Session())
    monkeypatch.setattr(rag_eval_service.rag_eval_repo, "get_rag_eval_run_by_id", fake_get_run)
    monkeypatch.setattr(rag_eval_service.rag_eval_repo, "mark_rag_eval_run_running", fake_mark_running)
    monkeypatch.setattr(rag_eval_service.rag_eval_repo, "update_rag_eval_run", fake_update)
    monkeypatch.setattr(rag_eval_service.rag_eval_repo, "mark_rag_eval_run_completed", fake_mark_completed)
    monkeypatch.setattr(rag_eval_service, "create_rag_eval_runtime", lambda: Runtime())
    async def fake_generate(result, *, provider, model, should_cancel):
        assert (provider, model) == ("ollama", "qwen2.5:3b")
        assert await should_cancel() is False
        return result

    monkeypatch.setattr(rag_eval_service, "generate_grounded_answers", fake_generate, raising=False)
    monkeypatch.setattr(
        rag_eval_service.RagasEvaluator,
        "from_model_selection",
        lambda *_args: Evaluator(),
    )

    await rag_eval_service._execute_rag_eval_run(42)

    assert stages == ["chunking", "retrieving", "generating_answer", "judging", "finished"]

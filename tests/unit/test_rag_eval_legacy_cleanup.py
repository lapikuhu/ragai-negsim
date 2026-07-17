from __future__ import annotations

import inspect
from pathlib import Path

from app.airag.evaluation import rag_eval_runtime
from app.main import app
from app.models import rag_eval as rag_eval_models
from app.repositories import rag_eval_repo
from app.schemas import rag_eval_schemas
from app.services import rag_eval_service


LEGACY_SCHEMA_NAMES = {
    "RagEvalGraphBuildConfig",
    "RagEvalRetrievalConfig",
    "RagEvalPairProfileBase",
    "RagEvalPairProfileCreateRequest",
    "RagEvalPairProfileCreate",
    "RagEvalPairProfileUpdateRequest",
    "RagEvalPairProfileUpdate",
    "RagEvalPairProfileRead",
    "RagEvalRunCreate",
    "RagEvalRunStartRequest",
    "validate_rag_eval_retrieval_config",
}

LEGACY_REPOSITORY_NAMES = {
    "get_rag_eval_pair_profile_by_id",
    "get_rag_eval_pair_profile_by_name",
    "ensure_rag_eval_pair_profile_name_available",
    "list_rag_eval_pair_profiles",
    "create_rag_eval_pair_profile",
    "rag_eval_pair_profile_has_runs",
    "update_rag_eval_pair_profile",
    "delete_rag_eval_pair_profile",
    "get_active_rag_eval_run",
    "update_rag_eval_run",
    "mark_rag_eval_run_running",
    "create_rag_eval_run",
    "create_rag_eval_query_result",
    "mark_rag_eval_run_completed",
}

LEGACY_SERVICE_NAMES = {
    "create_rag_eval_pair_profile_srvc",
    "list_rag_eval_pair_profiles_srvc",
    "get_rag_eval_pair_profile_srvc",
    "update_rag_eval_pair_profile_srvc",
    "delete_rag_eval_pair_profile_srvc",
    "start_rag_eval_run_srvc",
    "fail_interrupted_rag_eval_runs_srvc",
}


def test_transitional_rag_eval_imports_are_absent():
    assert not hasattr(rag_eval_runtime, "LegacyRagEvalRuntime")
    assert not hasattr(rag_eval_runtime, "create_legacy_rag_eval_runtime")
    assert not hasattr(rag_eval_models, "RagEvalPairProfile")
    assert all(not hasattr(rag_eval_schemas, name) for name in LEGACY_SCHEMA_NAMES)
    assert all(not hasattr(rag_eval_repo, name) for name in LEGACY_REPOSITORY_NAMES)
    assert all(not hasattr(rag_eval_service, name) for name in LEGACY_SERVICE_NAMES)
    assert "pair_profile_id" not in inspect.signature(
        rag_eval_service.list_rag_eval_runs_srvc
    ).parameters


def test_obsolete_evaluation_only_paths_and_routes_are_absent():
    evaluation_root = Path("app/airag/evaluation")
    assert not (evaluation_root / "answer_generation.py").exists()
    assert "make_invoke_runner" not in "\n".join(
        path.read_text(encoding="utf-8")
        for path in evaluation_root.glob("*.py")
    )
    assert not any(
        route.path.startswith("/rag-eval-pair-profiles")
        for route in app.routes
    )

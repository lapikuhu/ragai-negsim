from app.schemas.rag_eval_schemas import RagEvalRunStartRequest


def test_run_start_request_snapshots_model_selection():
    request = RagEvalRunStartRequest(
        k=3,
        llm_provider="openai",
        llm_model="gpt-4o-mini",
        embedding_model="text-embedding-3-small",
    )

    assert request.k == 3
    assert request.llm_provider == "openai"

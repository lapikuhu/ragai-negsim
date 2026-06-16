from langchain_core.callbacks import UsageMetadataCallbackHandler

from app.airag.observability import llm_usage


def test_extend_runnable_config_preserves_callbacks_and_appends_tags():
    handler = UsageMetadataCallbackHandler()
    parent_config = {
        "callbacks": [handler],
        "tags": ["graph:negotiation"],
        "metadata": {"simulation_id": "10"},
    }

    config = llm_usage.extend_runnable_config(
        parent_config,
        tags=["agent:coach", "node:generate"],
        metadata={"purpose": "rolling_evaluation"},
        run_name="coach.generate",
    )

    assert config["callbacks"] == [handler]
    assert config["tags"] == [
        "graph:negotiation",
        "agent:coach",
        "node:generate",
    ]
    assert config["metadata"] == {
        "simulation_id": "10",
        "purpose": "rolling_evaluation",
    }
    assert config["run_name"] == "coach.generate"


def test_summarize_usage_handler_returns_totals_and_models():
    handler = UsageMetadataCallbackHandler()
    handler.usage_metadata = {
        "gpt-4o-mini-2024-07-18": {
            "input_tokens": 8,
            "output_tokens": 10,
            "total_tokens": 18,
            "input_token_details": {"cache_read": 0},
            "output_token_details": {"reasoning": 0},
        },
        "gpt-4o-2024-08-06": {
            "input_tokens": 20,
            "output_tokens": 5,
            "total_tokens": 25,
            "input_token_details": {"cache_read": 2},
            "output_token_details": {"reasoning": 1},
        },
    }

    summary = llm_usage.summarize_usage_handler(handler)

    assert summary["totals"] == {
        "input_tokens": 28,
        "output_tokens": 15,
        "total_tokens": 43,
    }
    assert summary["models"]["gpt-4o-mini-2024-07-18"]["total_tokens"] == 18
    assert summary["models"]["gpt-4o-2024-08-06"]["input_token_details"] == {
        "cache_read": 2
    }

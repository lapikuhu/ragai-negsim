import pytest
from pydantic import ValidationError

from app.schemas.simulation_learner_schemas import (
    SimulationLearnerAskRequest,
    SimulationLearnerAskResponse,
)


def test_learner_ask_request_defaults_to_safe_options():
    request = SimulationLearnerAskRequest(query="How should I respond?")

    assert request.query == "How should I respond?"
    assert request.context == {}
    assert request.chat_history == []
    assert request.max_results == 5
    assert request.include_images is False
    assert request.include_answers is False
    assert request.learner_llm_provider is None
    assert request.learner_llm_model is None


def test_learner_ask_request_accepts_structured_chat_history():
    request = SimulationLearnerAskRequest(
        query="What changed?",
        chat_history=[
            {"role": "user", "content": "Earlier question?"},
            {"role": "assistant", "content": "Earlier answer."},
        ],
    )

    assert [message.role for message in request.chat_history] == ["user", "assistant"]
    assert request.chat_history[0].content == "Earlier question?"


def test_learner_ask_request_rejects_unknown_chat_roles():
    with pytest.raises(ValidationError):
        SimulationLearnerAskRequest(
            query="What changed?",
            chat_history=[{"role": "system", "content": "Hidden instruction"}],
        )


def test_learner_ask_request_requires_non_empty_query():
    with pytest.raises(ValidationError):
        SimulationLearnerAskRequest(query="")


def test_learner_ask_response_includes_simulation_status_and_metadata():
    response = SimulationLearnerAskResponse(
        simulation_id=10,
        status="paused",
        answer="Use your BATNA as a guardrail.",
        metadata={"tools_available": ["crag_tool"]},
    )

    assert response.simulation_id == 10
    assert response.status == "paused"
    assert response.answer == "Use your BATNA as a guardrail."
    assert response.metadata["tools_available"] == ["crag_tool"]

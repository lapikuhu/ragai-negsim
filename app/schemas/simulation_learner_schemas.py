from datetime import datetime, timezone
from typing import Any, Literal

from sqlmodel import Field, SQLModel


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class SimulationLearnerChatMessage(SQLModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1)


class SimulationLearnerAskRequest(SQLModel):
    """
    Request schema for learner's ask in a simulation.
    Attributes:
        query (str): The learner's query.
        context (dict[str, Any]): Optional context for the query.
        timestamp (datetime): The time of the request.
    """
    query: str = Field(min_length=1, title="Learner's query")
    context: dict[str, Any] = Field(
        default_factory=dict,
        title="Optional context for the query",
    )
    chat_history: list[SimulationLearnerChatMessage] = Field(
        default_factory=list,
        title="Ephemeral learner chat history",
    )
    max_results: int = Field(default=5, ge=1, title="Maximum web search results")
    include_images: bool = Field(default=False, title="Include Tavily images")
    include_answers: bool = Field(default=False, title="Include Tavily answer")
    learner_llm_provider: Literal["openai", "ollama"] | None = None
    learner_llm_model: str | None = None
    timestamp: datetime = Field(default_factory=_utc_now, title="Time of the request")


class SimulationLearnerAskResponse(SQLModel):
    """
    Response schema for learner's ask in a simulation.
    Attributes:
        answer (str): The answer to the learner's query.
        metadata (dict[str, Any]): Optional metadata related to the 
            response.
        timestamp (datetime): The time of the response.
    """
    simulation_id: int
    status: str
    answer: str = Field(min_length=1, title="Answer to the learner's query")
    sources: list[dict[str, Any]] = Field(
        default_factory=list,
        title="Structured source references used by retrieval tools",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        title="Optional metadata related to the response",
    )
    timestamp: datetime = Field(default_factory=_utc_now, title="Time of the response")

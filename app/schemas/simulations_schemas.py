from datetime import datetime
from typing import Any, Literal

from sqlmodel import Field, SQLModel


SimulationStatus = Literal["created", "active", "paused", "completed", "cancelled", "failed"]
SimulationSide = Literal["side_a", "side_b"]


class NegotiationStateSchema(SQLModel):
    current_phase: str | None = None
    user_side: SimulationSide | None = None
    data: dict[str, Any] = Field(default_factory=dict)


class SimulationMessageSchema(SQLModel):
    role: str = Field(min_length=1)
    content: str = Field(min_length=1)
    timestamp: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class SimulationBase(SQLModel):
    name: str = Field(min_length=3, title="Simulation name")
    description: str | None = None


class SimulationCreateRequest(SimulationBase):
    corpus_id: int
    corpus_index_id: int
    rag_profile_id: int
    coach_prompt_id: int | None = None
    counterpart_prompt_id: int | None = None
    evaluator_prompt_id: int | None = None
    session_id: int | None = None
    user_id_participant: int | None = None
    scenario_id: int | None = None
    counter_part_side_persona_id: int | None = None
    user_side: SimulationSide | None = None


class SimulationCreate(SimulationBase):
    user_id_owner: int
    corpus_id: int
    corpus_index_id: int
    rag_profile_id: int
    coach_prompt_id: int | None = None
    counterpart_prompt_id: int | None = None
    evaluator_prompt_id: int | None = None
    session_id: int | None = None
    user_id_participant: int | None = None
    scenario_id: int | None = None
    counter_part_side_persona_id: int | None = None
    user_side: SimulationSide | None = None


class SimulationRead(SimulationBase):
    id: int
    status: str
    session_id: int | None = None
    user_id_owner: int
    user_id_participant: int | None = None
    scenario_id: int | None = None
    corpus_id: int
    corpus_index_id: int
    rag_profile_id: int
    coach_prompt_id: int | None = None
    counterpart_prompt_id: int | None = None
    evaluator_prompt_id: int | None = None
    counter_part_side_persona_id: int | None = None
    user_side: str | None = None
    teacher_reviewed: bool
    teacher_id: int | None = None
    teacher_feedback: str | None = None
    reviewed_at: datetime | None = None
    created_at: datetime
    last_updated: datetime


class SimulationReadWithState(SimulationRead):
    negotiation_state: NegotiationStateSchema = Field(default_factory=NegotiationStateSchema)
    messages: list[SimulationMessageSchema] = Field(default_factory=list)


class SimulationUpdate(SQLModel):
    name: str | None = Field(default=None, min_length=3, title="Simulation name")
    description: str | None = None
    status: SimulationStatus | None = None
    session_id: int | None = None
    user_id_participant: int | None = None
    scenario_id: int | None = None
    corpus_index_id: int | None = None
    coach_prompt_id: int | None = None
    counterpart_prompt_id: int | None = None
    evaluator_prompt_id: int | None = None
    counter_part_side_persona_id: int | None = None
    user_side: SimulationSide | None = None
    negotiation_state: NegotiationStateSchema | None = None
    messages: list[SimulationMessageSchema] | None = None


class SimulationUpdateRequest(SQLModel):
    name: str | None = Field(default=None, min_length=3, title="Simulation name")
    description: str | None = None
    status: SimulationStatus | None = None
    session_id: int | None = None
    user_id_participant: int | None = None
    scenario_id: int | None = None
    corpus_index_id: int | None = None
    coach_prompt_id: int | None = None
    counterpart_prompt_id: int | None = None
    evaluator_prompt_id: int | None = None
    counter_part_side_persona_id: int | None = None
    user_side: SimulationSide | None = None


class SimulationStatusUpdate(SQLModel):
    status: SimulationStatus


class SimulationMessageAppend(SQLModel):
    message: SimulationMessageSchema


class SimulationMessagesReplace(SQLModel):
    messages: list[SimulationMessageSchema] = Field(default_factory=list)


class SimulationNegotiationStateUpdate(SQLModel):
    negotiation_state: NegotiationStateSchema


class SimulationStartRequest(SQLModel):
    side_a: dict[str, Any] = Field(default_factory=dict)
    side_b: dict[str, Any] = Field(default_factory=dict)
    max_turn_count: int = Field(default=12, ge=1, le=100)
    counterpart_llm_provider: Literal["openai", "ollama"] | None = None
    counterpart_llm_model: str | None = None
    evaluator_llm_provider: Literal["openai", "ollama"] | None = None
    evaluator_llm_model: str | None = None


class SimulationTurnRequest(SQLModel):
    message: str = Field(min_length=1)
    current_offer: dict[str, Any] | None = None
    action: Literal["continue", "end"] | None = None


class SimulationTokenUsageSchema(SQLModel):
    simulation_total: int | None = None
    coach_total: int | None = None
    counterpart_latest: int | None = None
    proxy_latest: int | None = None
    evaluator_total: int | None = None


class SimulationTurnResponse(SQLModel):
    simulation_id: int
    status: SimulationStatus
    phase: str | None = None
    should_pause: bool = False
    pause_reason: str | None = None
    messages: list[SimulationMessageSchema] = Field(default_factory=list)
    coach_advice: dict[str, Any] = Field(default_factory=dict)
    final_evaluation: dict[str, Any] = Field(default_factory=dict)
    counterpart_response: str | None = None
    token_usage: SimulationTokenUsageSchema = Field(default_factory=SimulationTokenUsageSchema)


class SimulationProxyTurnRequest(SQLModel):
    persona_id: int | None = None
    duration: Literal["this_turn", "remainder"]


class SimulationProxyTurnResponse(SimulationTurnResponse):
    proxy_response: str
    auto_user_proxy_enabled: bool = False
    user_proxy_persona: dict[str, Any] = Field(default_factory=dict)


class SimulationProxyDisableResponse(SQLModel):
    simulation_id: int
    status: SimulationStatus
    auto_user_proxy_enabled: bool = False
    user_proxy_persona: dict[str, Any] = Field(default_factory=dict)
    messages: list[SimulationMessageSchema] = Field(default_factory=list)


class SimulationTeacherReview(SQLModel):
    teacher_id: int
    teacher_feedback: str | None = None
    teacher_reviewed: bool = True
    reviewed_at: datetime | None = None


class SimulationTeacherReviewRequest(SQLModel):
    teacher_feedback: str = Field(min_length=1)


class SimulationEvaluationListItem(SimulationRead):
    scenario_name: str | None = None
    participant_user_id: int


class SimulationEvaluationListResponse(SQLModel):
    items: list[SimulationEvaluationListItem] = Field(default_factory=list)
    skip: int = 0
    limit: int = 20
    has_more: bool = False


class SimulationReadWithIds(SimulationRead):
    # Mostly redundant because SimulationRead already exposes foreign keys,
    # but useful if you want an explicit relationship-summary convention.
    related_user_ids: list[int] = Field(default_factory=list)

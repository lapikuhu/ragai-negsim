from typing_extensions import NotRequired, TypedDict
from typing import Annotated, Any, Literal
from pydantic import BaseModel, Field
import operator

# local imports
from app.airag.chains.negotiation.negotiation_model import (
	CoachAdvice,
	Confidence,
	Evaluation,
	Offer,
	ParentNegotiationState,
	RetrievalResult,
	Side,
	SideProfile,
)
from app.airag.prompts.neg_prompts.md_loader import COACH_PROMPT

# 
CoachNextMove = Literal[
	"accept",
	"reject",
	"counter",
	"clarify",
	"pause",
	"escalate",
	"unknown",
]

# Position assessment details that the coach will provide to help 
# the user understand their current standing in relation to their 
# goals and walk-away point.
class PositionAssessmentModel(BaseModel):
	"""Validated position assessment matching coach_prompt.md."""

	target_value: str
	reservation_value: str
	current_offer_assessment: str
	zopa_comment: str

# The coach advise model
class CoachAdviceModel(BaseModel):
	"""Validated coach advice matching CoachAdvice."""
	target_side: Side
	summary: str
	position_assessment: PositionAssessmentModel
	risks: list[str] = Field(default_factory=list)
	recommended_next_move: CoachNextMove | str
	suggested_response: str
	reasoning: str
	confidence: Confidence
	missing_information: list[str] = Field(default_factory=list)

# The state schema for the coach graph, which will be used to validate the 
# state.
class CoachGraphState(TypedDict, total=False):
	"""State consumed and produced by the coach graph."""
	session_id: str
	user_id: str
	user_side: Side
	side_a: SideProfile
	side_b: SideProfile
	messages: list[Any]
	phase: str
	active_side: Side
	current_offer: Offer
	offer_history: list[Offer]
	coach_advice: CoachAdvice
	side_a_response: str
	side_b_response: str
	evaluation: Evaluation
	retrieval_result: RetrievalResult
	next_action: str
	turn_count: int
	event_log: NotRequired[Annotated[list[str], operator.add]]

	coach_query: str
	retrieval_context: str
	coach_prompt: str
	coach_validation_error: str
	coach_retry_count: int
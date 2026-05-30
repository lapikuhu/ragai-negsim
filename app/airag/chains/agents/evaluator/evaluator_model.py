from pydantic import BaseModel, Field
from typing import Annotated, Any, Literal
import operator
from typing_extensions import NotRequired, TypedDict

# local imports
from app.airag.chains.negotiation.negotiation_model import (
	CoachAdvice,
	Confidence,
	Evaluation,
	NextAction,
	Offer,
	RetrievalResult,
	Side,
	SideProfile,
)

RiskLevel = Literal["low", "medium", "high"]
DealQuality = Literal["poor", "acceptable", "good", "excellent", "unknown"]
EvaluatorNextBestAction = Literal[
	"call_counterpart",
	"call_coach",
	"call_retriever",
	"ask_user",
	"end",
]

class SideAssessmentModel(BaseModel):
	"""Validated side-specific assessment matching evaluator_prompt.md."""

	position: str
	target_value_check: str
	reservation_value_check: str
	constraint_check: str
	risk_level: RiskLevel


class ZopaAssessmentModel(BaseModel):
	"""Validated ZOPA assessment matching evaluator_prompt.md."""

	zopa_exists: bool | None
	reasoning: str
	confidence: Confidence


class DealQualityModel(BaseModel):
	"""Validated deal quality assessment matching evaluator_prompt.md."""

	for_side_a: DealQuality
	for_side_b: DealQuality
	overall: DealQuality


class EvaluatorResponseModel(BaseModel):
	"""Validated evaluator response matching evaluator_prompt.md."""

	score: float = Field(ge=0.0, le=1.0)
	phase_assessment: str
	side_a_assessment: SideAssessmentModel
	side_b_assessment: SideAssessmentModel
	zopa_assessment: ZopaAssessmentModel
	detected_risks: list[str] = Field(default_factory=list)
	deal_quality: DealQualityModel
	next_best_action: EvaluatorNextBestAction
	reasoning: str
	missing_information: list[str] = Field(default_factory=list)
	confidence: Confidence


class EvaluatorGraphState(TypedDict, total=False):
	"""State consumed and produced by the evaluator graph."""

	session_id: str
	user_id: str
	user_side: Side
	side_a: SideProfile
	side_b: SideProfile
	messages: list[Any]
	phase: str
	active_side: Side
	current_offer: Offer
	offer_history: Annotated[list[Offer], operator.add]
	coach_advice: CoachAdvice
	side_a_response: str
	side_b_response: str
	evaluation: Evaluation
	retrieval_result: RetrievalResult
	next_action: NextAction
	turn_count: int
	event_log: NotRequired[Annotated[list[str], operator.add]]

	evaluator_query: str
	retrieval_context: str
	evaluator_prompt: str
	evaluator_response: dict[str, Any]
	evaluator_validation_error: str
	evaluator_retry_count: int
	missing_information: list[str]
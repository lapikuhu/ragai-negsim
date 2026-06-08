from typing import Annotated, Any, Literal
import operator
from pydantic import BaseModel, Field
from typing_extensions import NotRequired, TypedDict

from app.airag.chains.negotiation.negotiation_model import (
	CoachAdvice,
	Evaluation,
	Offer,
	RetrievalResult,
	Side,
	SideProfile,
)

CounterpartAction = Literal[
	"accept",
	"reject",
	"counter",
	"clarify",
	"stall",
	"reframe",
	"propose_package",
]

RiskLevel = Literal["low", "medium", "high"]


class CounterpartOfferModel(BaseModel):
	"""Validated offer emitted by the counterpart."""

	side: Side
	price: float | None = None
	terms: dict[str, Any] = Field(default_factory=dict)
	raw_text: str


class CounterpartPrivateNotesModel(BaseModel):
	"""Private strategy notes for logging/debugging, not user display."""

	strategy_used: str
	reservation_value_check: str
	target_value_check: str
	risk: RiskLevel


class CounterpartResponseModel(BaseModel):
	"""Validated response matching counterpart_prompt.md."""

	side: Side
	message: str
	action: CounterpartAction
	offer: CounterpartOfferModel
	private_notes: CounterpartPrivateNotesModel


class CounterpartGraphState(TypedDict, total=False):
	"""State consumed and produced by the counterpart graph."""

	simulation_id: str
	app_session_id: int
	session_id: str
	user_id: str
	counterpart_persona: dict[str, Any]
	scenario_public_context: dict[str, Any]
	own_private_context: dict[str, Any]
	user_side: Side
	messages: list[Any]
	phase: str
	active_side: Side
	current_offer: Offer
	offer_history: Annotated[list[Offer], operator.add]
	side_a_response: str
	side_b_response: str
	turn_count: int
	event_log: NotRequired[Annotated[list[str], operator.add]]

	counterpart_side: Side
	counterpart_response: dict[str, Any]
	counterpart_prompt: str
	counterpart_validation_error: str
	counterpart_retry_count: int
	missing_information: list[str]

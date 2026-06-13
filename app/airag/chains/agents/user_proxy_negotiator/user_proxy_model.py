from typing import Annotated, Any
import operator

from pydantic import BaseModel, Field
from typing_extensions import NotRequired, TypedDict

from app.airag.chains.negotiation.negotiation_model import CoachAdvice, Offer, Side


class UserProxyResponseModel(BaseModel):
    """Validated user proxy response."""

    message: str = Field(min_length=1)
    rationale: str = Field(default="")


class UserProxyGraphState(TypedDict, total=False):
    """State consumed and produced by the user proxy graph."""

    simulation_id: str
    app_session_id: int
    session_id: str
    user_id: str
    user_side: Side
    scenario_public_context: dict[str, Any]
    student_private_context: dict[str, Any]
    proxy_persona: dict[str, Any]
    coach_advice: CoachAdvice
    messages: list[Any]
    phase: str
    active_side: Side
    current_offer: Offer
    offer_history: Annotated[list[Offer], operator.add]
    turn_count: int
    event_log: NotRequired[Annotated[list[str], operator.add]]

    proxy_prompt: str
    proxy_response: dict[str, Any]
    proxy_validation_error: str
    proxy_retry_count: int
    missing_information: list[str]

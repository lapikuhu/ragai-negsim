import operator
from typing import Annotated, Any

from pydantic import BaseModel
from typing_extensions import NotRequired, TypedDict

from app.airag.chains.negotiation.negotiation_model import Confidence, EndIntent


class IntentClassificationModel(BaseModel):
    """Validated end-intent classification for the latest user turn."""

    intent: EndIntent
    confidence: Confidence
    reasoning: str


class IntentClassifierGraphState(TypedDict, total=False):
    """State consumed and produced by the intent-classifier graph."""

    messages: list[Any]
    intent_prompt: str
    intent_classification: dict[str, Any]
    intent_validation_error: str
    event_log: NotRequired[Annotated[list[str], operator.add]]

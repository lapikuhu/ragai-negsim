from typing import Annotated, Literal
from typing_extensions import TypedDict
import operator
from langchain_core.messages import AnyMessage
from langchain_core.documents import Document
from langgraph.graph.message import add_messages

# The basic negotiation state model and data structures that will be used in
# the negotiation graph are defined here.

# Sides of the negotiation
Side = Literal["side_a", "side_b"]

# How to evaluate offers - whether higher values are better (e.g. price for a seller)
ValuePreference = Literal["higher_is_better", "lower_is_better"]

# Confidence levels used by structured agent outputs.
Confidence = Literal["low", "medium", "high"]

# Phases of the negotiation, which can be used to track overall progress.
NegotiationPhase = Literal[
    "setup",
    "opening",
    "bargaining",
    "closing",
    "ended",
]

# What to do next in the negotiation, as decided by the graph's routing logic.
NextAction = Literal[
    "call_side_a",
    "call_side_b",
    "call_coach",
    "call_evaluator",
    "call_retriever",
    "ask_user",
    "end",
]

class SideProfile(TypedDict, total=False):
    """Stable information about one negotiation side."""
    side_id: str
    name: str
    role: str
    goal: str
    constraints: list[str]
    batna: str
    reservation_value: float # Worst acceptable outcome
    target_value: float # Ideal outcome
    value_preference: ValuePreference


class Offer(TypedDict, total=False):
    """An offer made by either side."""
    side: Side
    price: float
    terms: dict
    raw_text: str


class PositionAssessment(TypedDict, total=False):
    """User-side position assessment produced by the coach."""
    target_value: str
    reservation_value: str
    current_offer_assessment: str
    zopa_comment: str


class CoachAdvice(TypedDict, total=False):
    """Advice for the side controlled by the user."""
    target_side: Side
    summary: str
    position_assessment: PositionAssessment
    risks: list[str]
    recommended_next_move: str
    suggested_response: str
    reasoning: str
    confidence: Confidence
    missing_information: list[str]


class Evaluation(TypedDict, total=False):
    """Evaluation of the current negotiation state."""
    evaluated_side: Side
    score: float
    reasoning: str
    detected_risks: list[str]
    next_best_action: str


class RetrievalResult(TypedDict, total=False):
    query: str
    documents: list[Document]
    summary: str

# The negotiation state that will be passed through the graph, containing all 
# relevant information about the negotiation so far, as well as outputs from 
# various nodes and subgraphs.

class ParentNegotiationState(TypedDict, total=False):
    # Stable identifiers
    simulation_id: str
    # Legacy alias for simulation_id; app login/session linkage uses app_session_id.
    session_id: str
    app_session_id: int
    user_id: str

    # Which negotiation side the real user controls
    user_side: Side

    # Side identities / profiles
    side_a: SideProfile
    side_b: SideProfile

    # Main conversation state
    messages: Annotated[list[AnyMessage], add_messages]
    phase: NegotiationPhase

    # Current negotiation facts
    active_side: Side
    current_offer: Offer
    offer_history: Annotated[list[Offer], operator.add]

    # Outputs from subgraphs
    coach_advice: CoachAdvice
    side_a_response: str
    side_b_response: str
    evaluation: Evaluation
    retrieval_result: RetrievalResult

    # Control flow
    next_action: NextAction
    turn_count: int

    # Debug / observability
    event_log: Annotated[list[str], operator.add]

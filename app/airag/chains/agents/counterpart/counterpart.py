from typing_extensions import NotRequired, TypedDict
from typing import Annotated, Any, Literal
from pydantic import BaseModel, Field
import operator

# local imports
from app.airag.chains.agents.helpers import json_dumps, format_messages
from app.airag.chains.negotiation.negotiation_model import ParentNegotiationState
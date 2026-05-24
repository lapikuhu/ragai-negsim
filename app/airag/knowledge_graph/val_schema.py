# Validation schema draft for knowledge graph extraction. Work in progress.

from typing import Literal


ENTITIES = Literal[
    "CONCEPT",
    "TACTIC",
    "STRATEGY",
    "BIAS",
    "NEGOTIATION_PHASE",
    "OUTCOME",
    "PARTY",
]

RELATIONS = Literal[
    "SUPPORTS",
    "CONFLICTS_WITH",
    "LEADS_TO",
    "REDUCES",
    "INCREASES",
    "USED_IN",
    "DEPENDS_ON",
    "EXAMPLE_OF",
]

VALIDATION_SCHEMA = {
    "TACTIC": ["USED_IN", "LEADS_TO", "SUPPORTS", "CONFLICTS_WITH"],
    "STRATEGY": ["SUPPORTS", "DEPENDS_ON", "LEADS_TO"],
    "BIAS": ["REDUCES", "INCREASES", "CONFLICTS_WITH"],
    "CONCEPT": ["SUPPORTS", "DEPENDS_ON", "EXAMPLE_OF"],
    "NEGOTIATION_PHASE": ["USED_IN"],
}
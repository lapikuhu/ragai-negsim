from app.airag.chains.agents.counterpart.counterpart_nodes import (
    make_generate_counterpart_response_node,
    make_repair_counterpart_response_node,
)


def counterpart_payload():
    message = "I can offer checkout at 14:00 for EUR 25."
    return {
        "side": "side_a",
        "message": message,
        "action": "counter",
        "offer": {
            "side": "side_a",
            "price": 25.0,
            "terms": {"checkout_time": "14:00"},
            "raw_text": message,
        },
        "private_notes": {
            "strategy_used": "conditional_concession",
            "reservation_value_check": "within bounds",
            "target_value_check": "matches target",
            "risk": "low",
        },
    }


class FunctionCallingOnlyModel:
    def __init__(self):
        self.methods = []

    def with_structured_output(self, schema, *, method):
        self.methods.append(method)
        return self

    def invoke(self, prompt):
        return counterpart_payload()


def test_counterpart_generation_uses_function_calling_for_freeform_terms():
    model = FunctionCallingOnlyModel()
    node = make_generate_counterpart_response_node(model)

    result = node(
        {
            "user_side": "side_b",
            "scenario_public_context": {"name": "Late checkout"},
            "own_private_context": {"target_value": 25.0},
        }
    )

    assert result["counterpart_response"]["offer"]["terms"] == {
        "checkout_time": "14:00"
    }
    assert model.methods == ["function_calling"]


def test_counterpart_repair_uses_function_calling_for_freeform_terms():
    model = FunctionCallingOnlyModel()
    node = make_repair_counterpart_response_node(model)

    result = node(
        {
            "user_side": "side_b",
            "counterpart_validation_error": "invalid schema",
            "counterpart_prompt": "Respond as the hotel.",
        }
    )

    assert result["counterpart_response"]["action"] == "counter"
    assert model.methods == ["function_calling"]

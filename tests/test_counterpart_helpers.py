from app.airag.chains.agents.counterpart.counterpart_helpers import (
    build_effective_counterpart_profile,
    collect_missing_information,
    fallback_counterpart_response,
    render_counterpart_prompt,
)


def test_effective_counterpart_profile_prefers_private_context_over_persona_defaults():
    state = {
        "user_side": "side_a",
        "own_private_context": {
            "name": "Seller runtime",
            "target_value": 120.0,
            "value_preference": "higher_is_better",
        },
        "counterpart_persona": {
            "id": 300,
            "name": "Firm seller",
            "description": "Persona context",
            "target_value": 95.0,
            "reservation_value": 80.0,
            "value_preference": "lower_is_better",
        },
    }

    result = build_effective_counterpart_profile(state)

    assert result == {
        "persona_id": 300,
        "name": "Seller runtime",
        "description": "Persona context",
        "target_value": 120.0,
        "reservation_value": 80.0,
        "value_preference": "higher_is_better",
    }


def test_render_counterpart_prompt_includes_explicit_persona_and_effective_profile():
    state = {
        "user_side": "side_a",
        "counterpart_side": "side_b",
        "own_private_context": {"name": "Seller runtime", "target_value": 120.0},
        "counterpart_persona": {
            "id": 300,
            "name": "Firm seller",
            "description": "Persona context",
            "reservation_value": 90.0,
            "value_preference": "higher_is_better",
        },
        "messages": [],
        "current_offer": {},
        "offer_history": [],
        "phase": "opening",
        "active_side": "side_a",
    }

    rendered = render_counterpart_prompt(
        state,
        prompt_template="persona={counterpart_persona}\neffective={effective_counterpart_profile}",
    )

    assert '"id": 300' in rendered
    assert '"description": "Persona context"' in rendered
    assert '"persona_id": 300' in rendered
    assert '"target_value": 120.0' in rendered


def test_collect_missing_information_uses_private_context_shape():
    state = {
        "user_side": "side_a",
        "scenario_public_context": {"name": "Late checkout"},
        "own_private_context": {"target_value": 125.0, "reservation_value": 90.0},
        "counterpart_persona": {
            "id": 300,
            "name": "Firm seller",
        },
        "current_offer": {"price": 100.0},
        "offer_history": [{"price": 100.0}],
    }

    missing = collect_missing_information(state)

    assert "counterpart_persona" not in missing
    assert "scenario_public_context" not in missing
    assert "own_private_context" not in missing


def test_render_counterpart_prompt_appends_public_context_to_legacy_custom_template():
    rendered = render_counterpart_prompt(
        {
            "user_side": "side_b",
            "scenario_public_context": {
                "name": "Hotel late checkout",
                "description": "The guest wants a free late checkout.",
            },
            "own_private_context": {"reservation": "SIDE-A-SECRET"},
        },
        prompt_template="Reply as the counterpart.",
    )

    assert "PUBLIC CONTEXT" in rendered
    assert '"name": "Hotel late checkout"' in rendered
    assert '"description": "The guest wants a free late checkout."' in rendered


def test_counterpart_fallback_advances_scenario_instead_of_repeated_clarification():
    response = fallback_counterpart_response(
        {
            "user_side": "side_b",
            "scenario_public_context": {
                "name": "Hotel late checkout",
                "description": "The guest wants a free late checkout.",
            },
        },
        reason="structured output failed",
    )

    assert response["action"] == "counter"
    assert "Hotel late checkout" in response["message"]
    assert response["private_notes"]["strategy_used"] == "scenario_aware_fallback"

from app.airag.chains.agents.counterpart.counterpart_helpers import (
    build_effective_counterpart_profile,
    collect_missing_information,
    render_counterpart_prompt,
)


def test_effective_counterpart_profile_prefers_side_profile_over_persona_defaults():
    state = {
        "user_side": "side_a",
        "side_b": {
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
        "side_a": {"name": "Buyer"},
        "side_b": {"name": "Seller runtime", "target_value": 120.0},
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
        "retrieval_result": {},
        "evaluation": {},
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


def test_collect_missing_information_uses_effective_counterpart_profile():
    state = {
        "user_side": "side_a",
        "side_a": {"name": "Buyer"},
        "side_b": {"name": "Seller runtime"},
        "counterpart_persona": {
            "id": 300,
            "name": "Firm seller",
            "target_value": 125.0,
            "reservation_value": 90.0,
            "value_preference": "higher_is_better",
        },
        "current_offer": {"price": 100.0},
        "offer_history": [{"price": 100.0}],
    }

    missing = collect_missing_information(state)

    assert "counterpart_persona" not in missing
    assert "counterpart_profile.target_value" not in missing
    assert "counterpart_profile.reservation_value" not in missing
    assert "counterpart_profile.value_preference" not in missing
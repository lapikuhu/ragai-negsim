import pytest

from app.repositories import simulations_repo


def test_validate_status_transition_allows_paused_to_completed():
    simulations_repo._validate_status_transition("paused", "completed")


def test_validate_status_transition_still_rejects_completed_to_active():
    with pytest.raises(
        ValueError,
        match="Invalid simulation status transition: 'completed' -> 'active'",
    ):
        simulations_repo._validate_status_transition("completed", "active")

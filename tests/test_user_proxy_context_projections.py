from app.airag.chains.agents.context_projections import project_user_proxy_state


def parent_state():
    return {
        "simulation_id": "10",
        "session_id": "10",
        "app_session_id": 44,
        "user_id": "7",
        "user_side": "side_b",
        "scenario_public_context": {"sentinel": "PUBLIC"},
        "side_a_private_context": {"sentinel": "SIDE_A_SECRET"},
        "side_b_private_context": {"sentinel": "SIDE_B_SECRET"},
        "counterpart_persona": {"sentinel": "COUNTERPART_PERSONA"},
        "user_proxy_persona": {"sentinel": "PROXY_PERSONA"},
        "messages": [{"role": "user", "content": "LATEST-STUDENT"}],
        "phase": "bargaining",
        "active_side": "side_b",
        "current_offer": {"terms": {"sentinel": "OFFER"}},
        "offer_history": [{"terms": {"sentinel": "HISTORY"}}],
        "coach_advice": {"sentinel": "COACH_SECRET"},
        "evaluation": {"sentinel": "EVALUATOR_SECRET"},
        "final_evaluation": {"sentinel": "FINAL_SECRET"},
        "retrieval_result": {"summary": "SHARED_RETRIEVAL"},
        "event_log": ["INTERNAL_EVENT"],
    }


def test_user_proxy_projection_contains_only_student_privileges_and_coach_guidance():
    projected = project_user_proxy_state(parent_state())
    serialized = repr(projected)

    assert projected["student_private_context"]["sentinel"] == "SIDE_B_SECRET"
    assert projected["proxy_persona"]["sentinel"] == "PROXY_PERSONA"
    assert projected["coach_advice"]["sentinel"] == "COACH_SECRET"
    assert "SIDE_A_SECRET" not in serialized
    assert "EVALUATOR_SECRET" not in serialized
    assert "FINAL_SECRET" not in serialized
    assert "COUNTERPART_PERSONA" not in serialized
    assert projected["event_log"] == []

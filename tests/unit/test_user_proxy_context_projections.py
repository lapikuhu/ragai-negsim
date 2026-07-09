from app.airag.chains.agents.context_projections import project_user_proxy_state


def test_user_proxy_projection_contains_only_student_privileges_and_coach_guidance(
    agent_parent_state_factory,
):
    projected = project_user_proxy_state(
        agent_parent_state_factory(
            counterpart_persona={"sentinel": "COUNTERPART_PERSONA"},
            user_proxy_persona={"sentinel": "PROXY_PERSONA"},
        )
    )
    serialized = repr(projected)

    assert projected["student_private_context"]["sentinel"] == "SIDE_B_SECRET"
    assert projected["proxy_persona"]["sentinel"] == "PROXY_PERSONA"
    assert projected["coach_advice"]["sentinel"] == "COACH_SECRET"
    assert "SIDE_A_SECRET" not in serialized
    assert "EVALUATOR_SECRET" not in serialized
    assert "FINAL_SECRET" not in serialized
    assert "COUNTERPART_PERSONA" not in serialized
    assert projected["event_log"] == []

from app.airag.chains.agents.learner.learner_helpers import render_learner_agent_prompt


def test_learner_prompt_guides_selective_tool_use_and_training_balance():
    prompt = render_learner_agent_prompt(
        crag_available=True,
        negotiation_summary_available=True,
        tavily_search_available=True,
    )

    assert "Inspect the available tool guidance" in prompt
    assert "Do not call every available tool by default" in prompt
    assert "Balance tool use with general negotiation training" in prompt
    assert "Align every answer with both the user's query and the current negotiation state" in prompt

import re

from app.airag.chains.agents.learner import learner_agent
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


def test_learner_prompt_requires_structured_output_and_explicit_tool_policy():
    prompt = render_learner_agent_prompt(
        crag_available=True,
        graph_rag_available=True,
        negotiation_summary_available=True,
        tavily_search_available=True,
    )

    assert "Return a structured learner output" in prompt
    assert "tool_decision_summary" in prompt
    assert "evidence_used" in prompt
    assert "confidence" in prompt
    assert "Do not expose chain-of-thought" in prompt
    assert "If the learner explicitly asks you to use an available tool" in prompt


def test_make_learner_agent_uses_openai_safe_agent_name(monkeypatch):
    captured: dict[str, object] = {}

    def fake_create_agent(**kwargs):
        captured.update(kwargs)
        return object()

    monkeypatch.setattr(learner_agent, "create_agent", fake_create_agent)

    learner_agent.make_learner_agent(model=object())

    assert captured["name"] == "learner_agent"
    assert re.fullmatch(r"^[^\s<|\\/>]+$", str(captured["name"]))
    assert captured["response_format"] is learner_agent.LearnerStructuredOutput

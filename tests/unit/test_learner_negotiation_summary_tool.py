import json

from app.airag.chains.agents.learner.learner_agent import (
    build_learner_tools,
    make_summarize_negotiation_history_tool,
)
from app.airag.chains.agents.learner.learner_helpers import (
    render_learner_agent_prompt,
)


class CapturingSummarizer:
    def __init__(self, result=None, error=None):
        self.calls = []
        self.result = result or {
            "summary": "The buyer asked for a lower price and the seller held firm.",
            "key_points": ["buyer requested discount", "seller protected price"],
            "open_questions": ["Can delivery timing trade for price?"],
        }
        self.error = error

    def invoke(self, payload, config=None):
        self.calls.append({"payload": payload, "config": config})
        if self.error is not None:
            raise self.error
        return self.result


class MessageLikeResult:
    content = "The latest exchange focused on price and timing."


def test_summary_tool_schema_exposes_only_focus():
    tool = make_summarize_negotiation_history_tool(
        summarize_model=CapturingSummarizer(),
        messages=[{"role": "user", "content": "Can you lower the price?"}],
        user_side="side_a",
    )

    assert tool.args == {
        "focus": {
            "anyOf": [{"type": "string"}, {"type": "null"}],
            "default": None,
            "description": "Optional area to emphasize in the negotiation summary.",
            "title": "Focus",
        }
    }


def test_summary_tool_invokes_model_with_learner_safe_context_and_focus(
    agent_parent_state_factory,
):
    state = agent_parent_state_factory(
        user_side="side_a",
        messages=[{"role": "user", "content": "I need a lower price."}],
        scenario_public_context={"item": "software contract"},
        side_a_private_context={"target": "20% discount"},
        current_offer={"price": 1000},
        offer_history=[{"price": 1200}, {"price": 1000}],
    )
    model = CapturingSummarizer()
    tool = make_summarize_negotiation_history_tool(
        summarize_model=model,
        messages=state["messages"],
        user_side=state["user_side"],
        public_context=state["scenario_public_context"],
        student_private_context=state["side_a_private_context"],
        current_offer=state["current_offer"],
        offer_history=state["offer_history"],
    )

    payload = json.loads(tool.invoke({"focus": "concession pattern"}))

    prompt = model.calls[0]["payload"]
    assert "concession pattern" in prompt
    assert "software contract" in prompt
    assert "20% discount" in prompt
    assert "1000" in prompt
    assert "counterpart_private_context" not in prompt
    assert "evaluator" not in prompt.lower()
    assert payload == {
        "status": "success",
        "summary": "The buyer asked for a lower price and the seller held firm.",
        "key_points": ["buyer requested discount", "seller protected price"],
        "open_questions": ["Can delivery timing trade for price?"],
    }


def test_summary_tool_wraps_message_like_output_into_summary():
    tool = make_summarize_negotiation_history_tool(
        summarize_model=CapturingSummarizer(result=MessageLikeResult()),
        messages=[{"role": "user", "content": "Can you lower the price?"}],
        user_side="side_a",
    )

    payload = json.loads(tool.invoke({}))

    assert payload == {
        "status": "success",
        "summary": "The latest exchange focused on price and timing.",
        "key_points": [],
        "open_questions": [],
    }


def test_summary_tool_returns_failed_json_when_model_raises():
    tool = make_summarize_negotiation_history_tool(
        summarize_model=CapturingSummarizer(error=RuntimeError("model unavailable")),
        messages=[{"role": "user", "content": "Can you lower the price?"}],
        user_side="side_a",
    )

    payload = json.loads(tool.invoke({"focus": "risks"}))

    assert payload == {
        "status": "failed",
        "summary": "",
        "key_points": [],
        "open_questions": [],
        "error": "model unavailable",
    }


def test_build_learner_tools_includes_summary_only_with_bound_dependencies():
    without_summary = build_learner_tools(
        summarize_model=None,
        messages=[{"role": "user", "content": "Can you lower the price?"}],
        user_side="side_a",
    )
    with_summary = build_learner_tools(
        summarize_model=CapturingSummarizer(),
        messages=[{"role": "user", "content": "Can you lower the price?"}],
        user_side="side_a",
    )

    assert "summarize_negotiation_history_tool" not in [
        tool.name for tool in without_summary
    ]
    assert "summarize_negotiation_history_tool" in [
        tool.name for tool in with_summary
    ]


def test_render_learner_agent_prompt_reflects_summary_tool_availability():
    with_summary = render_learner_agent_prompt(
        "Base prompt",
        negotiation_summary_available=True,
    )
    without_summary = render_learner_agent_prompt(
        "Base prompt",
        negotiation_summary_available=False,
    )

    assert "Negotiation history summarization is available" in with_summary
    assert "Negotiation history summarization is not available" in without_summary
    assert "must not mention the summary tool" in without_summary

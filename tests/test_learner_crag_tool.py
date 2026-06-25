import json

from app.airag.chains.agents.learner.learner_agent import (
    build_learner_tools,
    make_crag_tool,
)
from app.airag.chains.agents.learner.learner_helpers import (
    render_learner_agent_prompt,
)


class CapturingCrag:
    def __init__(self, result=None, error=None):
        self.calls = []
        self.result = result or {
            "answer": "Use objective criteria before making concessions.",
            "context": "Objective criteria can anchor negotiation choices.",
            "evidence_ledger": {
                "sources": [{"rank": 1, "source": "negotiation-guide.md"}]
            },
        }
        self.error = error

    def invoke(self, payload, config=None):
        self.calls.append({"payload": payload, "config": config})
        if self.error is not None:
            raise self.error
        return self.result


def test_make_crag_tool_invokes_bound_graph_and_returns_structured_json():
    graph = CapturingCrag()
    tool = make_crag_tool(graph)

    payload = json.loads(tool.invoke({"question": "How should I make concessions?"}))

    assert graph.calls[0]["payload"] == {
        "question": "How should I make concessions?",
        "attempts": 0,
    }
    assert payload == {
        "status": "success",
        "answer": "Use objective criteria before making concessions.",
        "context": "Objective criteria can anchor negotiation choices.",
        "sources": [{"rank": 1, "source": "negotiation-guide.md"}],
        "evidence_ledger": {
            "sources": [{"rank": 1, "source": "negotiation-guide.md"}]
        },
    }


def test_make_crag_tool_returns_failed_json_when_graph_raises():
    tool = make_crag_tool(CapturingCrag(error=RuntimeError("retriever unavailable")))

    payload = json.loads(tool.invoke({"question": "What is my BATNA?"}))

    assert payload == {
        "status": "failed",
        "answer": "",
        "context": "",
        "sources": [],
        "error": "retriever unavailable",
    }


def test_build_learner_tools_omits_crag_when_graph_is_missing():
    tools = build_learner_tools(crag_graph=None)

    assert [tool.name for tool in tools] == []


def test_build_learner_tools_includes_crag_without_exposing_graph_argument():
    tools = build_learner_tools(crag_graph=CapturingCrag())
    crag_tools = [tool for tool in tools if tool.name == "crag_tool"]

    assert len(crag_tools) == 1
    assert crag_tools[0].args == {
        "question": {
            "description": "The learner's negotiation-related question.",
            "title": "Question",
            "type": "string",
        }
    }


def test_render_learner_agent_prompt_reflects_crag_availability():
    with_crag = render_learner_agent_prompt("Base prompt", crag_available=True)
    without_crag = render_learner_agent_prompt("Base prompt", crag_available=False)

    assert "CRAG retrieval is available" in with_crag
    assert "CRAG retrieval is not available" in without_crag
    assert "must not mention CRAG" in without_crag

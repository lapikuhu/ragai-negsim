import json

from app.airag.chains.agents.learner.learner_agent import (
    build_learner_tools,
    make_tavily_search_tool,
)
from app.airag.chains.agents.learner.learner_helpers import (
    render_learner_agent_prompt,
)


class CapturingTavilySearch:
    def __init__(self, result=None, error=None):
        self.calls = []
        self.result = result or {
            "results": [
                {
                    "title": "Negotiation update",
                    "url": "https://example.com/negotiation",
                    "content": "Recent negotiation research emphasizes preparation.",
                    "score": 0.91,
                }
            ]
        }
        self.error = error

    def invoke(self, payload, config=None):
        self.calls.append({"payload": payload, "config": config})
        if self.error is not None:
            raise self.error
        return self.result


class CapturingSummarizer:
    def __init__(self, result=None, error=None):
        self.calls = []
        self.result = result or {
            "summary": "Recent sources emphasize preparation before bargaining."
        }
        self.error = error

    def invoke(self, payload, config=None):
        self.calls.append({"payload": payload, "config": config})
        if self.error is not None:
            raise self.error
        return self.result


class MessageLikeResult:
    content = "A short web-search summary."


def test_tavily_tool_schema_exposes_only_query_and_max_results():
    tool = make_tavily_search_tool(
        tavily_search=CapturingTavilySearch(),
        tavily_summarizer_model=CapturingSummarizer(),
    )

    assert tool.args == {
        "query": {
            "description": "The external web search query.",
            "title": "Query",
            "type": "string",
        },
        "max_results": {
            "default": 5,
            "description": "Maximum number of web search results to retrieve.",
            "minimum": 1,
            "title": "Max Results",
            "type": "integer",
        },
    }


def test_tavily_tool_invokes_search_and_summarizer_and_returns_structured_json():
    search = CapturingTavilySearch()
    summarizer = CapturingSummarizer()
    tool = make_tavily_search_tool(
        tavily_search=search,
        tavily_summarizer_model=summarizer,
    )

    payload = json.loads(
        tool.invoke({"query": "current negotiation research", "max_results": 2})
    )

    assert search.calls[0]["payload"] == {
        "query": "current negotiation research",
        "max_results": 2,
        "include_images": False,
        "include_answers": False,
    }
    summary_prompt = summarizer.calls[0]["payload"]
    assert "current negotiation research" in summary_prompt
    assert "Recent negotiation research emphasizes preparation." in summary_prompt
    assert payload == {
        "status": "success",
        "query": "current negotiation research",
        "summary": "Recent sources emphasize preparation before bargaining.",
        "results": [
            {
                "title": "Negotiation update",
                "url": "https://example.com/negotiation",
                "content": "Recent negotiation research emphasizes preparation.",
                "score": 0.91,
            }
        ],
        "sources": [
            {
                "title": "Negotiation update",
                "url": "https://example.com/negotiation",
            }
        ],
    }


def test_tavily_tool_wraps_message_like_summary_output():
    tool = make_tavily_search_tool(
        tavily_search=CapturingTavilySearch(),
        tavily_summarizer_model=CapturingSummarizer(result=MessageLikeResult()),
    )

    payload = json.loads(tool.invoke({"query": "BATNA news"}))

    assert payload["status"] == "success"
    assert payload["summary"] == "A short web-search summary."


def test_tavily_tool_returns_failed_json_when_search_raises():
    tool = make_tavily_search_tool(
        tavily_search=CapturingTavilySearch(error=RuntimeError("search unavailable")),
        tavily_summarizer_model=CapturingSummarizer(),
    )

    payload = json.loads(tool.invoke({"query": "current bargaining news"}))

    assert payload == {
        "status": "failed",
        "query": "current bargaining news",
        "summary": "",
        "results": [],
        "sources": [],
        "error": "search unavailable",
    }


def test_tavily_tool_returns_failed_json_when_summarizer_raises():
    tool = make_tavily_search_tool(
        tavily_search=CapturingTavilySearch(),
        tavily_summarizer_model=CapturingSummarizer(error=RuntimeError("summary failed")),
    )

    payload = json.loads(tool.invoke({"query": "current bargaining news"}))

    assert payload == {
        "status": "failed",
        "query": "current bargaining news",
        "summary": "",
        "results": [],
        "sources": [],
        "error": "summary failed",
    }


def test_build_learner_tools_includes_tavily_only_with_bound_dependencies():
    without_tavily = build_learner_tools(
        tavily_search=CapturingTavilySearch(),
        tavily_summarizer_model=None,
    )
    with_tavily = build_learner_tools(
        tavily_search=CapturingTavilySearch(),
        tavily_summarizer_model=CapturingSummarizer(),
    )

    assert "tavily_search_tool" not in [tool.name for tool in without_tavily]
    assert "tavily_search_tool" in [tool.name for tool in with_tavily]


def test_render_learner_agent_prompt_reflects_tavily_availability():
    with_tavily = render_learner_agent_prompt(
        "Base prompt",
        tavily_search_available=True,
    )
    without_tavily = render_learner_agent_prompt(
        "Base prompt",
        tavily_search_available=False,
    )

    assert "Tavily web search is available" in with_tavily
    assert "Tavily web search is not available" in without_tavily
    assert "must not mention web search or Tavily" in without_tavily

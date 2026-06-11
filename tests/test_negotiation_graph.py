from typing import get_args

import pytest

from app.airag.chains.agents.evaluator.evaluator import make_evaluator_graph
from app.airag.chains.negotiation.negotiation import make_negotiation_graph
from app.airag.chains.negotiation.negotiation_model import (
    EvaluationMode,
    EvaluatorStrategy,
    RequestedAction,
    TerminalReason,
)


def test_negotiation_control_vocabularies_are_separate():
    assert set(get_args(RequestedAction)) == {"continue", "end"}
    assert set(get_args(EvaluatorStrategy)) == {
        "continue",
        "counter",
        "accept",
        "walk_away",
    }
    assert set(get_args(EvaluationMode)) == {"rolling", "final"}
    assert set(get_args(TerminalReason)) == {
        "student_request",
        "classified_intent",
        "turn_limit",
    }


class StubGraph:
    def __init__(self, callback):
        self.callback = callback

    def invoke(self, state):
        return self.callback(state)


def base_state():
    return {
        "simulation_id": "1",
        "session_id": "1",
        "user_id": "1",
        "user_side": "side_b",
        "counterpart_persona": {
            "name": "Firm hotel manager",
            "description": "Protects hotel operations while offering practical trades.",
        },
        "scenario_public_context": {"name": "Hotel late checkout"},
        "side_a_private_context": {"reservation": "SIDE-A-SECRET"},
        "side_b_private_context": {"reservation": "SIDE-B-SECRET"},
        "side_a": {"name": "Hotel"},
        "side_b": {"name": "Guest"},
        "messages": [
            {
                "role": "user",
                "content": "I do not want to pay for late checkout.",
                "side": "side_b",
            }
        ],
        "phase": "opening",
        "active_side": "side_b",
        "offer_history": [],
        "event_log": [],
        "turn_count": 0,
        "max_turn_count": 12,
    }


def build_stubbed_negotiation_graph(
    trace,
    classifier=None,
    evaluator_strategy="continue",
    final_evaluation=None,
    observed_counterpart_state=None,
    observed_evaluator_state=None,
    observed_coach_state=None,
):
    classifier = classifier or {
        "intent": "continue",
        "confidence": "high",
        "reasoning": "Continue.",
    }
    final_evaluation = final_evaluation or {
        "evaluated_side": "side_b",
        "overall_score": 0.7,
        "goal_achievement": "Protected the main objective.",
        "strengths": ["Stayed clear."],
        "mistakes": [],
        "concession_quality": "Good.",
        "communication_quality": "Clear.",
        "outcome_quality": "Unknown.",
        "lessons": ["Keep testing flexibility."],
        "reasoning": "Full-session assessment.",
        "confidence": "high",
        "missing_information": [],
    }

    def classify(state):
        trace.append("classifier")
        return {
            **state,
            "intent_classification": classifier,
            "event_log": [*state.get("event_log", []), "intent_classifier:completed"],
        }

    def counterpart(state):
        trace.append("counterpart")
        if observed_counterpart_state is not None:
            observed_counterpart_state.update(state)
        return {
            **state,
            "counterpart_response": {
                "side": "side_a",
                "message": "Late checkout normally has a fee.",
                "offer": {
                    "side": "side_a",
                    "terms": {"late_checkout_fee": 25},
                    "raw_text": "Late checkout normally has a fee.",
                },
            },
            "side_a_response": "Late checkout normally has a fee.",
            "current_offer": {
                "side": "side_a",
                "terms": {"late_checkout_fee": 25},
                "raw_text": "Late checkout normally has a fee.",
            },
            "event_log": [*state.get("event_log", []), "counterpart:completed"],
        }

    def evaluator(state):
        mode = state.get("evaluation_mode", "rolling")
        trace.append(f"evaluator:{mode}")
        if observed_evaluator_state is not None:
            observed_evaluator_state.update(state)
        if mode == "final":
            return {
                **state,
                "final_evaluation": final_evaluation,
                "event_log": [*state.get("event_log", []), "evaluator:final_completed"],
            }
        return {
            **state,
            "evaluation": {
                "evaluated_side": "side_b",
                "score": 0.5,
                "reasoning": "Rolling assessment.",
                "detected_risks": [],
                "next_best_action": evaluator_strategy,
                "confidence": "medium",
                "missing_information": [],
            },
            "event_log": [*state.get("event_log", []), "evaluator:rolling_completed"],
        }

    def coach(state):
        trace.append("coach")
        if observed_coach_state is not None:
            observed_coach_state.update(state)
        return {
            **state,
            "coach_advice": {
                "target_side": "side_b",
                "summary": "Ask what flexibility exists.",
            },
            "event_log": [*state.get("event_log", []), "coach:completed"],
        }

    return make_negotiation_graph(
        intent_classifier_graph=StubGraph(classify),
        counterpart_graph=StubGraph(counterpart),
        evaluator_graph=StubGraph(evaluator),
        coach_graph=StubGraph(coach),
    )


def test_normal_turn_is_counterpart_evaluator_coach_pause():
    trace = []
    graph = build_stubbed_negotiation_graph(
        trace=trace,
        classifier={"intent": "continue", "confidence": "high", "reasoning": ""},
        evaluator_strategy="walk_away",
    )

    result = graph.invoke(base_state())

    assert trace == ["classifier", "counterpart", "evaluator:rolling", "coach"]
    assert result["should_pause"] is True
    assert result["pause_reason"] == "counterpart_response_ready"
    assert result["evaluation"]["next_best_action"] == "walk_away"
    last_message = result["messages"][-1]
    if isinstance(last_message, dict):
        content = str(last_message.get("content"))
        role = last_message.get("role")
        side = last_message.get("side")
    else:
        content = str(getattr(last_message, "content", ""))
        role = getattr(last_message, "type", None)
        side = (
            getattr(last_message, "side", None)
            or getattr(last_message, "name", None)
            or getattr(last_message, "additional_kwargs", {}).get("side")
        )
    assert content == "Late checkout normally has a fee."
    assert role in {"assistant", "ai"}
    assert side == "side_a"
    assert result["phase"] != "ended"


def test_normal_turn_projects_privileged_agent_views():
    trace = []
    captured = {}
    graph = build_stubbed_negotiation_graph(
        trace=trace,
        observed_counterpart_state=captured.setdefault("counterpart", {}),
        observed_evaluator_state=captured.setdefault("evaluator", {}),
        observed_coach_state=captured.setdefault("coach", {}),
    )

    graph.invoke(base_state())

    assert "SIDE-A-SECRET" in repr(captured["counterpart"])
    assert "SIDE-B-SECRET" not in repr(captured["counterpart"])
    assert "evaluation" not in captured["counterpart"]
    assert captured["counterpart"]["counterpart_persona"]["name"] == "Firm hotel manager"

    assert "SIDE-B-SECRET" in repr(captured["coach"])
    assert "SIDE-A-SECRET" not in repr(captured["coach"])
    assert "evaluation" not in captured["coach"]

    assert "SIDE-A-SECRET" in repr(captured["evaluator"])
    assert "SIDE-B-SECRET" in repr(captured["evaluator"])


def test_structured_end_skips_classifier_counterpart_and_coach():
    trace = []
    graph = build_stubbed_negotiation_graph(trace=trace)

    result = graph.invoke({**base_state(), "requested_action": "end"})

    assert trace == ["evaluator:final"]
    assert result["phase"] == "ended"
    assert result["terminal_reason"] == "student_request"
    assert result["should_pause"] is False


def test_low_confidence_end_continues():
    trace = []
    graph = build_stubbed_negotiation_graph(
        trace=trace,
        classifier={"intent": "end", "confidence": "low", "reasoning": "uncertain"},
    )

    result = graph.invoke(base_state())

    assert trace == ["classifier", "counterpart", "evaluator:rolling", "coach"]
    assert result["phase"] != "ended"


def test_acceptance_language_ends_simulation_without_counterpart_turn():
    trace = []
    state = {
        **base_state(),
        "messages": [
            {
                "role": "user",
                "content": "OK. I agree to your terms.",
                "side": "side_b",
            }
        ],
    }
    graph = build_stubbed_negotiation_graph(
        trace=trace,
        classifier={
            "intent": "end",
            "confidence": "high",
            "reasoning": "Agreement on terms ends the simulation.",
        },
    )

    result = graph.invoke(state)

    assert trace == ["classifier", "evaluator:final"]
    assert result["phase"] == "ended"
    assert result["terminal_reason"] == "classified_intent"
    assert result["should_pause"] is False


def test_high_confidence_end_routes_to_final_evaluation():
    trace = []
    graph = build_stubbed_negotiation_graph(
        trace=trace,
        classifier={
            "intent": "end",
            "confidence": "high",
            "reasoning": "The student explicitly asked to end the simulation.",
        },
    )

    result = graph.invoke(
        {
            **base_state(),
            "messages": [
                {
                    "role": "user",
                    "content": "Please end the simulation now.",
                    "side": "side_b",
                }
            ],
        }
    )

    assert trace == ["classifier", "evaluator:final"]
    assert result["phase"] == "ended"
    assert result["terminal_reason"] == "classified_intent"
    assert result["intent_classification"]["intent"] == "end"
    assert "orchestrator:terminal reason=classified_intent" in result["event_log"]


def test_turn_limit_runs_final_evaluator_before_another_counterpart():
    trace = []
    graph = build_stubbed_negotiation_graph(trace=trace)

    result = graph.invoke({**base_state(), "turn_count": 12, "max_turn_count": 12})

    assert trace == ["evaluator:final"]
    assert result["terminal_reason"] == "turn_limit"


@pytest.mark.parametrize(
    "strategy",
    ["continue", "counter", "accept", "walk_away"],
)
def test_rolling_strategy_never_changes_graph_route(strategy):
    trace = []
    graph = build_stubbed_negotiation_graph(
        trace=trace,
        evaluator_strategy=strategy,
    )

    result = graph.invoke(base_state())

    assert trace == ["classifier", "counterpart", "evaluator:rolling", "coach"]
    assert result["evaluation"]["next_best_action"] == strategy
    assert result["should_pause"] is True


@pytest.mark.parametrize(
    "legacy_action",
    ["ask_user", "call_coach", "call_evaluator", "end"],
)
def test_legacy_next_action_does_not_control_new_graph(legacy_action):
    trace = []
    graph = build_stubbed_negotiation_graph(trace=trace)

    result = graph.invoke({**base_state(), "next_action": legacy_action})

    assert trace == ["classifier", "counterpart", "evaluator:rolling", "coach"]
    assert result["should_pause"] is True
    assert result["pause_reason"] == "counterpart_response_ready"
    assert result["phase"] != "ended"


def test_incomplete_state_still_runs_normal_turn_without_ask_user():
    trace = []
    graph = build_stubbed_negotiation_graph(trace=trace)

    result = graph.invoke(
        {
            **base_state(),
            "side_a": {},
            "side_b": {},
            "current_offer": {},
            "offer_history": [],
        }
    )

    assert trace == ["classifier", "counterpart", "evaluator:rolling", "coach"]
    assert result["pause_reason"] == "counterpart_response_ready"
    assert result["should_pause"] is True
    assert "ask_user" not in result.get("event_log", [])


def test_final_evaluator_failure_falls_back_and_still_finalizes():
    trace = []

    class RaisingModel:
        def with_structured_output(self, schema):
            return self

        def invoke(self, prompt):
            raise RuntimeError("evaluator unavailable")

    def classify(state):
        trace.append("classifier")
        return {
            **state,
            "intent_classification": {
                "intent": "end",
                "confidence": "high",
                "reasoning": "Stop now.",
            },
        }

    def counterpart(state):
        trace.append("counterpart")
        return state

    def coach(state):
        trace.append("coach")
        return state

    evaluator_graph = make_evaluator_graph(model=RaisingModel(), crag_graph=None)
    graph = make_negotiation_graph(
        intent_classifier_graph=StubGraph(classify),
        counterpart_graph=StubGraph(counterpart),
        coach_graph=StubGraph(coach),
        evaluator_graph=evaluator_graph,
    )

    result = graph.invoke(base_state())

    assert trace == ["classifier"]
    assert result["phase"] == "ended"
    assert result["should_pause"] is False
    assert result["final_evaluation"]["confidence"] == "low"

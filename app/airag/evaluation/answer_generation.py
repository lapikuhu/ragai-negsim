"""Grounded answer generation for retrieval evaluation runs."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import replace
from typing import Any

from app.airag.evaluation.eval_models import EvalRunResult
from app.airag.llm_models.llm_models import get_llm
from app.airag.observability.llm_usage import guarded_invoke_with_config
from app.services.llm_models_service import normalize_llm_selection


ANSWER_GENERATION_PROMPT_VERSION = "grounded_answer_v1"
NO_RETRIEVED_EVIDENCE_ANSWER = "I don't have enough retrieved evidence to answer this question."


class RagEvalAnswerGenerationCancelled(Exception):
    """Raised when a run is cancelled between answer-generation calls."""


def _grounded_answer_prompt(query: str, contexts: tuple[str, ...]) -> str:
    """
    Construct a prompt for grounded answer generation.
    Args:
        query: The question to answer.
        contexts: The retrieved contexts to use as evidence.
    Returns:
        A string prompt for the answer-generation model.
    """
    evidence = "\n\n".join(
        f"[Evidence {index}]\n{context}" for index, context in enumerate(contexts, start=1)
    )
    return f"""Answer the question using only the retrieved evidence below.
If the evidence does not support an answer, say that the retrieved evidence is insufficient.
Do not add facts, assumptions, or citations not present in the evidence.

Question:
{query}

Retrieved evidence:
{evidence}
"""


def _response_text(response: Any) -> str:
    """
    Extract the text content from the answer-generation model response.
    Args:
        response: The raw response from the model.
    Returns:
        The extracted text content.
    Raises:
        ValueError: If the extracted text is empty.
    """
    content = getattr(response, "content", response)
    if isinstance(content, str):
        text = content.strip()
    elif isinstance(content, list):
        text = "".join(
            item if isinstance(item, str) else str(item.get("text", ""))
            for item in content
        ).strip()
    else:
        text = str(content).strip()
    if not text:
        raise ValueError("Answer-generation model returned an empty answer")
    return text


async def generate_grounded_answers(
    eval_run: EvalRunResult,
    *,
    provider: str,
    model: str,
    should_cancel: Callable[[], Awaitable[bool]] | None = None,
) -> EvalRunResult:
    """
    Generate one grounded answer per retrieved evaluation result.
    Args:
        eval_run: The evaluation run containing the results to generate 
            answers for.
        provider: The LLM provider to use for answer generation.
        model: The LLM model to use for answer generation.
        should_cancel: An optional callable that returns True if the run 
            should be cancelled.
    Returns:
        An updated evaluation run with generated answers.
    Raises:
        RagEvalAnswerGenerationCancelled: If the run is cancelled during 
        answer generation.
    """
    selection = normalize_llm_selection(provider, model)
    llm = None
    generated = []
    for result in eval_run.results:
        if should_cancel is not None and await should_cancel():
            raise RagEvalAnswerGenerationCancelled()
        if not result.retrieved_contexts:
            generated.append(replace(result, answer=NO_RETRIEVED_EVIDENCE_ANSWER))
            continue
        if llm is None:
            llm = get_llm(
                provider=selection["provider"],
                model_name=selection["model"],
                temperature=0,
            )
            if llm is None:
                raise ValueError("Unable to initialize the selected answer-generation LLM")
        response = await asyncio.to_thread(
            guarded_invoke_with_config,
            llm,
            _grounded_answer_prompt(result.query, result.retrieved_contexts),
        )
        generated.append(replace(result, answer=_response_text(response)))
    return replace(eval_run, results=tuple(generated))

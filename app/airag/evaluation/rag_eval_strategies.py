"""Registry of RAG strategies that have isolated evaluation adapters."""
from __future__ import annotations
from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping


@dataclass(frozen=True)
class EvaluationStrategyDefinition:
    strategy: str
    handler_name: str


class EvaluationStrategyRegistry:
    def __init__(self, definitions: tuple[EvaluationStrategyDefinition, ...]) -> None:
        self._definitions: Mapping[str, EvaluationStrategyDefinition] = MappingProxyType(
            {definition.strategy: definition for definition in definitions}
        )

    def require(self, strategy: object) -> EvaluationStrategyDefinition:
        """
        Checks if the given strategy is supported and returns its definition.
        Args:
            strategy: The RAG evaluation strategy to check.
        Returns:
            The corresponding EvaluationStrategyDefinition if supported.
        Raises:
            ValueError: If the strategy is not supported.
        """
        if not isinstance(strategy, str) or not strategy.strip():
            raise ValueError(f"Unsupported RAG evaluation strategy: {strategy}")
        try:
            return self._definitions[strategy]
        except KeyError as exc:
            raise ValueError(f"Unsupported RAG evaluation strategy: {strategy}") from exc


EVALUATION_STRATEGIES = EvaluationStrategyRegistry(
    (
        EvaluationStrategyDefinition("crag", "_evaluate_crag"),
        EvaluationStrategyDefinition("graphrag", "_evaluate_graphrag"),
    )
)

import ast
from pathlib import Path


SEEDER_PATH = Path(__file__).resolve().parents[1] / "scripts" / "seeder.py"


def _assignment_value(name: str) -> ast.AST:
    module = ast.parse(SEEDER_PATH.read_text(encoding="utf-8"))
    for statement in module.body:
        if not isinstance(statement, ast.Assign):
            continue
        for target in statement.targets:
            if isinstance(target, ast.Name) and target.id == name:
                return statement.value
    raise AssertionError(f"{name} assignment not found in {SEEDER_PATH}")


def test_placeholder_scenarios_are_written_as_literal_list() -> None:
    assert isinstance(_assignment_value("PLACEHOLDER_SCENARIOS"), ast.List)


def test_placeholder_personas_are_written_as_literal_list() -> None:
    assert isinstance(_assignment_value("PLACEHOLDER_PERSONAS"), ast.List)

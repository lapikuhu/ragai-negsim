"""Serialization helpers for persisted RAG evaluation run exports."""

import csv
import io
import json
import re
from collections.abc import Mapping
from datetime import datetime
from typing import Any

from app.schemas.rag_eval_schemas import RagEvalRunRead


_RUN_FIELDS = (
    "id",
    "configuration_id",
    "status",
    "stage",
    "progress",
    "completed_examples",
    "total_examples",
    "queued_at",
    "started_at",
    "completed_at",
    "suite_version",
    "suite_content_hash",
)
_FORMULA_PREFIX = re.compile(r"^\s*[=+\-@]")


def _excel_cell(value: Any) -> str | int | float:
    """
    Convert a value to a deterministic, spreadsheet-safe CSV cell.

    Args:
        value (Any): The value to convert.
    Returns:
        str | int | float: The spreadsheet-safe CSV cell representation 
        of the value.
    """
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return value
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, (dict, list)):
        text = json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    else:
        text = str(value)
    return f"'{text}" if _FORMULA_PREFIX.match(text) else text


def serialize_rag_eval_run_summary_csv(run: RagEvalRunRead) -> bytes:
    """
    Serialize persisted run metadata and aggregates as Excel-friendly CSV.
    Args:
        run (RagEvalRunRead): The persisted RAG evaluation run to serialize.
    Returns:
        bytes: The Excel-friendly CSV representation of the run.
    """
    output = io.StringIO(newline="")
    writer = csv.writer(output, lineterminator="\r\n")
    writer.writerow(("Section", "Field", "Value"))

    for field in _RUN_FIELDS:
        writer.writerow(("Run", field, _excel_cell(getattr(run, field))))

    for field in sorted(run.configuration_snapshot):
        writer.writerow(
            (
                "Configuration",
                _excel_cell(field),
                _excel_cell(run.configuration_snapshot[field]),
            )
        )

    for field in sorted(run.resolved_pipeline_snapshot):
        writer.writerow(
            (
                "Resolved pipeline",
                _excel_cell(field),
                _excel_cell(run.resolved_pipeline_snapshot[field]),
            )
        )

    for metric in sorted(run.overall_metrics):
        writer.writerow(
            (
                "Overall metrics",
                _excel_cell(metric),
                _excel_cell(run.overall_metrics[metric]),
            )
        )

    for category in sorted(run.category_metrics):
        metrics = run.category_metrics[category]
        if not isinstance(metrics, Mapping):
            raise TypeError("category metric group must be a mapping")
        for metric in sorted(metrics):
            writer.writerow(
                (
                    "Category metrics",
                    _excel_cell(f"{category} / {metric}"),
                    _excel_cell(metrics[metric]),
                )
            )

    return output.getvalue().encode("utf-8-sig")


def serialize_rag_eval_run_summary_json(run: RagEvalRunRead) -> bytes:
    """
    Serialize persisted run metadata and aggregates as structured JSON.

    Args:
        run (RagEvalRunRead): The persisted RAG evaluation run to serialize.
    Returns:
        bytes: The JSON representation of the run.
    """
    serialized_run = run.model_dump(mode="json")
    for metrics in run.category_metrics.values():
        if not isinstance(metrics, Mapping):
            raise TypeError("category metric group must be a mapping")

    summary = {
        "run": {field: serialized_run[field] for field in _RUN_FIELDS},
        "configuration": serialized_run["configuration_snapshot"],
        "resolved_pipeline": serialized_run["resolved_pipeline_snapshot"],
        "overall_metrics": serialized_run["overall_metrics"],
        "category_metrics": serialized_run["category_metrics"],
    }
    return json.dumps(
        summary,
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    ).encode("utf-8")

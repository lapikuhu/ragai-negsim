import csv
import io
import json
from datetime import datetime, timezone

import pytest

from app.schemas.rag_eval_schemas import RagEvalRunRead


def _completed_run() -> RagEvalRunRead:
    return RagEvalRunRead(
        id=11,
        configuration_id=7,
        status="completed",
        stage="finished",
        progress=100.0,
        completed_examples=80,
        total_examples=80,
        queued_at=datetime(2026, 8, 12, 8, 0, tzinfo=timezone.utc),
        started_at=None,
        completed_at=datetime(2026, 8, 12, 8, 10, tzinfo=timezone.utc),
        cancel_requested=False,
        cancellation_requested_at=None,
        failure_code=None,
        failure_message=None,
        configuration_snapshot={
            "nested": {"z": True, "a": "α"},
            "a_formula": "=SUM(1,2)",
            "+formula_key": "safe",
            "quoted": 'comma, quote " and\nnewline',
        },
        suite_version="rag-eval-v1",
        suite_content_hash="abc123",
        resolved_pipeline_snapshot={"model": "gpt-4o-mini"},
        overall_metrics={"faithfulness": 0.91234},
        category_metrics={
            "direct_retrieval": {"context_recall": 0.87654}
        },
    )


def test_summary_csv_has_deterministic_excel_safe_rows():
    from app.services.rag_eval_export import serialize_rag_eval_run_summary_csv

    payload = serialize_rag_eval_run_summary_csv(_completed_run())

    assert payload.startswith(b"\xef\xbb\xbf")
    text = payload.decode("utf-8-sig")
    assert "\r\n" in text
    rows = list(csv.reader(io.StringIO(text, newline="")))
    assert rows[0] == ["Section", "Field", "Value"]
    assert rows[1:13] == [
        ["Run", "id", "11"],
        ["Run", "configuration_id", "7"],
        ["Run", "status", "completed"],
        ["Run", "stage", "finished"],
        ["Run", "progress", "100.0"],
        ["Run", "completed_examples", "80"],
        ["Run", "total_examples", "80"],
        ["Run", "queued_at", "2026-08-12T08:00:00+00:00"],
        ["Run", "started_at", ""],
        ["Run", "completed_at", "2026-08-12T08:10:00+00:00"],
        ["Run", "suite_version", "rag-eval-v1"],
        ["Run", "suite_content_hash", "abc123"],
    ]
    assert ["Configuration", "a_formula", "'=SUM(1,2)"] in rows
    assert ["Configuration", "'+formula_key", "safe"] in rows
    assert [
        "Configuration",
        "quoted",
        'comma, quote " and\nnewline',
    ] in rows
    assert ["Configuration", "nested", '{"a":"α","z":true}'] in rows
    assert ["Overall metrics", "faithfulness", "0.91234"] in rows
    assert [
        "Category metrics",
        "direct_retrieval / context_recall",
        "0.87654",
    ] in rows


def test_summary_json_has_deterministic_structured_sections():
    from app.services.rag_eval_export import serialize_rag_eval_run_summary_json

    payload = serialize_rag_eval_run_summary_json(_completed_run())

    assert not payload.startswith(b"\xef\xbb\xbf")
    assert payload == serialize_rag_eval_run_summary_json(_completed_run())
    assert json.loads(payload) == {
        "category_metrics": {
            "direct_retrieval": {"context_recall": 0.87654}
        },
        "configuration": {
            "+formula_key": "safe",
            "a_formula": "=SUM(1,2)",
            "nested": {"a": "α", "z": True},
            "quoted": 'comma, quote " and\nnewline',
        },
        "overall_metrics": {"faithfulness": 0.91234},
        "resolved_pipeline": {"model": "gpt-4o-mini"},
        "run": {
            "completed_at": "2026-08-12T08:10:00Z",
            "completed_examples": 80,
            "configuration_id": 7,
            "id": 11,
            "progress": 100.0,
            "queued_at": "2026-08-12T08:00:00Z",
            "stage": "finished",
            "started_at": None,
            "status": "completed",
            "suite_content_hash": "abc123",
            "suite_version": "rag-eval-v1",
            "total_examples": 80,
        },
    }


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (None, ""),
        (True, "true"),
        (False, "false"),
        (-1.25, -1.25),
        ("  @SUM(A1:A2)", "'  @SUM(A1:A2)"),
        ('comma, quote " and\nnewline', 'comma, quote " and\nnewline'),
    ],
)
def test_excel_cell_conversion(value, expected):
    from app.services.rag_eval_export import _excel_cell

    assert _excel_cell(value) == expected


def test_category_metrics_must_be_mappings():
    from app.services.rag_eval_export import serialize_rag_eval_run_summary_csv

    run = _completed_run().model_copy(
        update={"category_metrics": {"direct_retrieval": 0.5}}
    )

    with pytest.raises(TypeError, match="category metric group must be a mapping"):
        serialize_rag_eval_run_summary_csv(run)

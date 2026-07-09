from __future__ import annotations

import pytest

from athenaeum.runtime.minimal import build_report_output
from athenaeum.runtime.models import SchemaValidationError, validate_json_schema_subset
from athenaeum.schemas import ReportOutput, output_schema


def test_report_output_schema_requires_core_fields() -> None:
    schema = output_schema("report")

    assert "report_markdown" in schema["required"]
    assert "title" in schema["required"]
    assert schema["properties"]["report_markdown"]["type"] == "string"


def test_minimal_report_output_validates_against_schema() -> None:
    output = build_report_output("Should we ship?", run_id="abc12345", seed=7)

    validated = ReportOutput.model_validate(output.model_dump(mode="json"))

    assert validated.run_id == "abc12345"
    assert validated.report_markdown.startswith("# ATHENAEUM Report")
    assert validated.claims
    assert validated.citations


def test_schema_subset_rejects_missing_required_report_field() -> None:
    with pytest.raises(SchemaValidationError, match="report_markdown"):
        validate_json_schema_subset({"title": "x", "question": "q", "summary": "s"}, output_schema("report"))


def test_schema_subset_rejects_wrong_report_markdown_type() -> None:
    with pytest.raises(SchemaValidationError, match="report_markdown"):
        validate_json_schema_subset(
            {"title": "x", "question": "q", "summary": "s", "report_markdown": 123},
            output_schema("report"),
        )

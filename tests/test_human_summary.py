from dataclasses import FrozenInstanceError

import pandas as pd
import pytest

import vzor
from vzor._human_summary import format_schema_drift_summary, format_validation_summary
from vzor.agent_output import build_agent_output


@pytest.mark.parametrize(
    ("dataframe", "expected"),
    [
        (pd.DataFrame(), "Inspection completed: 0 rows, 0 columns, 0 nullable columns."),
        (pd.DataFrame({"id": [1]}), "Inspection completed: 1 row, 1 column, 0 nullable columns."),
        (
            pd.DataFrame({"id": [1, 2], "region": ["North", None], "enabled": [True, False]}),
            "Inspection completed: 2 rows, 3 columns, 1 nullable column.",
        ),
    ],
)
def test_inspection_human_summary_is_exact_and_derived(
    dataframe: pd.DataFrame,
    expected: str,
) -> None:
    report = vzor.inspect(dataframe)

    assert report.human_summary == expected
    assert report.human_summary == report.human_summary
    assert "human_summary" not in repr(report)
    with pytest.raises(FrozenInstanceError):
        report.summary.row_count = 0


def test_validation_human_summary_uses_existing_core_counts_and_cli_formatter() -> None:
    dataframe = pd.DataFrame({"id": [1]})
    valid = vzor.validate(dataframe, vzor.suggest_schema(dataframe))
    invalid = vzor.validate(
        dataframe,
        vzor.SuggestedDatasetSchema(
            columns=(
                vzor.SuggestedColumnSchema(
                    name="missing",
                    logical_type="integer",
                    nullable=False,
                    constraints=vzor.SuggestedConstraints(
                        numeric_range=None,
                        allowed_values=None,
                    ),
                ),
            )
        ),
    )

    assert valid.human_summary == "Validation passed: 0 errors, 0 warnings."
    assert invalid.human_summary == "Validation failed: 2 errors, 0 warnings."
    assert valid.human_summary == build_agent_output("validation", valid.result)["human_summary"]
    assert invalid.human_summary == build_agent_output("validation", invalid.result)["human_summary"]
    assert invalid.human_summary == invalid.human_summary
    assert "human_summary" not in repr(invalid)


@pytest.mark.parametrize(
    ("is_valid", "errors", "warnings", "expected"),
    [
        (False, 1, 0, "Validation failed: 1 error, 0 warnings."),
        (False, 2, 1, "Validation failed: 2 errors, 1 warning."),
        (True, 0, 2, "Validation passed: 0 errors, 2 warnings."),
    ],
)
def test_validation_formatter_pluralizes_all_supported_counts(
    is_valid: bool,
    errors: int,
    warnings: int,
    expected: str,
) -> None:
    assert format_validation_summary(is_valid, errors, warnings) == expected


@pytest.mark.parametrize(
    ("before", "after", "expected"),
    [
        (
            pd.DataFrame({"id": [1]}),
            pd.DataFrame({"id": [1]}),
            "Comparison completed: no changes detected.",
        ),
        (
            pd.DataFrame({"id": [1, 2]}),
            pd.DataFrame({"id": [1, 2, 1]}),
            "Comparison completed: no column changes; row count changed from 2 to 3.",
        ),
        (
            pd.DataFrame({"id": [1]}),
            pd.DataFrame({"id": [1], "added": [1]}),
            "Comparison completed: 1 added, 0 removed, 0 changed columns.",
        ),
        (
            pd.DataFrame({"id": [1], "removed": [1]}),
            pd.DataFrame({"id": [1]}),
            "Comparison completed: 0 added, 1 removed, 0 changed columns.",
        ),
        (
            pd.DataFrame({"value": [1]}),
            pd.DataFrame({"value": ["one"]}),
            "Comparison completed: 0 added, 0 removed, 1 changed column.",
        ),
        (
            pd.DataFrame({"old": [1], "changed": [1]}),
            pd.DataFrame({"changed": ["one"], "new": [1]}),
            "Comparison completed: 1 added, 1 removed, 1 changed column.",
        ),
        (
            pd.DataFrame({"old": [1], "changed": [1]}),
            pd.DataFrame({"changed": ["one", "one"], "new": [1, 1]}),
            "Comparison completed: 1 added, 1 removed, 1 changed column; row count changed from 1 to 2.",
        ),
    ],
)
def test_comparison_human_summary_covers_each_factual_case(
    before: pd.DataFrame,
    after: pd.DataFrame,
    expected: str,
) -> None:
    report = vzor.compare(before, after)

    assert report.human_summary == expected
    assert report.human_summary == report.human_summary
    assert "human_summary" not in repr(report)
    with pytest.raises(FrozenInstanceError):
        report.summary.has_changes = False


@pytest.mark.parametrize(
    ("before", "after", "expected"),
    [
        (
            pd.DataFrame(),
            pd.DataFrame(),
            "Schema drift check passed: no structural drift detected.",
        ),
        (
            pd.DataFrame({"removed": [1]}),
            pd.DataFrame(),
            "Schema drift detected: 1 error, 0 warnings.",
        ),
        (
            pd.DataFrame({"first": [1], "second": [2]}),
            pd.DataFrame(),
            "Schema drift detected: 2 errors, 0 warnings.",
        ),
        (
            pd.DataFrame(),
            pd.DataFrame({"added": [1]}),
            "Schema drift detected: 0 errors, 1 warning.",
        ),
        (
            pd.DataFrame(),
            pd.DataFrame({"first": [1], "second": [2]}),
            "Schema drift detected: 0 errors, 2 warnings.",
        ),
        (
            pd.DataFrame({"removed": [1]}),
            pd.DataFrame({"added": [1]}),
            "Schema drift detected: 1 error, 1 warning.",
        ),
    ],
)
def test_schema_drift_human_summary_covers_structural_severities(
    before: pd.DataFrame,
    after: pd.DataFrame,
    expected: str,
) -> None:
    report = vzor.schema_drift(before, after)

    assert report.human_summary == expected
    assert report.human_summary == report.human_summary
    assert "human_summary" not in repr(report)
    with pytest.raises(FrozenInstanceError):
        report.summary.has_drift = False


def test_schema_drift_formatter_pluralizes_without_interpreting_issues() -> None:
    assert format_schema_drift_summary(False, 0, 0) == (
        "Schema drift check passed: no structural drift detected."
    )
    assert format_schema_drift_summary(True, 2, 1) == (
        "Schema drift detected: 2 errors, 1 warning."
    )


def test_inspection_human_summary_matches_the_existing_cli_text() -> None:
    report = vzor.inspect(pd.DataFrame({"id": [1, 2], "region": ["North", None]}))

    assert report.human_summary == build_agent_output("inspection", report)["human_summary"]


def test_human_summary_is_the_only_public_api_addition() -> None:
    public_before_v032 = {
        "ColumnProfile",
        "ComparisonReport",
        "ComparisonSummary",
        "DatasetProfile",
        "InspectionReport",
        "InspectionSummary",
        "NumericStats",
        "ObservedColumnSchema",
        "ObservedDatasetSchema",
        "ObservedRange",
        "SchemaDriftReport",
        "SchemaDriftSummary",
        "SuggestedColumnSchema",
        "SuggestedConstraints",
        "SuggestedDatasetSchema",
        "SuggestedNumericRange",
        "ValidationReport",
        "ValidationSummary",
        "compare",
        "inspect",
        "observed_schema",
        "profile",
        "schema_drift",
        "suggest_schema",
        "validate",
        "version",
    }
    reports = (
        vzor.inspect(pd.DataFrame()),
        vzor.validate(pd.DataFrame(), vzor.SuggestedDatasetSchema(columns=())),
        vzor.compare(pd.DataFrame(), pd.DataFrame()),
        vzor.schema_drift(pd.DataFrame(), pd.DataFrame()),
    )

    assert set(vzor.__all__) == public_before_v032
    assert all(isinstance(report.human_summary, str) for report in reports)

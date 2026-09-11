from dataclasses import FrozenInstanceError

import numpy as np
import pandas as pd
import pytest

import vzor
from vzor.validation import ValidationIssue, ValidationResult


def test_validation_report_delegates_counts_and_filters_issues_in_order() -> None:
    issues = (
        ValidationIssue("warning-a", "warning", "first", None, None),
        ValidationIssue("error-a", "error", "second", None, None),
        ValidationIssue("warning-b", "warning", "third", None, None),
        ValidationIssue("error-b", "error", "fourth", None, None),
    )
    report = vzor.ValidationReport(
        result=ValidationResult(False, 2, 2, issues),
        summary=vzor.ValidationSummary(False, 2, 2),
    )

    assert report.issues is issues
    assert report.is_valid is False
    assert report.error_count == 2
    assert report.warning_count == 2
    assert report.issue_count == 4
    assert isinstance(report.errors, tuple)
    assert isinstance(report.warnings, tuple)
    assert tuple(issue.code for issue in report.errors) == ("error-a", "error-b")
    assert tuple(issue.code for issue in report.warnings) == ("warning-a", "warning-b")
    with pytest.raises(FrozenInstanceError):
        report.summary.error_count = 0


def test_validation_report_empty_filtered_collections_are_tuples() -> None:
    dataframe = pd.DataFrame({"id": [1]})
    report = vzor.validate(dataframe, vzor.suggest_schema(dataframe))

    assert report.is_valid is True
    assert report.issue_count == 0
    assert report.errors == ()
    assert report.warnings == ()


def test_comparison_report_delegates_counts_and_filters_columns_in_core_order() -> None:
    before = pd.DataFrame(
        {
            "unchanged_a": [1, 1],
            "removed_a": [1, 1],
            "changed_a": [1, 1],
            "removed_b": [2, 2],
            "changed_b": [2, 2],
            "unchanged_b": [2, 2],
        }
    )
    after = pd.DataFrame(
        {
            "added_z": [0, 0],
            "unchanged_b": [2, 2],
            "changed_b": ["two", "two"],
            "added_a": [3, 3],
            "changed_a": ["one", "one"],
            "unchanged_a": [1, 1],
        }
    )
    report = vzor.compare(before, after)

    assert report.has_changes is True
    assert report.row_count_changed is False
    assert report.before_row_count == report.after_row_count == 2
    assert report.added_columns == 2
    assert report.removed_columns == 2
    assert report.changed_columns == 2
    assert report.unchanged_columns == 2
    assert all(
        isinstance(columns, tuple)
        for columns in (report.added, report.removed, report.changed, report.unchanged)
    )
    assert tuple(column.name for column in report.added) == ("added_z", "added_a")
    assert tuple(column.name for column in report.removed) == ("removed_a", "removed_b")
    assert tuple(column.name for column in report.changed) == ("changed_a", "changed_b")
    assert tuple(column.name for column in report.unchanged) == (
        "unchanged_a",
        "unchanged_b",
    )


def test_comparison_report_empty_filters_and_row_count_delegates() -> None:
    before = pd.DataFrame({"id": [1, 2]})
    report = vzor.compare(before, pd.DataFrame({"id": [1, 2, 1]}))

    assert report.has_changes is True
    assert report.row_count_changed is True
    assert report.before_row_count == 2
    assert report.after_row_count == 3
    assert report.added == report.removed == report.changed == ()
    assert tuple(column.name for column in report.unchanged) == ("id",)


def test_schema_drift_report_delegates_counts_and_filters_issues_in_order() -> None:
    before = pd.DataFrame({"removed_a": [1], "removed_b": [2]})
    after = pd.DataFrame({"added_z": [3], "added_a": [4]})
    report = vzor.schema_drift(before, after)

    assert report.has_drift is True
    assert report.error_count == 2
    assert report.warning_count == 2
    assert report.issue_count == 4
    assert isinstance(report.errors, tuple)
    assert isinstance(report.warnings, tuple)
    assert tuple(issue.column for issue in report.errors) == ("removed_a", "removed_b")
    assert tuple(issue.column for issue in report.warnings) == ("added_z", "added_a")


def test_schema_drift_report_empty_filtered_collections_are_tuples() -> None:
    dataframe = pd.DataFrame({"id": [1]})
    report = vzor.schema_drift(dataframe, dataframe.copy())

    assert report.has_drift is False
    assert report.error_count == report.warning_count == report.issue_count == 0
    assert report.errors == ()
    assert report.warnings == ()


def test_inspection_report_delegates_every_summary_count() -> None:
    dataframe = pd.DataFrame(
        {
            "integer": [1, 2],
            "float": [1.0, np.nan],
            "category": pd.Categorical(["A", "B"]),
            "string": pd.Series(["A", "B"], dtype="string"),
            "boolean": [True, False],
            "datetime": pd.to_datetime(["2025-01-01", "2025-01-02"]),
            "unknown": pd.Series([None, None], dtype="object"),
        }
    )
    report = vzor.inspect(dataframe)

    assert report.row_count == 2
    assert report.column_count == 7
    assert report.nullable_columns == 2
    assert report.numeric_columns == 2
    assert report.categorical_columns == 1
    assert report.string_columns == 1
    assert report.boolean_columns == 1
    assert report.datetime_columns == 1
    assert report.unknown_columns == 1


def test_existing_column_lookup_is_exact_case_sensitive_and_deterministic() -> None:
    dataframe = pd.DataFrame({"First": [1], "last": [2]})
    datasets = (
        vzor.profile(dataframe),
        vzor.observed_schema(dataframe),
        vzor.suggest_schema(dataframe),
    )
    empty_datasets = (
        vzor.profile(pd.DataFrame()),
        vzor.observed_schema(pd.DataFrame()),
        vzor.suggest_schema(pd.DataFrame()),
    )

    for dataset in datasets:
        assert dataset.column("First") is dataset.columns[0]
        assert dataset.column("last") is dataset.columns[-1]
        assert dataset.column("First") is dataset.column("First")
        with pytest.raises(KeyError, match="Column 'first' not found"):
            dataset.column("first")
    for dataset in empty_datasets:
        with pytest.raises(KeyError, match="Column 'missing' not found"):
            dataset.column("missing")


def test_convenience_properties_do_not_change_repr_equality_or_hash() -> None:
    dataframe = pd.DataFrame({"id": [1, 2]})
    report = vzor.inspect(dataframe)
    equivalent = vzor.inspect(dataframe.copy())
    original_repr = repr(report)
    original_hash = hash(report)

    _ = (
        report.row_count,
        report.column_count,
        report.nullable_columns,
        report.numeric_columns,
        report.human_summary,
    )

    assert report == equivalent
    assert hash(report) == original_hash == hash(equivalent)
    assert repr(report) == original_repr
    assert "row_count:" in original_repr
    assert "human_summary" not in original_repr


def test_python_ux_adds_no_top_level_symbols() -> None:
    expected = {
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

    assert set(vzor.__all__) == expected
    assert not hasattr(vzor, "get_column")
    assert not hasattr(vzor, "find_column")

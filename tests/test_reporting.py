from dataclasses import FrozenInstanceError
from importlib import import_module

import numpy as np
import pandas as pd
import pytest

import vzor
import vzor.comparison as comparison_module
import vzor.validation as validation_module

schema_drift_module = import_module("vzor.schema_drift")


def suggested_column(
    name: str,
    logical_type: str,
    *,
    nullable: bool = False,
    numeric_range: tuple[float | None, float | None] | None = None,
    allowed_values: tuple[str | bool, ...] | None = None,
) -> vzor.SuggestedColumnSchema:
    return vzor.SuggestedColumnSchema(
        name=name,
        logical_type=logical_type,
        nullable=nullable,
        constraints=vzor.SuggestedConstraints(
            numeric_range=(
                None
                if numeric_range is None
                else vzor.SuggestedNumericRange(*numeric_range)
            ),
            allowed_values=allowed_values,
        ),
    )


def schema(*columns: vzor.SuggestedColumnSchema) -> vzor.SuggestedDatasetSchema:
    return vzor.SuggestedDatasetSchema(columns=columns)


def issue_codes(report: vzor.ValidationReport) -> tuple[str, ...]:
    return tuple(issue.code for issue in report.issues)


def drift_codes(report: vzor.SchemaDriftReport) -> tuple[str, ...]:
    return tuple(issue.code for issue in report.issues)


def test_validate_valid_dataset_uses_core_result_and_delegates_issues() -> None:
    dataframe = pd.DataFrame({"id": [1, 2], "region": pd.Categorical(["A", "B"])})
    report = vzor.validate(dataframe, vzor.suggest_schema(dataframe))

    assert isinstance(report, vzor.ValidationReport)
    assert isinstance(report.summary, vzor.ValidationSummary)
    assert report.summary.is_valid is True
    assert report.summary.error_count == report.summary.warning_count == 0
    assert report.summary.issue_count == 0
    assert report.issues is report.result.issues
    assert report.issues == ()


def test_reports_are_deterministic_for_empty_and_all_null_datasets() -> None:
    empty = pd.DataFrame()
    empty_schema = schema()
    empty_validation = vzor.validate(empty, empty_schema)
    empty_comparison = vzor.compare(empty, empty.copy())
    empty_drift = vzor.schema_drift(empty, empty.copy())
    all_null = pd.DataFrame({"optional": pd.Series([None, None], dtype="object")})
    all_null_schema = vzor.suggest_schema(all_null)

    assert empty_validation.summary.is_valid is True
    assert empty_comparison.summary.has_changes is False
    assert empty_drift.summary.has_drift is False
    assert vzor.validate(all_null, all_null_schema) == vzor.validate(all_null, all_null_schema)
    assert vzor.compare(all_null, all_null.copy()) == vzor.compare(all_null, all_null.copy())
    assert vzor.schema_drift(all_null, all_null.copy()) == vzor.schema_drift(
        all_null, all_null.copy()
    )


@pytest.mark.parametrize(
    ("dataframe", "contract", "expected_code"),
    [
        (
            pd.DataFrame({"id": [1]}),
            schema(suggested_column("id", "integer"), suggested_column("region", "string")),
            "missing_column",
        ),
        (
            pd.DataFrame({"id": [1], "extra": [2]}),
            schema(suggested_column("id", "integer")),
            "unexpected_column",
        ),
        (
            pd.DataFrame({"id": ["one"]}),
            schema(suggested_column("id", "integer")),
            "type_mismatch",
        ),
        (
            pd.DataFrame({"value": pd.Series([1.0, np.nan], dtype="float64")}),
            schema(suggested_column("value", "float", nullable=False)),
            "null_not_allowed",
        ),
        (
            pd.DataFrame({"region": pd.Series(pd.Categorical(["South"]))}),
            schema(
                suggested_column(
                    "region",
                    "categorical",
                    allowed_values=("North",),
                )
            ),
            "value_not_allowed",
        ),
        (
            pd.DataFrame({"enabled": [False]}),
            schema(suggested_column("enabled", "boolean", allowed_values=(True,))),
            "value_not_allowed",
        ),
        (
            pd.DataFrame({"value": pd.Series([11.0], dtype="float64")}),
            schema(suggested_column("value", "float", numeric_range=(0.0, 10.0))),
            "range_violation",
        ),
    ],
)
def test_validate_reports_each_existing_validation_code(
    dataframe: pd.DataFrame,
    contract: vzor.SuggestedDatasetSchema,
    expected_code: str,
) -> None:
    report = vzor.validate(dataframe, contract)

    assert report.summary.is_valid is False
    assert issue_codes(report) == (expected_code,)
    assert report.summary.issue_count == 1


def test_validate_nan_is_ignored_and_infinities_follow_the_existing_range_policy() -> None:
    contract = schema(
        suggested_column("value", "float", nullable=True, numeric_range=(0.0, 10.0))
    )
    nan_report = vzor.validate(
        pd.DataFrame({"value": pd.Series([np.nan, 5.0], dtype="float64")}),
        contract,
    )
    positive_report = vzor.validate(
        pd.DataFrame({"value": pd.Series([np.inf], dtype="float64")}),
        contract,
    )
    negative_report = vzor.validate(
        pd.DataFrame({"value": pd.Series([-np.inf], dtype="float64")}),
        contract,
    )

    assert nan_report.summary.is_valid is True
    assert issue_codes(positive_report) == ("range_violation",)
    assert issue_codes(negative_report) == ("range_violation",)


def test_validate_multiple_issues_preserve_core_order_summary_repr_and_frozen_state() -> None:
    contract = schema(
        suggested_column("missing", "integer"),
        suggested_column("value", "float", nullable=False, numeric_range=(0.0, 10.0)),
    )
    report = vzor.validate(
        pd.DataFrame({"value": pd.Series([np.nan, 12.0], dtype="float64"), "extra": [1, 2]}),
        contract,
    )

    assert issue_codes(report) == (
        "missing_column",
        "null_not_allowed",
        "range_violation",
        "unexpected_column",
    )
    assert report.summary.error_count == report.summary.issue_count == 4
    assert repr(report) == repr(report)
    assert repr(report).index("summary:") < repr(report).index("issues:")
    with pytest.raises(FrozenInstanceError):
        report.summary.error_count = 0
    with pytest.raises(FrozenInstanceError):
        report.result.issues = ()


def test_validate_preserves_existing_input_errors_and_normalizes_once(monkeypatch) -> None:
    calls = 0
    normalize = validation_module._normalize_dataframe

    def counting_normalize(dataframe: pd.DataFrame):
        nonlocal calls
        calls += 1
        return normalize(dataframe)

    monkeypatch.setattr(validation_module, "_normalize_dataframe", counting_normalize)
    report = vzor.validate(pd.DataFrame({"id": [1]}), schema(suggested_column("id", "integer")))

    assert report.summary.is_valid is True
    assert calls == 1
    with pytest.raises(TypeError, match="SuggestedDatasetSchema"):
        vzor.validate(pd.DataFrame({"id": [1]}), object())
    with pytest.raises(ValueError, match="Duplicate column names"):
        vzor.validate(
            pd.DataFrame([[1, 2]], columns=["id", "id"]),
            schema(suggested_column("id", "integer")),
        )
    with pytest.raises(TypeError, match="mixed or unsupported object values"):
        vzor.validate(
            pd.DataFrame({"id": ["one", 2]}),
            schema(suggested_column("id", "string")),
        )


def test_compare_identical_and_row_count_only_datasets() -> None:
    before = pd.DataFrame({"id": [1, 2], "region": ["North", "South"]})
    identical = vzor.compare(before, before.copy())
    rows_changed = vzor.compare(
        before,
        pd.DataFrame({"id": [1, 2, 1], "region": ["North", "South", "North"]}),
    )

    assert identical.summary.has_changes is False
    assert identical.summary.unchanged_columns == 2
    assert tuple(column.status for column in identical.columns) == ("unchanged", "unchanged")
    assert rows_changed.summary.has_changes is True
    assert rows_changed.summary.row_count_changed is True
    assert rows_changed.summary.changed_columns == 0


@pytest.mark.parametrize(
    ("before", "after", "status", "change"),
    [
        (pd.DataFrame({"id": [1]}), pd.DataFrame({"id": [1], "added": [2]}), "added", None),
        (pd.DataFrame({"id": [1], "removed": [2]}), pd.DataFrame({"id": [1]}), "removed", None),
        (pd.DataFrame({"value": [1]}), pd.DataFrame({"value": ["one"]}), "changed", "logical_type_changed"),
        (pd.DataFrame({"value": [1.0, 2.0]}), pd.DataFrame({"value": [1.0, np.nan]}), "changed", "nullability_changed"),
        (pd.DataFrame({"value": [1, 1]}), pd.DataFrame({"value": [1, 2]}), "changed", "unique_count_changed"),
        (pd.DataFrame({"value": [1.0, 2.0]}), pd.DataFrame({"value": [1.0, 3.0]}), "changed", "range_changed"),
        (
            pd.DataFrame({"region": pd.Categorical(["North", "South"])}),
            pd.DataFrame({"region": pd.Categorical(["North", "West"])}),
            "changed",
            "observed_values_changed",
        ),
    ],
)
def test_compare_preserves_all_existing_change_semantics(
    before: pd.DataFrame,
    after: pd.DataFrame,
    status: str,
    change: str | None,
) -> None:
    report = vzor.compare(before, after)
    column = report.columns[-1]

    assert column.status == status
    if change is None:
        assert column.changes == ()
    else:
        assert change in column.changes


def test_compare_reordering_rename_summary_order_repr_frozen_and_normalization(monkeypatch) -> None:
    before = pd.DataFrame({"first": [1], "second": [2]})
    reordered = vzor.compare(before, before[["second", "first"]])
    renamed = vzor.compare(before, pd.DataFrame({"first": [1], "renamed": [2]}))
    calls = 0
    normalize = comparison_module._normalize_dataframe

    def counting_normalize(dataframe: pd.DataFrame):
        nonlocal calls
        calls += 1
        return normalize(dataframe)

    monkeypatch.setattr(comparison_module, "_normalize_dataframe", counting_normalize)
    normalized = vzor.compare(before, before)

    assert reordered.summary.has_changes is False
    assert tuple(column.name for column in reordered.columns) == ("first", "second")
    assert tuple(column.status for column in renamed.columns) == ("unchanged", "removed", "added")
    assert renamed.summary.removed_columns == renamed.summary.added_columns == 1
    assert normalized.columns is normalized.result.columns
    assert calls == 2
    assert repr(renamed) == repr(renamed)
    assert repr(renamed).index("summary:") < repr(renamed).index("columns:")
    with pytest.raises(FrozenInstanceError):
        renamed.summary.has_changes = False


def test_schema_drift_preserves_structural_policy_and_ignores_factual_only_changes() -> None:
    base = pd.DataFrame({"id": [1, 2], "value": [1.0, 2.0]})
    no_drift = vzor.schema_drift(base, pd.DataFrame({"id": [1, 2, 3], "value": [1.0, 2.0, 3.0]}))
    added = vzor.schema_drift(base, pd.DataFrame({"id": [1, 2], "value": [1.0, 2.0], "extra": [0, 0]}))
    removed = vzor.schema_drift(base, pd.DataFrame({"id": [1, 2]}))
    logical_type = vzor.schema_drift(pd.DataFrame({"value": [1]}), pd.DataFrame({"value": ["one"]}))
    nullable_more = vzor.schema_drift(pd.DataFrame({"value": [1.0, 2.0]}), pd.DataFrame({"value": [1.0, np.nan]}))
    nullable_less = vzor.schema_drift(pd.DataFrame({"value": [1.0, np.nan]}), pd.DataFrame({"value": [1.0, 2.0]}))

    assert no_drift.summary.has_drift is False
    assert drift_codes(added) == ("column_added",)
    assert added.issues[0].severity == "warning"
    assert drift_codes(removed) == ("column_removed",)
    assert removed.issues[0].severity == "error"
    assert drift_codes(logical_type) == ("logical_type_changed",)
    assert nullable_more.issues[0].severity == "error"
    assert nullable_less.issues[0].severity == "warning"


@pytest.mark.parametrize(
    ("before", "after"),
    [
        (pd.DataFrame({"value": [1, 1]}), pd.DataFrame({"value": [1, 2]})),
        (pd.DataFrame({"value": [1.0, 2.0]}), pd.DataFrame({"value": [1.0, 3.0]})),
        (
            pd.DataFrame({"region": pd.Categorical(["North", "South"])}),
            pd.DataFrame({"region": pd.Categorical(["North", "West"])}),
        ),
        (pd.DataFrame({"id": [1, 2]}), pd.DataFrame({"id": [1, 2, 3]})),
    ],
)
def test_schema_drift_ignores_non_structural_changes(
    before: pd.DataFrame,
    after: pd.DataFrame,
) -> None:
    report = vzor.schema_drift(before, after)

    assert report.summary.has_drift is False
    assert report.issues == ()


def test_schema_drift_order_summary_repr_frozen_and_normalization(monkeypatch) -> None:
    before = pd.DataFrame({"old": [1, 2], "typed": [1, 2], "nullable": [1.0, 2.0]})
    after = pd.DataFrame(
        {"typed": ["one", "two"], "nullable": [1.0, np.nan], "new": [1, 2]}
    )
    report = vzor.schema_drift(before, after)
    calls = 0
    normalize = schema_drift_module._normalize_dataframe

    def counting_normalize(dataframe: pd.DataFrame):
        nonlocal calls
        calls += 1
        return normalize(dataframe)

    monkeypatch.setattr(schema_drift_module, "_normalize_dataframe", counting_normalize)
    normalized = vzor.schema_drift(before, after)

    assert drift_codes(report) == (
        "column_removed",
        "logical_type_changed",
        "nullability_changed",
        "column_added",
    )
    assert report.summary.issue_count == 4
    assert report.issues is report.result.issues
    assert normalized == report
    assert calls == 2
    assert repr(report) == repr(report)
    assert repr(report).index("summary:") < repr(report).index("issues:")
    with pytest.raises(FrozenInstanceError):
        report.summary.has_drift = False


def test_reporting_public_api_is_exact_and_existing_api_remains_available() -> None:
    additions = {
        "validate",
        "compare",
        "schema_drift",
        "ValidationReport",
        "ValidationSummary",
        "ComparisonReport",
        "ComparisonSummary",
        "SchemaDriftReport",
        "SchemaDriftSummary",
    }
    previous = {"version", "profile", "observed_schema", "suggest_schema", "inspect"}

    assert additions <= set(vzor.__all__)
    assert previous <= set(vzor.__all__)
    assert callable(vzor.validate)
    assert callable(vzor.compare)
    assert callable(vzor.schema_drift)
    for internal_name in (
        "_validate_dataset_schema",
        "validate_dataset_file",
        "compare_datasets",
        "schema_drift_datasets",
    ):
        assert not hasattr(vzor, internal_name)

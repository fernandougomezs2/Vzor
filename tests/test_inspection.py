from dataclasses import FrozenInstanceError
from inspect import signature

import pandas as pd
import pytest

import vzor
import vzor.inspection as inspection_module


def mixed_dataframe() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "id": [1, 2, 3],
            "sales": [10.0, 20.0, None],
            "active": [True, False, True],
            "region": ["North", "South", "North"],
            "category": pd.Categorical(["A", "B", "A"]),
            "date": pd.to_datetime(["2026-01-01", "2026-01-02", "2026-01-03"]),
            "unknown": pd.Series([None, None, None], dtype=object),
        }
    )


def test_inspect_has_a_simple_public_signature_and_returns_immutable_models() -> None:
    report = vzor.inspect(mixed_dataframe())

    assert list(signature(vzor.inspect).parameters) == ["df"]
    assert isinstance(report, vzor.InspectionReport)
    assert isinstance(report.summary, vzor.InspectionSummary)
    with pytest.raises(FrozenInstanceError):
        report.profile = vzor.profile(pd.DataFrame())
    with pytest.raises(FrozenInstanceError):
        report.summary.row_count = 0


def test_inspect_matches_all_specialized_apis() -> None:
    df = mixed_dataframe()

    report = vzor.inspect(df)

    assert report.profile == vzor.profile(df)
    assert report.observed_schema == vzor.observed_schema(df)
    assert report.suggested_schema == vzor.suggest_schema(df)


def test_inspect_matches_specialized_apis_for_clone_regression_edge_cases() -> None:
    dataframe = pd.DataFrame(
        {
            "integer": pd.Series([1, pd.NA, 1, 4], dtype="Int64"),
            "float": [1.0, float("nan"), float("inf"), float("-inf")],
            "boolean": pd.Series([True, pd.NA, False, True], dtype="boolean"),
            "datetime": pd.to_datetime(["2026-01-01", None, "2026-01-03", "2026-01-04"]),
            "text": ["área", None, "東京", "área"],
            "category": pd.Categorical(["small", "large", "small", "medium"]),
            "all_null": pd.Series([None, None, None, None], dtype=object),
            "high_cardinality_small": ["uno", "dos", "tres", "cuatro"],
        }
    )

    first = vzor.inspect(dataframe)
    second = vzor.inspect(dataframe)

    assert first == second
    assert first.profile == vzor.profile(dataframe)
    assert first.observed_schema == vzor.observed_schema(dataframe)
    assert first.suggested_schema == vzor.suggest_schema(dataframe)


def test_mixed_dataframe_summary_counts_existing_results() -> None:
    report = vzor.inspect(mixed_dataframe())

    assert report.summary == vzor.InspectionSummary(
        row_count=3,
        column_count=7,
        nullable_columns=2,
        numeric_columns=2,
        categorical_columns=1,
        string_columns=1,
        boolean_columns=1,
        datetime_columns=1,
        unknown_columns=1,
    )


def test_empty_dataframe_produces_an_empty_report_and_summary() -> None:
    report = vzor.inspect(pd.DataFrame())

    assert report.summary == vzor.InspectionSummary(
        row_count=0,
        column_count=0,
        nullable_columns=0,
        numeric_columns=0,
        categorical_columns=0,
        string_columns=0,
        boolean_columns=0,
        datetime_columns=0,
        unknown_columns=0,
    )
    assert report.profile.columns == ()
    assert report.observed_schema.columns == ()
    assert report.suggested_schema.columns == ()


def test_typed_empty_dataframe_counts_logical_types_without_nullable_columns() -> None:
    df = pd.DataFrame(
        {
            "integer": pd.Series(dtype="int64"),
            "float": pd.Series(dtype="float64"),
            "string": pd.Series(dtype="string"),
            "boolean": pd.Series(dtype="boolean"),
            "categorical": pd.Series(pd.Categorical([])),
            "datetime": pd.Series(dtype="datetime64[ns]"),
        }
    )

    report = vzor.inspect(df)

    assert report.summary == vzor.InspectionSummary(
        row_count=0,
        column_count=6,
        nullable_columns=0,
        numeric_columns=2,
        categorical_columns=1,
        string_columns=1,
        boolean_columns=1,
        datetime_columns=1,
        unknown_columns=0,
    )
    assert report.profile == vzor.profile(df)
    assert report.observed_schema == vzor.observed_schema(df)
    assert report.suggested_schema == vzor.suggest_schema(df)


def test_unknown_all_null_counts_as_nullable_and_unknown() -> None:
    report = vzor.inspect(
        pd.DataFrame({"unknown": pd.Series([None, None], dtype=object)})
    )

    assert report.summary.row_count == 2
    assert report.summary.column_count == 1
    assert report.summary.nullable_columns == 1
    assert report.summary.unknown_columns == 1
    assert report.profile.column("unknown").logical_type == "unknown"


def test_order_unicode_names_and_index_are_preserved_or_ignored_as_expected() -> None:
    df = pd.DataFrame(
        {"東京": [1, 2], "área": ["Norte", "Sur"], "客户": [True, False]},
        index=pd.Index(["fila-1", "fila-2"], name="índice"),
    )

    report = vzor.inspect(df)
    expected_names = ("東京", "área", "客户")

    assert tuple(column.name for column in report.profile.columns) == expected_names
    assert tuple(column.name for column in report.observed_schema.columns) == expected_names
    assert tuple(column.name for column in report.suggested_schema.columns) == expected_names
    assert report.summary.column_count == 3


@pytest.mark.parametrize(
    ("value", "error", "message"),
    [
        ([], TypeError, "Vzor expects a pandas.DataFrame"),
        (pd.DataFrame({1: [1]}), TypeError, "column names must be strings"),
        (
            pd.DataFrame({"mixed": ["A", 1]}),
            TypeError,
            "mixed or unsupported object values",
        ),
    ],
)
def test_inspect_preserves_shared_input_errors(value, error, message: str) -> None:
    with pytest.raises(error, match=message):
        vzor.inspect(value)


def test_inspect_rejects_duplicate_names() -> None:
    df = pd.DataFrame([[1, 2]], columns=["duplicate", "duplicate"])

    with pytest.raises(ValueError, match="Duplicate column names are not supported"):
        vzor.inspect(df)


def test_inspect_preserves_uint64_overflow_behavior() -> None:
    df = pd.DataFrame({"value": pd.Series([2**63], dtype="uint64")})

    with pytest.raises(OverflowError, match="outside the supported i64 range"):
        vzor.inspect(df)


def test_inspect_normalizes_the_dataframe_once(monkeypatch) -> None:
    calls = 0
    normalize = inspection_module._normalize_dataframe

    def counting_normalize(df: pd.DataFrame):
        nonlocal calls
        calls += 1
        return normalize(df)

    monkeypatch.setattr(inspection_module, "_normalize_dataframe", counting_normalize)

    report = vzor.inspect(mixed_dataframe())

    assert calls == 1
    assert report.summary.column_count == 7


def test_existing_public_api_and_version_remain_available() -> None:
    df = pd.DataFrame({"x": [1, 2, 3]})

    assert vzor.profile(df).column("x").logical_type == "integer"
    assert vzor.observed_schema(df).column("x").logical_type == "integer"
    assert vzor.suggest_schema(df).column("x").logical_type == "integer"
    assert vzor.inspect(df).profile.column("x").logical_type == "integer"
    assert vzor.version() == "0.3.2"

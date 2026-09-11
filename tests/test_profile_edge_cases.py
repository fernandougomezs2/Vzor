from dataclasses import FrozenInstanceError

import numpy as np
import pandas as pd
import pytest

import vzor


def test_completely_empty_and_typed_empty_dataframes_are_stable():
    empty = vzor.profile(pd.DataFrame())
    typed = vzor.profile(
        pd.DataFrame(
            {
                "id": pd.Series(dtype="int64"),
                "sales": pd.Series(dtype="float64"),
                "name": pd.Series(dtype="string"),
            }
        )
    )

    assert empty.row_count == 0
    assert empty.column_count == 0
    assert empty.columns == ()

    assert typed.row_count == 0
    assert typed.column_count == 3
    for column in typed.columns:
        assert column.count == 0
        assert column.null_count == 0
        assert column.unique_count == 0
        assert column.numeric_stats is None


def test_all_null_columns_match_pandas_missing_semantics():
    df = pd.DataFrame(
        {
            "object_none": pd.Series([None, None, None], dtype="object"),
            "nullable_integer": pd.Series([pd.NA, pd.NA, pd.NA], dtype="Int64"),
            "float_nan": pd.Series([np.nan, np.nan, np.nan], dtype="float64"),
            "datetime_nat": pd.Series([pd.NaT] * 3, dtype="datetime64[ns]"),
            "nullable_string": pd.Series([pd.NA, pd.NA, pd.NA], dtype="string"),
            "nullable_boolean": pd.Series([pd.NA, pd.NA, pd.NA], dtype="boolean"),
        }
    )

    result = vzor.profile(df)

    assert result.column("object_none").logical_type == "unknown"
    for name in df.columns:
        column = result.column(name)
        assert column.count == 3
        assert column.null_count == int(df[name].isna().sum()) == 3
        assert column.unique_count == 0
        assert column.numeric_stats is None


def test_empty_and_special_strings_are_not_null_tokens():
    values = ["", "NULL", "null", "NaN", "None", " ", "0", None]
    column = vzor.profile(
        pd.DataFrame({"text": pd.Series(values, dtype="object")})
    ).column("text")

    assert column.logical_type == "string"
    assert column.count == 8
    assert column.null_count == 1
    assert column.unique_count == 7


def test_cardinality_and_count_invariants_across_supported_types():
    df = pd.DataFrame(
        {
            "integer": pd.Series([1, 1, 2, pd.NA, pd.NA], dtype="Int64"),
            "string": pd.Series(["A", "A", "B", pd.NA, pd.NA], dtype="string"),
            "boolean": pd.Series(
                [True, False, True, pd.NA, pd.NA], dtype="boolean"
            ),
            "float": pd.Series([0.0, -0.0, 1.0, np.nan, 1.0], dtype="float64"),
            "categorical": pd.Series(
                ["x", "x", "y", None, None], dtype="category"
            ),
        }
    )

    result = vzor.profile(df)

    for column in result.columns:
        assert column.count == result.row_count == 5
        assert 0 <= column.null_count <= column.count
        assert 0 <= column.unique_count <= column.count - column.null_count
        assert column.unique_count == 2

    assert result.column("float").null_count == 1
    assert result.column("float").unique_count == 2
    assert result.column("boolean").numeric_stats is None
    assert result.column("categorical").numeric_stats is None


def test_nan_and_infinities_keep_their_distinct_pandas_semantics():
    result = vzor.profile(
        pd.DataFrame(
            {
                "nan": [1.0, np.nan, 2.0],
                "positive_infinity": [1.0, np.inf, 2.0],
                "negative_infinity": [-1.0, -np.inf, -3.0],
                "only_non_finite": [np.inf, -np.inf, np.nan],
            }
        )
    )

    nan = result.column("nan")
    assert nan.count == 3
    assert nan.null_count == 1
    assert nan.unique_count == 2
    assert nan.numeric_stats.mean == pytest.approx(1.5)

    positive = result.column("positive_infinity")
    assert positive.null_count == 0
    assert positive.unique_count == 3
    assert positive.numeric_stats.min == pytest.approx(1.0)
    assert positive.numeric_stats.max == pytest.approx(2.0)
    assert positive.numeric_stats.mean == pytest.approx(1.5)
    assert positive.numeric_stats.median == pytest.approx(1.5)
    assert positive.numeric_stats.p25 == pytest.approx(1.25)
    assert positive.numeric_stats.p75 == pytest.approx(1.75)

    negative = result.column("negative_infinity")
    assert negative.null_count == 0
    assert negative.unique_count == 3
    assert negative.numeric_stats.min == pytest.approx(-3.0)
    assert negative.numeric_stats.max == pytest.approx(-1.0)
    assert negative.numeric_stats.mean == pytest.approx(-2.0)

    only_non_finite = result.column("only_non_finite")
    assert only_non_finite.null_count == 1
    assert only_non_finite.unique_count == 2
    assert only_non_finite.numeric_stats is None


def test_column_names_order_and_custom_index_are_preserved_correctly():
    names = ["", "ventas totales", "área", "客户", "column.with.dots"]
    df = pd.DataFrame([[1, 2, 3, 4, 5]], columns=names, index=[100])

    result = vzor.profile(df)

    assert [column.name for column in result.columns] == names
    assert result.row_count == 1
    assert result.column_count == len(names)
    assert all(column.name != "index" for column in result.columns)

    ranged = vzor.profile(pd.DataFrame({"value": [1, 2, 3]}))
    assert ranged.row_count == 3
    assert ranged.column_count == 1
    assert [column.name for column in ranged.columns] == ["value"]


def test_public_models_lookup_column_count_and_nested_immutability():
    result = vzor.profile(pd.DataFrame({"value": [1, 2, 3]}))
    column = result.column("value")
    stats = column.numeric_stats

    assert result.column_count == len(result.columns)
    assert isinstance(result.columns, tuple)
    assert result.column("value") is column

    with pytest.raises(KeyError, match="Column 'missing' not found"):
        result.column("missing")
    with pytest.raises(FrozenInstanceError):
        result.row_count = 100
    with pytest.raises(FrozenInstanceError):
        column.null_count = 0
    with pytest.raises(FrozenInstanceError):
        stats.mean = 50.0


def test_numeric_statistics_percentiles_and_single_value_are_consistent():
    stats = vzor.profile(pd.DataFrame({"value": [1, 2, 3, 4]})).column(
        "value"
    ).numeric_stats

    assert stats.min == pytest.approx(1.0)
    assert stats.max == pytest.approx(4.0)
    assert stats.mean == pytest.approx(2.5)
    assert stats.median == pytest.approx(2.5)
    assert stats.p25 == pytest.approx(1.75)
    assert stats.p50 == pytest.approx(stats.median)
    assert stats.p75 == pytest.approx(3.25)

    single = vzor.profile(pd.DataFrame({"value": [42]})).column(
        "value"
    ).numeric_stats
    assert {
        single.min,
        single.max,
        single.mean,
        single.median,
        single.p25,
        single.p50,
        single.p75,
    } == {42.0}


def test_main_phase_two_regression_scenario():
    df = pd.DataFrame(
        {
            "id": [1, 2, 3],
            "sales": [10.0, 20.0, None],
            "region": ["North", "South", "North"],
        }
    )

    result = vzor.profile(df)

    assert result.row_count == 3
    assert result.column_count == 3
    assert result.column("id").logical_type == "integer"
    assert result.column("sales").null_count == 1
    assert result.column("sales").unique_count == 2
    assert result.column("sales").numeric_stats.mean == pytest.approx(15.0)
    assert result.column("region").logical_type == "string"
    assert result.column("region").unique_count == 2


def test_ten_thousand_row_smoke_profile_has_expected_results():
    size = 10_000
    df = pd.DataFrame(
        {
            "id": range(size),
            "amount": [float(index % 100) for index in range(size)],
            "label": [f"group-{index % 10}" for index in range(size)],
        }
    )

    result = vzor.profile(df)

    assert result.row_count == size
    assert result.column_count == 3
    assert result.column("id").unique_count == size
    assert result.column("amount").unique_count == 100
    assert result.column("amount").numeric_stats.mean == pytest.approx(49.5)
    assert result.column("label").unique_count == 10
    assert all(column.count == size for column in result.columns)


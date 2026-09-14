from dataclasses import FrozenInstanceError
from importlib import import_module

import numpy as np
import pandas as pd
import pytest

import vzor


def test_profile_returns_public_immutable_models():
    result = vzor.profile(
        pd.DataFrame(
            {
                "id": [1, 2, 3],
                "sales": [10.0, 20.0, None],
                "region": ["North", "South", "North"],
            }
        )
    )

    assert isinstance(result, vzor.DatasetProfile)
    assert result.row_count == 3
    assert result.column_count == 3
    assert isinstance(result.columns, tuple)
    assert result.column("id").logical_type == "integer"
    assert result.column("sales").null_count == 1
    assert result.column("sales").unique_count == 2
    assert result.column("sales").numeric_stats.mean == pytest.approx(15.0)
    assert result.column("region").logical_type == "string"

    with pytest.raises(FrozenInstanceError):
        result.row_count = 4
    with pytest.raises(FrozenInstanceError):
        result.column("id").count = 4
    with pytest.raises(FrozenInstanceError):
        result.column("sales").numeric_stats.mean = 4.0


def test_column_lookup_reports_missing_name():
    result = vzor.profile(pd.DataFrame({"id": [1]}))

    with pytest.raises(KeyError, match="Column 'missing' not found"):
        result.column("missing")


def test_supported_pandas_dtypes_are_mapped_to_logical_types():
    result = vzor.profile(
        pd.DataFrame(
            {
                "integer": pd.Series([1, 2], dtype="int64"),
                "float": pd.Series([1.5, 2.5], dtype="float64"),
                "boolean": pd.Series([True, False], dtype="bool"),
                "string": pd.Series(["a", "b"], dtype="string"),
                "datetime": pd.to_datetime(["2026-01-01", "2026-01-02"]),
                "categorical": pd.Series(["a", "b"], dtype="category"),
                "object_string": pd.Series(["x", "y"], dtype="object"),
            }
        )
    )

    assert [column.logical_type for column in result.columns] == [
        "integer",
        "float",
        "boolean",
        "string",
        "datetime",
        "categorical",
        "string",
    ]
    assert result.column("categorical").numeric_stats is None
    assert result.column("datetime").numeric_stats is None


def test_mixed_object_column_is_rejected():
    df = pd.DataFrame({"mixed": pd.Series(["A", 10, "B"], dtype="object")})

    with pytest.raises(TypeError, match="Column 'mixed'"):
        vzor.profile(df)


def test_non_string_category_is_rejected():
    df = pd.DataFrame({"category": pd.Series([1, 2], dtype="category")})

    with pytest.raises(TypeError, match="Column 'category' contains a non-string category"):
        vzor.profile(df)


def test_pandas_missing_values_map_to_null():
    result = vzor.profile(
        pd.DataFrame(
            {
                "none": pd.Series(["a", None], dtype="object"),
                "na": pd.Series([1, pd.NA], dtype="Int64"),
                "nat": pd.Series([pd.Timestamp("2026-01-01"), pd.NaT]),
                "nan": pd.Series([1.0, np.nan], dtype="float64"),
            }
        )
    )

    assert all(column.null_count == 1 for column in result.columns)
    assert result.column("nan").unique_count == 1


def test_infinity_is_non_null_but_excluded_from_statistics():
    result = vzor.profile(pd.DataFrame({"value": [1.0, np.inf, -np.inf]}))
    column = result.column("value")

    assert column.null_count == 0
    assert column.unique_count == 3
    assert column.numeric_stats.min == pytest.approx(1.0)
    assert column.numeric_stats.max == pytest.approx(1.0)
    assert column.numeric_stats.mean == pytest.approx(1.0)


def test_integer_and_float_statistics_are_returned():
    result = vzor.profile(
        pd.DataFrame(
            {
                "integer": [1, 2, 3, 4],
                "float": [1.0, 2.0, 3.0, 4.0],
            }
        )
    )

    for name in ("integer", "float"):
        stats = result.column(name).numeric_stats
        assert stats.min == pytest.approx(1.0)
        assert stats.max == pytest.approx(4.0)
        assert stats.mean == pytest.approx(2.5)
        assert stats.median == pytest.approx(2.5)
        assert stats.p25 == pytest.approx(1.75)
        assert stats.p50 == pytest.approx(2.5)
        assert stats.p75 == pytest.approx(3.25)


def test_empty_dataframes_are_supported():
    empty = vzor.profile(pd.DataFrame())
    typed = vzor.profile(
        pd.DataFrame(
            {
                "id": pd.Series(dtype="int64"),
                "sales": pd.Series(dtype="float64"),
            }
        )
    )

    assert empty.row_count == 0
    assert empty.column_count == 0
    assert empty.columns == ()
    assert typed.row_count == 0
    assert typed.column_count == 2
    assert all(column.count == 0 for column in typed.columns)


def test_invalid_dataframe_shapes_and_inputs_are_rejected():
    duplicate_columns = pd.DataFrame([[1, 2]], columns=["value", "value"])
    non_string_columns = pd.DataFrame([[1, 2]], columns=[1, 2])

    with pytest.raises(ValueError, match="Duplicate column names are not supported"):
        vzor.profile(duplicate_columns)
    with pytest.raises(TypeError, match="column names must be strings"):
        vzor.profile(non_string_columns)
    with pytest.raises(TypeError, match="expects a pandas.DataFrame"):
        vzor.profile([1, 2, 3])


def test_public_symbols_and_version_remain_available():
    assert callable(vzor.profile)
    assert vzor.version() == "0.4.0"
    assert vzor.DatasetProfile is not None
    assert vzor.ColumnProfile is not None
    assert vzor.NumericStats is not None


def test_internal_binding_maps_core_errors_to_python_exceptions():
    core = import_module("vzor._vzor_core")

    with pytest.raises(
        TypeError,
        match="Column 'value' expected integer values but received float",
    ):
        core.profile_dataset([("value", "integer", [1.5])])

    with pytest.raises(
        ValueError,
        match="Column 'second' has 2 values; expected 1",
    ):
        core.profile_dataset(
            [
                ("first", "integer", [1]),
                ("second", "integer", [1, 2]),
            ]
        )

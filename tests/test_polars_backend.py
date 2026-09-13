"""Public contract tests for the optional direct Polars backend."""

from __future__ import annotations

import math
import sys

import pandas as pd
import pytest

import vzor

pl = pytest.importorskip("polars")


@pytest.mark.parametrize(
    ("dtype", "expected"),
    [
        (pl.Int8, "integer"), (pl.Int16, "integer"), (pl.Int32, "integer"),
        (pl.Int64, "integer"), (pl.UInt8, "integer"), (pl.UInt16, "integer"),
        (pl.UInt32, "integer"), (pl.UInt64, "integer"), (pl.Float32, "float"),
        (pl.Float64, "float"), (pl.Boolean, "boolean"), (pl.String, "string"),
        (pl.Categorical, "categorical"), (pl.Date, "datetime"), (pl.Datetime("us"), "datetime"),
        (pl.Null, "unknown"),
    ],
)
def test_polars_dtype_matrix(dtype: pl.DataType, expected: str) -> None:
    if dtype == pl.Boolean:
        values = [True, None]
    elif dtype == pl.String or dtype == pl.Categorical:
        values = ["one", None]
    elif dtype == pl.Date:
        values = [None, None]
    elif isinstance(dtype, pl.Datetime) or dtype == pl.Null:
        values = [None, None]
    else:
        values = [1, None]
    profile = vzor.profile(pl.DataFrame({"value": pl.Series(values, dtype=dtype)}))
    assert profile.column("value").logical_type == expected


def test_polars_float_null_nan_infinities_and_negative_zero() -> None:
    profile = vzor.profile(pl.DataFrame({"value": [float("nan"), float("inf"), -float("inf"), -0.0]}))
    column = profile.column("value")
    assert column.null_count == 1
    assert column.unique_count == 3
    assert column.numeric_stats is not None
    assert column.numeric_stats.min == 0.0
    assert math.copysign(1.0, column.numeric_stats.min) == -1.0


def test_polars_unicode_empty_and_categorical_observations() -> None:
    dataframe = pl.DataFrame({
        "text": ["á", "ñ", "😀", "", "NULL", "NaN", "None", None],
        "category": pl.Series(["north", "south", "north", None, "south", "north", "south", "north"], dtype=pl.Categorical),
    })
    observed = vzor.observed_schema(dataframe)
    assert observed.column("text").observed_values == ("á", "ñ", "😀", "", "NULL", "NaN", "None")
    assert observed.column("category").observed_values == ("north", "south")
    suggested = vzor.suggest_schema(dataframe)
    assert suggested.column("category").constraints.allowed_values == ("north", "south")


def test_polars_enum_maps_to_categorical() -> None:
    dataframe = pl.DataFrame({"value": pl.Series(["north", "south"], dtype=pl.Enum(["north", "south"]))})
    assert vzor.profile(dataframe).column("value").logical_type == "categorical"


def test_polars_uint64_boundary_matches_i64_policy() -> None:
    assert vzor.profile(pl.DataFrame({"value": pl.Series([2**63 - 1], dtype=pl.UInt64)})).column("value").count == 1
    with pytest.raises(OverflowError, match="outside the supported i64 range"):
        vzor.profile(pl.DataFrame({"value": pl.Series([2**63], dtype=pl.UInt64)}))


def test_polars_pandas_parity_for_public_models_and_cross_validation() -> None:
    pandas_frame = pd.DataFrame({
        "id": pd.Series([1, 2, None], dtype="Int64"),
        "score": [1.5, float("nan"), 3.5],
        "enabled": pd.Series([True, False, None], dtype="boolean"),
        "region": pd.Categorical(["north", "south", "north"]),
        "text": ["á", "", None],
    })
    polars_frame = pl.DataFrame({
        "id": pl.Series([1, 2, None], dtype=pl.Int64),
        "score": [1.5, float("nan"), 3.5],
        "enabled": pl.Series([True, False, None], dtype=pl.Boolean),
        "region": pl.Series(["north", "south", "north"], dtype=pl.Categorical),
        "text": ["á", "", None],
    })
    assert vzor.profile(pandas_frame) == vzor.profile(polars_frame)
    assert vzor.observed_schema(pandas_frame) == vzor.observed_schema(polars_frame)
    assert vzor.suggest_schema(pandas_frame) == vzor.suggest_schema(polars_frame)
    assert vzor.inspect(pandas_frame) == vzor.inspect(polars_frame)
    schema = vzor.suggest_schema(pandas_frame)
    assert vzor.validate(polars_frame, schema).is_valid
    assert vzor.validate(pandas_frame, vzor.suggest_schema(polars_frame)).is_valid


def test_polars_mixed_backend_compare_and_drift_are_supported() -> None:
    pandas_frame = pd.DataFrame({"id": [1, 2], "region": pd.Categorical(["north", "south"])})
    polars_frame = pl.DataFrame({"id": [1, 2], "region": pl.Series(["north", "south"], dtype=pl.Categorical)})
    assert not vzor.compare(pandas_frame, polars_frame).has_changes
    assert not vzor.compare(polars_frame, pandas_frame).has_changes
    assert not vzor.schema_drift(pandas_frame, polars_frame).has_drift
    assert not vzor.schema_drift(polars_frame, pandas_frame).has_drift


def test_polars_lazyframe_and_unsupported_inputs_are_rejected() -> None:
    with pytest.raises(TypeError, match="materialized polars.DataFrame"):
        vzor.profile(pl.DataFrame({"value": [1]}).lazy())
    with pytest.raises(TypeError, match="pandas.DataFrame or polars.DataFrame"):
        vzor.profile({"value": [1]})


def test_polars_reports_keep_repr_html_and_determinism(tmp_path) -> None:
    dataframe = pl.DataFrame({"id": [1, 2], "name": ["uno", "dos"]})
    first = vzor.inspect(dataframe)
    second = vzor.inspect(dataframe)
    assert first == second
    assert repr(first) == repr(second)
    output = tmp_path / "report.html"
    first.to_html(output)
    assert "Inspection completed" in output.read_text(encoding="utf-8")


def test_pandas_dispatch_does_not_import_optional_polars(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "polars", None)
    assert vzor.profile(pd.DataFrame({"value": [1]})).row_count == 1

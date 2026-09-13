"""Optional direct Polars-to-core normalization; Polars is never imported by Vzor startup."""

from __future__ import annotations

import math
from typing import Any

from ._pandas_adapter import NormalizedColumn


def is_polars_dataframe(value: Any) -> bool:
    import polars as pl

    return isinstance(value, pl.DataFrame)


def is_polars_lazyframe(value: Any) -> bool:
    import polars as pl

    return isinstance(value, pl.LazyFrame)


def normalize_polars_dataframe(df: Any) -> list[NormalizedColumn]:
    """Read Polars columns directly, without converting through pandas."""
    import polars as pl

    if not isinstance(df, pl.DataFrame):
        if isinstance(df, pl.LazyFrame):
            raise TypeError("Vzor requires a materialized polars.DataFrame; polars.LazyFrame is unsupported")
        raise TypeError("Vzor expects a polars.DataFrame")
    if any(not isinstance(name, str) for name in df.columns):
        raise TypeError("DataFrame column names must be strings")

    return [
        (name, _infer_logical_type(series.dtype), _normalized_values(series, name), False)
        for name, series in zip(df.columns, df.iter_columns(), strict=True)
    ]


def _infer_logical_type(dtype: Any) -> str:
    import polars as pl

    if dtype == pl.Null:
        return "unknown"
    if dtype.is_integer():
        return "integer"
    if dtype.is_float():
        return "float"
    if dtype == pl.Boolean:
        return "boolean"
    if dtype == pl.String:
        return "string"
    if dtype == pl.Categorical or isinstance(dtype, pl.Enum):
        return "categorical"
    if dtype == pl.Date or isinstance(dtype, pl.Datetime):
        return "datetime"
    raise TypeError(f"Column has unsupported Polars dtype '{dtype}'")


def _normalized_values(series: Any, column_name: str):
    logical_type = _infer_logical_type(series.dtype)
    return (_normalize_value(value, logical_type, column_name) for value in series)


def _normalize_value(value: Any, logical_type: str, column_name: str) -> object:
    if value is None:
        return None
    if logical_type == "integer":
        normalized = int(value)
        if not -(2**63) <= normalized <= 2**63 - 1:
            raise OverflowError(f"Column '{column_name}' contains an integer outside the supported i64 range")
        return normalized
    if logical_type == "float":
        normalized = float(value)
        return None if math.isnan(normalized) else normalized
    if logical_type == "boolean":
        return bool(value)
    if logical_type in {"string", "categorical"}:
        if isinstance(value, str):
            return value
    elif logical_type == "datetime":
        return value.isoformat()
    raise TypeError(f"Column '{column_name}' contains an unsupported value")

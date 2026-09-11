"""Shared pandas-to-core normalization for Vzor's public APIs."""

from typing import Any

import pandas as pd
from pandas.api.types import (
    is_bool_dtype,
    is_datetime64_any_dtype,
    is_float_dtype,
    is_integer_dtype,
    is_object_dtype,
    is_string_dtype,
)

NormalizedColumn = tuple[str, str, list[object]]


def _normalize_dataframe(df: pd.DataFrame) -> list[NormalizedColumn]:
    if not isinstance(df, pd.DataFrame):
        raise TypeError("Vzor expects a pandas.DataFrame")
    if df.columns.duplicated().any():
        raise ValueError("Duplicate column names are not supported")
    if any(not isinstance(name, str) for name in df.columns):
        raise TypeError("DataFrame column names must be strings")

    columns = []
    for name in df.columns:
        series = df[name]
        logical_type = _infer_logical_type(series)
        values = [_normalize_value(value, logical_type, name) for value in series]
        columns.append((name, logical_type, values))

    return columns


def _infer_logical_type(series: pd.Series) -> str:
    dtype = series.dtype

    if isinstance(dtype, pd.CategoricalDtype):
        return "categorical"
    if is_datetime64_any_dtype(dtype):
        return "datetime"
    if is_bool_dtype(dtype):
        return "boolean"
    if is_integer_dtype(dtype):
        return "integer"
    if is_float_dtype(dtype):
        return "float"
    if is_object_dtype(dtype):
        non_null_values = series[~series.isna()]
        if non_null_values.empty:
            return "unknown"
        if all(isinstance(value, str) for value in non_null_values):
            return "string"
        raise TypeError(f"Column '{series.name}' has mixed or unsupported object values")
    if is_string_dtype(dtype):
        return "string"

    raise TypeError(f"Column '{series.name}' has unsupported dtype '{dtype}'")


def _normalize_value(value: Any, logical_type: str, column_name: str) -> object:
    if pd.isna(value):
        return None

    if logical_type == "integer":
        normalized = int(value)
        if not -(2**63) <= normalized <= 2**63 - 1:
            raise OverflowError(
                f"Column '{column_name}' contains an integer outside the supported i64 range"
            )
        return normalized
    if logical_type == "float":
        return float(value)
    if logical_type == "boolean":
        return bool(value)
    if logical_type == "string":
        if isinstance(value, str):
            return value
    elif logical_type == "categorical":
        if isinstance(value, str):
            return value
        raise TypeError(f"Column '{column_name}' contains a non-string category")
    elif logical_type == "datetime":
        return value.isoformat()

    raise TypeError(f"Column '{column_name}' contains an unsupported value")

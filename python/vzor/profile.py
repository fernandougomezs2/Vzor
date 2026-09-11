"""Public profiling adapter for pandas DataFrames."""

from typing import Any

import pandas as pd

from ._pandas_adapter import _normalize_dataframe
from ._vzor_core import profile_dataset as _profile_dataset
from .models import ColumnProfile, DatasetProfile, NumericStats


def profile(df: pd.DataFrame) -> DatasetProfile:
    """Profile a pandas DataFrame using the Vzor Rust core."""
    return _build_dataset_profile(_profile_dataset(_normalize_dataframe(df)))


def _build_dataset_profile(data: dict[str, Any]) -> DatasetProfile:
    columns = tuple(_build_column_profile(column) for column in data["columns"])
    return DatasetProfile(row_count=data["row_count"], columns=columns)


def _build_column_profile(data: dict[str, Any]) -> ColumnProfile:
    stats_data = data["numeric_stats"]
    numeric_stats = NumericStats(**stats_data) if stats_data is not None else None
    return ColumnProfile(
        name=data["name"],
        logical_type=data["logical_type"],
        count=data["count"],
        null_count=data["null_count"],
        unique_count=data["unique_count"],
        numeric_stats=numeric_stats,
    )

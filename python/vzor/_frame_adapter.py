"""Private backend dispatch for supported materialized DataFrames."""

from __future__ import annotations

from typing import Any

import pandas as pd

from ._pandas_adapter import NormalizedColumn, _normalize_dataframe as _normalize_pandas


def normalize_dataframe(df: Any) -> list[NormalizedColumn]:
    """Normalize a supported DataFrame without exposing backend abstractions."""
    if isinstance(df, pd.DataFrame):
        return _normalize_pandas(df)

    try:
        from ._polars_adapter import (
            is_polars_dataframe,
            is_polars_lazyframe,
            normalize_polars_dataframe,
        )
    except ModuleNotFoundError as error:
        if error.name != "polars":
            raise
        is_polars_dataframe = lambda value: False
        is_polars_lazyframe = lambda value: False

    if is_polars_dataframe(df):
        return normalize_polars_dataframe(df)
    if is_polars_lazyframe(df):
        raise TypeError("Vzor requires a materialized polars.DataFrame; polars.LazyFrame is unsupported")
    raise TypeError("Vzor expects a pandas.DataFrame or polars.DataFrame")

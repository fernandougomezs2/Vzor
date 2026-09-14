"""Regression coverage for the private typed/fallback transport classification."""

from __future__ import annotations

import pandas as pd
import pytest

import vzor
from vzor._pandas_adapter import _normalize_dataframe as normalize_pandas

pl = pytest.importorskip("polars")
from vzor._polars_adapter import normalize_polars_dataframe


def test_polars_non_null_numeric_and_boolean_use_raw_typed_transport() -> None:
    columns = normalize_polars_dataframe(
        pl.DataFrame(
            {
                "signed": pl.Series([1, 2], dtype=pl.Int64),
                "unsigned": pl.Series([1, 2], dtype=pl.UInt32),
                "float": pl.Series([1.0, float("nan")], dtype=pl.Float64),
                "boolean": pl.Series([True, False], dtype=pl.Boolean),
            }
        )
    )
    assert [column[3] for column in columns] == [True, True, True, True]


def test_nullable_and_uint64_polars_use_checked_fallback_transport() -> None:
    columns = normalize_polars_dataframe(
        pl.DataFrame(
            {
                "nullable": pl.Series([1, None], dtype=pl.Int64),
                "flag": pl.Series([True, None], dtype=pl.Boolean),
                "uint64": pl.Series([1, 2], dtype=pl.UInt64),
                "text": ["a", "b"],
            }
        )
    )
    assert [column[3] for column in columns] == [False, False, False, False]


def test_sliced_frames_and_nullable_cross_backend_keep_public_parity() -> None:
    pandas_frame = pd.DataFrame(
        {
            "integer": pd.Series([0, 1, 2, 3], dtype="Int64"),
            "boolean": pd.Series([True, False, None, True], dtype="boolean"),
            "text": ["á", "", None, "東京"],
        }
    ).iloc[1:]
    polars_frame = pl.DataFrame(
        {
            "integer": pl.Series([0, 1, 2, 3], dtype=pl.Int64),
            "boolean": pl.Series([True, False, None, True], dtype=pl.Boolean),
            "text": ["á", "", None, "東京"],
        }
    ).slice(1)
    assert vzor.profile(pandas_frame) == vzor.profile(polars_frame)
    assert vzor.inspect(pandas_frame) == vzor.inspect(polars_frame)
    # The existing pandas scalar transport supports sliced Series safely; it
    # does not claim a contiguous borrowed buffer.
    assert normalize_pandas(pandas_frame)[0][3] is True

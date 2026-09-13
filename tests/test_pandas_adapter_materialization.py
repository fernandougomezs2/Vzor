import numpy as np
import pandas as pd

from vzor._pandas_adapter import _normalize_dataframe


def test_normalization_selects_raw_scalars_and_preserves_dtype_values() -> None:
    dataframe = pd.DataFrame(
        {
            "int64": pd.Series([1, -2, 3], dtype="int64"),
            "uint": pd.Series([0, 2**40, 2**41], dtype="uint64"),
            "float32": pd.Series([0.0, -0.0, np.inf], dtype="float32"),
            "nullable_int": pd.Series([1, pd.NA, 3], dtype="Int64"),
            "boolean": pd.Series([True, pd.NA, False], dtype="boolean"),
            "text": pd.Series(["", "área", pd.NA], dtype="string"),
            "object": pd.Series(["東京", None, "東京"], dtype=object),
            "category": pd.Series(["A", "B", None], dtype="category"),
            "datetime": pd.to_datetime(["2026-01-01", None, "2026-01-03"]),
            "datetime_tz": pd.to_datetime(["2026-01-01T00:00:00Z", None, "2026-01-03T00:00:00Z"], utc=True),
            "all_null": pd.Series([None, None, None], dtype=object),
        }
    )

    columns = _normalize_dataframe(dataframe)
    assert [raw_scalars for _, _, _, raw_scalars in columns] == [
        True,
        False,
        True,
        False,
        False,
        False,
        False,
        False,
        False,
        False,
        False,
    ]
    normalized = {
        name: (logical_type, list(values)) for name, logical_type, values, _ in columns
    }
    assert normalized["int64"] == ("integer", [1, -2, 3])
    assert normalized["uint"] == ("integer", [0, 2**40, 2**41])
    assert normalized["float32"][0] == "float"
    assert normalized["float32"][1] == [0.0, -0.0, float("inf")]
    assert normalized["nullable_int"] == ("integer", [1, None, 3])
    assert normalized["boolean"] == ("boolean", [True, None, False])
    assert normalized["text"] == ("string", ["", "área", None])
    assert normalized["object"] == ("string", ["東京", None, "東京"])
    assert normalized["category"] == ("categorical", ["A", "B", None])
    assert normalized["datetime"] == ("datetime", ["2026-01-01T00:00:00", None, "2026-01-03T00:00:00"])
    assert normalized["datetime_tz"] == ("datetime", ["2026-01-01T00:00:00+00:00", None, "2026-01-03T00:00:00+00:00"])
    assert normalized["all_null"] == ("unknown", [None, None, None])

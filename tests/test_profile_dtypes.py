import numpy as np
import pandas as pd
import pytest

import vzor


def test_signed_integer_dtypes_and_nullable_integer_statistics():
    result = vzor.profile(
        pd.DataFrame(
            {
                "int32": pd.Series([-2, 0, 2, 4], dtype="int32"),
                "int64": pd.Series([-4, -2, 0, 2], dtype="int64"),
                "nullable": pd.Series([1, pd.NA, 3, 5], dtype="Int64"),
            }
        )
    )

    assert all(column.logical_type == "integer" for column in result.columns)
    assert result.column("nullable").null_count == 1
    assert result.column("nullable").unique_count == 3

    stats = result.column("nullable").numeric_stats
    assert stats.min == pytest.approx(1.0)
    assert stats.max == pytest.approx(5.0)
    assert stats.mean == pytest.approx(3.0)
    assert stats.median == pytest.approx(3.0)
    assert stats.p25 == pytest.approx(2.0)
    assert stats.p50 == pytest.approx(3.0)
    assert stats.p75 == pytest.approx(4.0)


def test_large_signed_and_supported_unsigned_integers_do_not_wrap():
    result = vzor.profile(
        pd.DataFrame(
            {
                "signed": pd.Series([-(2**40), 0, 2**40], dtype="int64"),
                "unsigned": pd.Series([0, 2**40, 2**41], dtype="uint64"),
            }
        )
    )

    assert result.column("signed").logical_type == "integer"
    assert result.column("signed").numeric_stats.min == pytest.approx(-(2**40))
    assert result.column("signed").numeric_stats.max == pytest.approx(2**40)
    assert result.column("unsigned").logical_type == "integer"
    assert result.column("unsigned").unique_count == 3
    assert result.column("unsigned").numeric_stats.max == pytest.approx(2**41)


def test_uint64_above_i64_range_fails_with_column_context():
    df = pd.DataFrame({"too_large": pd.Series([2**63], dtype="uint64")})

    with pytest.raises(OverflowError, match="too_large"):
        vzor.profile(df)


def test_float32_and_float64_have_the_same_logical_type_and_statistics():
    result = vzor.profile(
        pd.DataFrame(
            {
                "float32": pd.Series([1.25, -2.5, 1.25], dtype="float32"),
                "float64": pd.Series([1.25, -2.5, 1.25], dtype="float64"),
            }
        )
    )

    for name in ("float32", "float64"):
        column = result.column(name)
        assert column.logical_type == "float"
        assert column.unique_count == 2
        assert column.numeric_stats.min == pytest.approx(-2.5)
        assert column.numeric_stats.max == pytest.approx(1.25)
        assert column.numeric_stats.mean == pytest.approx(0.0)


def test_nullable_boolean_and_string_dtypes_preserve_semantics():
    result = vzor.profile(
        pd.DataFrame(
            {
                "flag": pd.Series([True, False, True, pd.NA], dtype="boolean"),
                "label": pd.Series(["", "A", "A", pd.NA], dtype="string"),
            }
        )
    )

    flag = result.column("flag")
    assert flag.logical_type == "boolean"
    assert flag.null_count == 1
    assert flag.unique_count == 2
    assert flag.numeric_stats is None

    label = result.column("label")
    assert label.logical_type == "string"
    assert label.null_count == 1
    assert label.unique_count == 2
    assert label.numeric_stats is None


def test_datetime_naive_repeated_nat_and_all_nat_columns():
    result = vzor.profile(
        pd.DataFrame(
            {
                "dates": pd.to_datetime(
                    ["2026-01-01", "2026-01-01", "2026-01-02", None]
                ),
                "all_nat": pd.Series([pd.NaT] * 4, dtype="datetime64[ns]"),
            }
        )
    )

    dates = result.column("dates")
    assert dates.logical_type == "datetime"
    assert dates.null_count == 1
    assert dates.unique_count == 2
    assert dates.numeric_stats is None

    all_nat = result.column("all_nat")
    assert all_nat.logical_type == "datetime"
    assert all_nat.null_count == 4
    assert all_nat.unique_count == 0
    assert all_nat.numeric_stats is None


def test_timezone_aware_datetime_uses_the_existing_datetime_transport():
    df = pd.DataFrame(
        {"event_at": pd.to_datetime(["2026-01-01T00:00:00Z", None], utc=True)}
    )

    column = vzor.profile(df).column("event_at")

    assert column.logical_type == "datetime"
    assert column.null_count == 1
    assert column.unique_count == 1
    assert column.numeric_stats is None


def test_string_categories_cover_null_repetition_single_and_empty_inputs():
    result = vzor.profile(
        pd.DataFrame(
            {
                "region": pd.Series(
                    ["North", "South", "North", None], dtype="category"
                ),
                "single": pd.Series(["Only"] * 4, dtype="category"),
            }
        )
    )

    region = result.column("region")
    assert region.logical_type == "categorical"
    assert region.null_count == 1
    assert region.unique_count == 2
    assert region.numeric_stats is None
    assert result.column("single").unique_count == 1

    empty_dtype = pd.CategoricalDtype(categories=["North", "South"])
    empty = vzor.profile(
        pd.DataFrame({"region": pd.Series([], dtype=empty_dtype)})
    ).column("region")
    assert empty.logical_type == "categorical"
    assert empty.count == 0
    assert empty.null_count == 0
    assert empty.unique_count == 0


def test_non_string_category_remains_an_explicit_type_error():
    df = pd.DataFrame({"category": pd.Series([1, 2, 1], dtype="category")})

    with pytest.raises(TypeError, match="Column 'category'.*non-string category"):
        vzor.profile(df)


@pytest.mark.parametrize(
    "values",
    [
        ["A", 10, "B"],
        ["A", 10.5],
        ["A", True],
    ],
)
def test_mixed_object_variants_are_rejected(values):
    df = pd.DataFrame({"mixed": pd.Series(values, dtype="object")})

    with pytest.raises(TypeError, match="Column 'mixed'"):
        vzor.profile(df)


from dataclasses import FrozenInstanceError

import numpy as np
import pandas as pd
import pytest

import vzor


def _assert_profile_schema_invariants(df: pd.DataFrame) -> tuple[object, object]:
    profile = vzor.profile(df)
    schema = vzor.observed_schema(df)

    assert schema.row_count == profile.row_count == len(df)
    assert schema.column_count == len(schema.columns)
    assert profile.column_count == len(profile.columns)
    assert [column.name for column in schema.columns] == list(df.columns)
    assert [column.name for column in profile.columns] == list(df.columns)

    for profile_column, schema_column in zip(profile.columns, schema.columns, strict=True):
        assert schema_column.logical_type == profile_column.logical_type
        assert schema_column.observed_nullable == (profile_column.null_count > 0)
        assert schema_column.observed_unique_count == profile_column.unique_count
        if profile_column.numeric_stats is None:
            assert schema_column.observed_range is None
        else:
            assert schema_column.observed_range is not None
            assert schema_column.observed_range.min == pytest.approx(
                profile_column.numeric_stats.min
            )
            assert schema_column.observed_range.max == pytest.approx(
                profile_column.numeric_stats.max
            )
        if schema_column.observed_values is not None:
            assert isinstance(schema_column.observed_values, tuple)
            assert len(schema_column.observed_values) == schema_column.observed_unique_count
            assert None not in schema_column.observed_values

    return profile, schema


def test_mixed_dataframe_preserves_all_profile_schema_invariants():
    df = pd.DataFrame(
        {
            "id": pd.Series([1, 2, pd.NA, 4], dtype="Int64"),
            "sales": pd.Series([10.0, np.nan, 20.0, np.inf], dtype="float64"),
            "active": pd.Series([False, True, False, pd.NA], dtype="boolean"),
            "region": pd.Series(["South", "North", "", pd.NA], dtype="string"),
            "segment": pd.Series(["Retail", "Wholesale", "Retail", None], dtype="category"),
            "event_at": pd.to_datetime(["2026-01-01", None, "2026-01-01", None]),
            "empty": pd.Series([None, None, None, None], dtype="object"),
        }
    )

    profile, schema = _assert_profile_schema_invariants(df)

    assert schema.column("active").observed_values == (False, True)
    assert schema.column("region").observed_values == ("South", "North", "")
    assert schema.column("segment").observed_values == ("Retail", "Wholesale")
    assert schema.column("sales").observed_range == vzor.ObservedRange(10.0, 20.0)
    assert schema.column("empty").logical_type == "unknown"
    assert profile.column("empty").numeric_stats is None


@pytest.mark.parametrize("logical_type", ["string", "categorical"])
@pytest.mark.parametrize("count", [0, 1, 49, 50, 51])
def test_discrete_cardinality_boundaries(logical_type, count):
    values = [f"value-{index}" for index in range(count)]
    series_dtype = "string" if logical_type == "string" else "category"
    series = pd.Series(values, dtype=series_dtype)
    column = vzor.observed_schema(pd.DataFrame({"value": series})).column("value")

    assert column.observed_unique_count == count
    if count <= 50:
        assert column.observed_values == tuple(values)
    else:
        assert column.observed_values is None


@pytest.mark.parametrize("count", [50, 51])
def test_nulls_do_not_affect_discrete_cardinality_threshold(count):
    values = [f"value-{index}" for index in range(count)] + [pd.NA, pd.NA]
    column = vzor.observed_schema(
        pd.DataFrame({"value": pd.Series(values, dtype="string")})
    ).column("value")

    assert column.observed_nullable
    assert column.observed_unique_count == count
    if count == 50:
        assert column.observed_values == tuple(values[:50])
    else:
        assert column.observed_values is None


@pytest.mark.parametrize(
    ("values", "expected"),
    [
        ([True], (True,)),
        ([False], (False,)),
        ([True, False], (True, False)),
        ([False, True, False], (False, True)),
        ([True, True], (True,)),
        ([pd.NA, pd.NA], ()),
    ],
)
def test_boolean_observed_values_preserve_first_appearance(values, expected):
    column = vzor.observed_schema(
        pd.DataFrame({"active": pd.Series(values, dtype="boolean")})
    ).column("active")

    assert column.logical_type == "boolean"
    assert column.observed_values == expected
    assert column.observed_unique_count == len(expected)
    assert column.observed_nullable == any(value is pd.NA for value in values)


def test_string_object_values_preserve_empty_space_and_unicode_values():
    values = ["", " ", "\u00f1", "\u5ba2\u6237", "", None]
    column = vzor.observed_schema(
        pd.DataFrame({"text": pd.Series(values, dtype="object")})
    ).column("text")

    assert column.logical_type == "string"
    assert column.observed_nullable
    assert column.observed_values == ("", " ", "\u00f1", "\u5ba2\u6237")


def test_categorical_values_use_first_appearance_not_declared_category_order():
    dtype = pd.CategoricalDtype(categories=["North", "South", "West"], ordered=True)
    column = vzor.observed_schema(
        pd.DataFrame(
            {"region": pd.Series(["South", "North", "South", "West", None], dtype=dtype)}
        )
    ).column("region")

    assert column.logical_type == "categorical"
    assert column.observed_nullable
    assert column.observed_values == ("South", "North", "West")


def test_numeric_dtypes_and_special_float_values_remain_consistent():
    df = pd.DataFrame(
        {
            "int32": pd.Series([-1, 0, 2], dtype="int32"),
            "nullable_int": pd.Series([1, pd.NA, 3], dtype="Int64"),
            "uint64": pd.Series([0, 2**40, 2**41], dtype="uint64"),
            "float32": pd.Series([1.5, -2.5, 1.5], dtype="float32"),
            "finite_and_inf": [1.0, np.inf, 2.0],
            "only_inf": [np.inf, -np.inf, np.nan],
        }
    )

    profile, schema = _assert_profile_schema_invariants(df)

    for name in ("int32", "nullable_int", "uint64", "float32", "finite_and_inf", "only_inf"):
        assert schema.column(name).observed_values is None
    assert schema.column("finite_and_inf").observed_range == vzor.ObservedRange(1.0, 2.0)
    assert schema.column("only_inf").observed_range is None
    assert profile.column("only_inf").null_count == 1
    assert profile.column("only_inf").unique_count == 2


def test_datetime_variants_and_unknown_all_null_keep_observation_policy():
    df = pd.DataFrame(
        {
            "naive": pd.to_datetime(["2026-01-01", None, "2026-01-01"]),
            "aware": pd.to_datetime(["2026-01-01T00:00:00Z", None, "2026-01-01T00:00:00Z"], utc=True),
            "all_nat": pd.Series([pd.NaT, pd.NaT, pd.NaT], dtype="datetime64[ns]"),
            "unknown": pd.Series([None, None, None], dtype="object"),
        }
    )

    _, schema = _assert_profile_schema_invariants(df)

    for name in ("naive", "aware", "all_nat", "unknown"):
        assert schema.column(name).observed_range is None
        assert schema.column(name).observed_values is None
    assert schema.column("naive").observed_nullable
    assert schema.column("all_nat").observed_nullable
    assert schema.column("all_nat").observed_unique_count == 0
    assert schema.column("unknown").logical_type == "unknown"


def test_typed_empty_columns_preserve_type_specific_observations():
    df = pd.DataFrame(
        {
            "integer": pd.Series(dtype="int64"),
            "float": pd.Series(dtype="float64"),
            "string": pd.Series(dtype="string"),
            "boolean": pd.Series(dtype="boolean"),
            "categorical": pd.Series(dtype="category"),
        }
    )

    profile, schema = _assert_profile_schema_invariants(df)

    assert profile.row_count == schema.row_count == 0
    assert [column.logical_type for column in schema.columns] == [
        "integer",
        "float",
        "string",
        "boolean",
        "categorical",
    ]
    for column in schema.columns:
        assert not column.observed_nullable
        assert column.observed_unique_count == 0
        assert column.observed_range is None
    assert schema.column("integer").observed_values is None
    assert schema.column("float").observed_values is None
    assert schema.column("string").observed_values == ()
    assert schema.column("boolean").observed_values == ()
    assert schema.column("categorical").observed_values == ()


@pytest.mark.parametrize(
    "index",
    [pd.RangeIndex(1), [100], ["row"], pd.DatetimeIndex(["2026-01-01"])],
)
def test_valid_column_names_and_indexes_do_not_change_schema_columns(index):
    names = ["", "sales total", "\u00e1rea", "\u5ba2\u6237", "a.b", "with-dash"]
    df = pd.DataFrame([range(len(names))], columns=names, index=index)

    profile, schema = _assert_profile_schema_invariants(df)

    assert [column.name for column in profile.columns] == names
    assert [column.name for column in schema.columns] == names
    assert schema.column("\u5ba2\u6237").name == "\u5ba2\u6237"
    assert all(column.name != "index" for column in schema.columns)


def test_profile_and_observed_schema_share_invalid_input_error_types():
    invalid_dataframes = [
        (pd.DataFrame([[1, 2]], columns=["x", "x"]), ValueError),
        (pd.DataFrame([[1, 2]], columns=[1, 2]), TypeError),
        (pd.DataFrame({"mixed": pd.Series(["A", 1], dtype="object")}), TypeError),
        (pd.DataFrame({"mixed": pd.Series(["A", 1.5], dtype="object")}), TypeError),
        (pd.DataFrame({"mixed": pd.Series(["A", True], dtype="object")}), TypeError),
        (pd.DataFrame({"category": pd.Series([1, 2], dtype="category")}), TypeError),
    ]

    for df, exception_type in invalid_dataframes:
        for function in (vzor.profile, vzor.observed_schema):
            with pytest.raises(exception_type):
                function(df)
    for function in (vzor.profile, vzor.observed_schema):
        with pytest.raises(TypeError):
            function([1, 2, 3])


def test_observed_schema_lookup_and_all_models_are_immutable():
    schema = vzor.observed_schema(
        pd.DataFrame({"\u5ba2\u6237": [1, 2], "region": ["North", "South"]})
    )
    customer = schema.column("\u5ba2\u6237")

    assert isinstance(schema.columns, tuple)
    assert isinstance(schema.column("region").observed_values, tuple)
    with pytest.raises(KeyError, match="Column 'missing' not found"):
        schema.column("missing")
    with pytest.raises(FrozenInstanceError):
        schema.row_count = 5
    with pytest.raises(FrozenInstanceError):
        schema.columns = ()
    with pytest.raises(FrozenInstanceError):
        customer.name = "other"
    with pytest.raises(FrozenInstanceError):
        customer.observed_nullable = True
    with pytest.raises(FrozenInstanceError):
        customer.observed_range.min = 0.0


def test_large_low_cardinality_schema_smoke_case():
    size = 10_000
    df = pd.DataFrame(
        {
            "id": range(size),
            "amount": [float(index % 100) for index in range(size)],
            "label": ["A" if index % 2 == 0 else "B" for index in range(size)],
            "segment": pd.Series(
                ["retail" if index % 3 else "wholesale" for index in range(size)],
                dtype="category",
            ),
        }
    )

    profile, schema = _assert_profile_schema_invariants(df)

    assert profile.row_count == schema.row_count == size
    assert schema.column("id").observed_values is None
    assert schema.column("amount").observed_values is None
    assert schema.column("label").observed_values == ("A", "B")
    assert schema.column("segment").observed_values == ("wholesale", "retail")

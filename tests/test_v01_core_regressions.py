from dataclasses import FrozenInstanceError
from math import inf

import numpy as np
import pandas as pd
import pytest

import vzor


PUBLIC_APIS = (vzor.profile, vzor.observed_schema, vzor.suggest_schema)


def test_profile_observed_and_suggested_share_all_core_invariants() -> None:
    df = pd.DataFrame(
        {
            "integer": pd.Series([1, 2, 3], dtype="int64"),
            "float": pd.Series([1.0, np.nan, 2.0], dtype="float64"),
            "boolean": pd.Series([True, False, True], dtype="bool"),
            "string": pd.Series(["área", "東京", ""], dtype="string"),
            "categorical": pd.Series(pd.Categorical(["South", "North", "South"])),
            "datetime": pd.Series(pd.to_datetime(["2026-01-01", "2026-01-02", "2026-01-03"])),
            "unknown": pd.Series([None, None, None], dtype=object),
        }
    )

    profile = vzor.profile(df)
    observed = vzor.observed_schema(df)
    suggested = vzor.suggest_schema(df)

    assert profile.column_count == observed.column_count == suggested.column_count == len(df.columns)
    assert [column.name for column in profile.columns] == list(df.columns)
    assert [column.name for column in observed.columns] == list(df.columns)
    assert [column.name for column in suggested.columns] == list(df.columns)

    for profile_column, observed_column, suggested_column in zip(
        profile.columns, observed.columns, suggested.columns, strict=True
    ):
        assert profile_column.name == observed_column.name == suggested_column.name
        assert (
            profile_column.logical_type
            == observed_column.logical_type
            == suggested_column.logical_type
        )
        assert observed_column.observed_nullable == (profile_column.null_count > 0)
        assert suggested_column.nullable == observed_column.observed_nullable
        assert observed_column.observed_unique_count == profile_column.unique_count
        assert suggested_column.constraints.numeric_range is None
        if profile_column.numeric_stats is None:
            assert observed_column.observed_range is None
        else:
            assert observed_column.observed_range is not None
            assert observed_column.observed_range.min == profile_column.numeric_stats.min
            assert observed_column.observed_range.max == profile_column.numeric_stats.max

    assert observed.column("string").observed_values == ("área", "東京", "")
    assert suggested.column("string").constraints.allowed_values is None
    assert observed.column("categorical").observed_values == ("South", "North")
    assert suggested.column("categorical").constraints.allowed_values == ("South", "North")
    for name in ("integer", "float", "boolean", "datetime", "unknown"):
        assert suggested.column(name).constraints.allowed_values is None


def test_empty_dataframe_is_consistent_across_all_public_apis() -> None:
    df = pd.DataFrame()

    profile = vzor.profile(df)
    observed = vzor.observed_schema(df)
    suggested = vzor.suggest_schema(df)

    assert profile.row_count == observed.row_count == 0
    assert profile.column_count == observed.column_count == suggested.column_count == 0
    assert profile.columns == observed.columns == suggested.columns == ()


def test_unicode_column_names_and_values_are_preserved_exactly() -> None:
    df = pd.DataFrame(
        {
            "área": pd.Series(pd.Categorical(["España", "東京", "客户", ""])),
            "東京": pd.Series(["España", "東京", "客户", ""], dtype="string"),
        }
    )

    observed = vzor.observed_schema(df)
    suggested = vzor.suggest_schema(df)

    assert tuple(column.name for column in observed.columns) == ("área", "東京")
    assert suggested.column("área").constraints.allowed_values == (
        "España",
        "東京",
        "客户",
        "",
    )
    assert observed.column("東京").observed_values == ("España", "東京", "客户", "")
    assert suggested.column("東京").constraints.allowed_values is None


@pytest.mark.parametrize("logical_type", ("string", "categorical"))
@pytest.mark.parametrize("count", (49, 50, 51))
def test_observed_value_threshold_and_suggested_policy(logical_type: str, count: int) -> None:
    values = [f"value-{index}" for index in range(count)]
    series = (
        pd.Series(pd.Categorical(values))
        if logical_type == "categorical"
        else pd.Series(values, dtype="string")
    )
    df = pd.DataFrame({"values": series})

    observed = vzor.observed_schema(df).column("values")
    suggested = vzor.suggest_schema(df).column("values")

    if count <= 50:
        assert observed.observed_values == tuple(values)
        expected_allowed = tuple(values) if logical_type == "categorical" else None
        assert suggested.constraints.allowed_values == expected_allowed
    else:
        assert observed.observed_values is None
        assert suggested.constraints.allowed_values is None


@pytest.mark.parametrize(
    ("name", "series", "expected_values"),
    [
        ("string", pd.Series([pd.NA, pd.NA], dtype="string"), ()),
        ("boolean", pd.Series([pd.NA, pd.NA], dtype="boolean"), ()),
        ("categorical", pd.Series(pd.Categorical([None, None])), ()),
        ("unknown", pd.Series([None, None], dtype=object), None),
    ],
)
def test_all_null_columns_preserve_observed_semantics_without_constraints(
    name: str, series: pd.Series, expected_values: tuple[str | bool, ...] | None
) -> None:
    df = pd.DataFrame({name: series})

    profile = vzor.profile(df).column(name)
    observed = vzor.observed_schema(df).column(name)
    suggested = vzor.suggest_schema(df).column(name)

    assert profile.null_count == len(df)
    assert observed.observed_nullable is True
    assert observed.observed_unique_count == 0
    assert observed.observed_values == expected_values
    assert suggested.nullable is True
    assert suggested.constraints.numeric_range is None
    assert suggested.constraints.allowed_values is None


def test_categorical_threshold_with_nulls_retains_only_non_null_values() -> None:
    values_at_limit = [f"value-{index}" for index in range(50)] + [None, None]
    values_above_limit = [f"value-{index}" for index in range(51)] + [None]

    at_limit_observed = vzor.observed_schema(
        pd.DataFrame({"category": pd.Categorical(values_at_limit)})
    ).column("category")
    at_limit_suggested = vzor.suggest_schema(
        pd.DataFrame({"category": pd.Categorical(values_at_limit)})
    ).column("category")
    above_limit_observed = vzor.observed_schema(
        pd.DataFrame({"category": pd.Categorical(values_above_limit)})
    ).column("category")
    above_limit_suggested = vzor.suggest_schema(
        pd.DataFrame({"category": pd.Categorical(values_above_limit)})
    ).column("category")

    assert at_limit_observed.observed_nullable is True
    assert at_limit_observed.observed_unique_count == 50
    assert at_limit_observed.observed_values == tuple(values_at_limit[:-2])
    assert at_limit_suggested.nullable is True
    assert at_limit_suggested.constraints.allowed_values == tuple(values_at_limit[:-2])
    assert above_limit_observed.observed_values is None
    assert above_limit_suggested.constraints.allowed_values is None


def test_nan_and_infinite_float_semantics_are_consistent() -> None:
    df = pd.DataFrame({"mixed": [np.nan, 1.0, inf, -inf, 2.0]})
    infinite_only = pd.DataFrame({"infinite": [inf, -inf]})

    mixed_profile = vzor.profile(df).column("mixed")
    mixed_observed = vzor.observed_schema(df).column("mixed")
    mixed_suggested = vzor.suggest_schema(df).column("mixed")
    infinite_profile = vzor.profile(infinite_only).column("infinite")
    infinite_observed = vzor.observed_schema(infinite_only).column("infinite")
    infinite_suggested = vzor.suggest_schema(infinite_only).column("infinite")

    assert mixed_profile.null_count == 1
    assert mixed_observed.observed_nullable is True
    assert mixed_profile.numeric_stats is not None
    assert mixed_profile.numeric_stats.min == 1.0
    assert mixed_profile.numeric_stats.max == 2.0
    assert mixed_observed.observed_range is not None
    assert mixed_observed.observed_range.min == 1.0
    assert mixed_observed.observed_range.max == 2.0
    assert mixed_suggested.constraints.numeric_range is None
    assert infinite_profile.null_count == 0
    assert infinite_profile.numeric_stats is None
    assert infinite_observed.observed_range is None
    assert infinite_suggested.constraints.numeric_range is None


def test_uint64_range_is_consistent_across_public_apis() -> None:
    supported = pd.DataFrame({"value": pd.Series([2**63 - 1], dtype="uint64")})
    overflow = pd.DataFrame({"value": pd.Series([2**63], dtype="uint64")})

    for api in PUBLIC_APIS:
        assert api(supported).column("value").logical_type == "integer"
        with pytest.raises(OverflowError, match="outside the supported i64 range"):
            api(overflow)


@pytest.mark.parametrize(
    "values", (["A", 1], ["A", True], ["A", 1.2])
)
def test_mixed_object_values_raise_type_error_in_all_public_apis(values: list[object]) -> None:
    df = pd.DataFrame({"mixed": values})

    for api in PUBLIC_APIS:
        with pytest.raises(TypeError, match="mixed or unsupported object values"):
            api(df)


@pytest.mark.parametrize("bad_input", ([], pd.DataFrame({1: [1]})))
def test_invalid_inputs_fail_consistently_in_all_public_apis(bad_input: object) -> None:
    expected_error = TypeError
    for api in PUBLIC_APIS:
        with pytest.raises(expected_error):
            api(bad_input)


def test_duplicate_names_fail_consistently_in_all_public_apis() -> None:
    df = pd.DataFrame([[1, 2]], columns=["duplicate", "duplicate"])

    for api in PUBLIC_APIS:
        with pytest.raises(ValueError, match="Duplicate column names are not supported"):
            api(df)


@pytest.mark.parametrize(
    "index",
    (
        pd.RangeIndex(3),
        pd.Index([10, 20, 30]),
        pd.Index(["one", "two", "three"]),
        pd.DatetimeIndex(["2026-01-01", "2026-01-02", "2026-01-03"]),
    ),
)
def test_all_public_apis_ignore_dataframe_index(index: pd.Index) -> None:
    df = pd.DataFrame({"z": [1, 2, 3], "a": [1.0, 2.0, 3.0]}, index=index)

    profile = vzor.profile(df)
    observed = vzor.observed_schema(df)
    suggested = vzor.suggest_schema(df)

    assert [column.name for column in profile.columns] == ["z", "a"]
    assert [column.name for column in observed.columns] == ["z", "a"]
    assert [column.name for column in suggested.columns] == ["z", "a"]


def test_typed_empty_columns_work_in_all_public_apis() -> None:
    df = pd.DataFrame(
        {
            "integer": pd.Series(dtype="int64"),
            "float": pd.Series(dtype="float64"),
            "string": pd.Series(dtype="string"),
            "boolean": pd.Series(dtype="boolean"),
            "categorical": pd.Series(pd.Categorical([])),
            "datetime": pd.Series(dtype="datetime64[ns]"),
        }
    )

    profile = vzor.profile(df)
    observed = vzor.observed_schema(df)
    suggested = vzor.suggest_schema(df)

    assert profile.row_count == observed.row_count == 0
    assert profile.column_count == observed.column_count == suggested.column_count == 6
    assert all(column.constraints.numeric_range is None for column in suggested.columns)
    assert all(column.constraints.allowed_values is None for column in suggested.columns)


def test_suggested_models_are_deeply_immutable_and_support_unicode_lookup() -> None:
    numeric_range = vzor.SuggestedNumericRange(min=0.0, max=None)
    constraints = vzor.SuggestedConstraints(
        numeric_range=numeric_range,
        allowed_values=("España", "東京", "客户", ""),
    )
    column = vzor.SuggestedColumnSchema(
        name="área",
        logical_type="categorical",
        nullable=False,
        constraints=constraints,
    )
    schema = vzor.SuggestedDatasetSchema(columns=(column,))

    assert schema.column("área") is column
    assert isinstance(schema.columns, tuple)
    assert isinstance(constraints.allowed_values, tuple)
    for target, attribute, value in (
        (schema, "columns", ()),
        (column, "name", "other"),
        (column, "nullable", True),
        (column, "constraints", constraints),
        (constraints, "numeric_range", None),
        (constraints, "allowed_values", None),
        (numeric_range, "min", None),
        (numeric_range, "max", 10.0),
    ):
        with pytest.raises(FrozenInstanceError):
            setattr(target, attribute, value)


def test_column_names_do_not_trigger_special_constraints() -> None:
    df = pd.DataFrame(
        {
            "id": [1, 2, 3],
            "age": [18, 25, 65],
            "email": ["a@example.com", "b@example.com", "c@example.com"],
            "price": [10.0, 20.0, 30.0],
            "status": ["new", "old", "new"],
            "date": pd.to_datetime(["2026-01-01", "2026-01-02", "2026-01-03"]),
        }
    )

    schema = vzor.suggest_schema(df)

    for column in schema.columns:
        assert column.constraints.numeric_range is None
        assert column.constraints.allowed_values is None
        assert not hasattr(column, "unique")
        assert not hasattr(column, "primary_key")
        assert not hasattr(column, "confidence")
        assert not hasattr(column, "reason")
        assert not hasattr(column, "recommendation")


def test_large_dataframe_smoke_preserves_core_invariants() -> None:
    row_count = 10_000
    regions = ["North", "South", "West"]
    df = pd.DataFrame(
        {
            "integer": list(range(row_count)),
            "float": [float(index) for index in range(row_count)],
            "string": [regions[index % len(regions)] for index in range(row_count)],
            "categorical": pd.Categorical(
                [regions[index % len(regions)] for index in range(row_count)]
            ),
        }
    )

    profile = vzor.profile(df)
    observed = vzor.observed_schema(df)
    suggested = vzor.suggest_schema(df)

    assert profile.column_count == observed.column_count == suggested.column_count == 4
    assert suggested.column("string").constraints.allowed_values is None
    assert suggested.column("categorical").constraints.allowed_values == tuple(regions)
    assert all(column.constraints.numeric_range is None for column in suggested.columns)

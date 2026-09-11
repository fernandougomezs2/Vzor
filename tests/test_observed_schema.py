from dataclasses import FrozenInstanceError

import numpy as np
import pandas as pd
import pytest

import vzor


def test_observed_schema_returns_public_models_and_preserves_structure():
    df = pd.DataFrame(
        {
            "sales": [10.0, 20.0, None],
            "region": ["North", "South", "North"],
            "active": [False, True, False],
        },
        index=[100, 200, 300],
    )

    schema = vzor.observed_schema(df)

    assert isinstance(schema, vzor.ObservedDatasetSchema)
    assert schema.row_count == 3
    assert schema.column_count == 3
    assert isinstance(schema.columns, tuple)
    assert [column.name for column in schema.columns] == ["sales", "region", "active"]
    assert schema.column("region") is schema.columns[1]
    assert all(column.name != "index" for column in schema.columns)

    with pytest.raises(KeyError, match="Column 'missing' not found"):
        schema.column("missing")


def test_observed_schema_models_are_immutable_including_nested_values():
    schema = vzor.observed_schema(
        pd.DataFrame({"value": [1, 2, 3], "label": ["A", "B", "A"]})
    )
    numeric = schema.column("value")
    label = schema.column("label")

    assert isinstance(numeric.observed_range, vzor.ObservedRange)
    assert isinstance(label.observed_values, tuple)

    with pytest.raises(FrozenInstanceError):
        schema.row_count = 10
    with pytest.raises(FrozenInstanceError):
        numeric.observed_nullable = True
    with pytest.raises(FrozenInstanceError):
        numeric.observed_range.min = 0.0


def test_profile_and_observed_schema_are_consistent_for_supported_types():
    df = pd.DataFrame(
        {
            "id": pd.Series([1, 2, 3, 4], dtype="Int64"),
            "sales": pd.Series([10.0, 20.0, None, 10.0], dtype="float64"),
            "region": pd.Series(["North", "South", "North", None], dtype="category"),
            "active": pd.Series([True, False, True, pd.NA], dtype="boolean"),
            "event_at": pd.to_datetime(["2026-01-01", "2026-01-02", None, None]),
            "unknown": pd.Series([None, None, None, None], dtype="object"),
        }
    )

    profile = vzor.profile(df)
    schema = vzor.observed_schema(df)

    assert schema.row_count == profile.row_count
    assert schema.column_count == profile.column_count
    for profile_column, schema_column in zip(profile.columns, schema.columns, strict=True):
        assert schema_column.name == profile_column.name
        assert schema_column.logical_type == profile_column.logical_type
        assert schema_column.observed_nullable == (profile_column.null_count > 0)
        assert schema_column.observed_unique_count == profile_column.unique_count
        if profile_column.numeric_stats is None:
            assert schema_column.observed_range is None
        else:
            assert schema_column.observed_range.min == pytest.approx(
                profile_column.numeric_stats.min
            )
            assert schema_column.observed_range.max == pytest.approx(
                profile_column.numeric_stats.max
            )


def test_boolean_values_keep_first_appearance_and_all_null_is_empty_tuple():
    schema = vzor.observed_schema(
        pd.DataFrame(
            {
                "active": pd.Series([False, True, False], dtype="boolean"),
                "unknown_active": pd.Series([pd.NA, pd.NA, pd.NA], dtype="boolean"),
            }
        )
    )

    active = schema.column("active")
    assert active.logical_type == "boolean"
    assert not active.observed_nullable
    assert active.observed_unique_count == 2
    assert active.observed_values == (False, True)
    assert active.observed_range is None

    all_null = schema.column("unknown_active")
    assert all_null.observed_nullable
    assert all_null.observed_unique_count == 0
    assert all_null.observed_values == ()


def test_low_cardinality_string_values_keep_order_null_and_empty_semantics():
    column = vzor.observed_schema(
        pd.DataFrame(
            {
                "region": pd.Series(
                    ["South", "", "North", "South", pd.NA], dtype="string"
                )
            }
        )
    ).column("region")

    assert column.logical_type == "string"
    assert column.observed_nullable
    assert column.observed_unique_count == 3
    assert column.observed_values == ("South", "", "North")
    assert column.observed_range is None


@pytest.mark.parametrize("count, retained", [(50, True), (51, False)])
def test_string_observed_values_threshold_is_inclusive(count, retained):
    values = [f"value-{index}" for index in range(count)]
    column = vzor.observed_schema(
        pd.DataFrame({"label": pd.Series(values, dtype="string")})
    ).column("label")

    if retained:
        assert column.observed_values == tuple(values)
        assert len(column.observed_values) == column.observed_unique_count == count
    else:
        assert column.observed_values is None
        assert column.observed_unique_count == count


@pytest.mark.parametrize("count, retained", [(2, True), (51, False)])
def test_categorical_observed_values_follow_threshold(count, retained):
    values = [f"category-{index}" for index in range(count)]
    column = vzor.observed_schema(
        pd.DataFrame({"category": pd.Series(values, dtype="category")})
    ).column("category")

    assert column.logical_type == "categorical"
    assert column.observed_range is None
    if retained:
        assert column.observed_values == tuple(values)
        assert len(column.observed_values) == column.observed_unique_count == count
    else:
        assert column.observed_values is None
        assert column.observed_unique_count == count


def test_numeric_datetime_and_unknown_observations_have_expected_shapes():
    schema = vzor.observed_schema(
        pd.DataFrame(
            {
                "integer": [1, 2, 3],
                "float": [10.0, 20.0, None],
                "event_at": pd.to_datetime(["2026-01-01", None, "2026-01-03"]),
                "unknown": pd.Series([None, None, None], dtype="object"),
            }
        )
    )

    integer = schema.column("integer")
    assert integer.logical_type == "integer"
    assert integer.observed_range == vzor.ObservedRange(min=1.0, max=3.0)
    assert integer.observed_values is None

    float_column = schema.column("float")
    assert float_column.logical_type == "float"
    assert float_column.observed_nullable
    assert float_column.observed_range == vzor.ObservedRange(min=10.0, max=20.0)
    assert float_column.observed_values is None

    datetime = schema.column("event_at")
    assert datetime.logical_type == "datetime"
    assert datetime.observed_nullable
    assert datetime.observed_range is None
    assert datetime.observed_values is None

    unknown = schema.column("unknown")
    assert unknown.logical_type == "unknown"
    assert unknown.observed_nullable
    assert unknown.observed_unique_count == 0
    assert unknown.observed_range is None
    assert unknown.observed_values is None


def test_numeric_columns_without_finite_values_have_no_observed_range():
    column = vzor.observed_schema(
        pd.DataFrame({"value": [np.inf, -np.inf, np.nan]})
    ).column("value")

    assert column.logical_type == "float"
    assert column.observed_nullable
    assert column.observed_unique_count == 2
    assert column.observed_range is None
    assert column.observed_values is None


def test_empty_and_typed_empty_dataframes_are_supported():
    empty = vzor.observed_schema(pd.DataFrame())
    typed = vzor.observed_schema(
        pd.DataFrame(
            {
                "id": pd.Series(dtype="int64"),
                "name": pd.Series(dtype="string"),
                "active": pd.Series(dtype="boolean"),
                "category": pd.Series(dtype="category"),
            }
        )
    )

    assert empty.row_count == 0
    assert empty.column_count == 0
    assert empty.columns == ()
    assert typed.row_count == 0
    assert typed.column_count == 4
    assert typed.column("id").observed_range is None
    assert typed.column("id").observed_values is None
    assert typed.column("name").observed_values == ()
    assert typed.column("active").observed_values == ()
    assert typed.column("category").observed_values == ()


def test_observed_schema_reuses_profile_input_validation():
    duplicate_columns = pd.DataFrame([[1, 2]], columns=["value", "value"])
    non_string_columns = pd.DataFrame([[1, 2]], columns=[1, 2])
    mixed_object = pd.DataFrame(
        {"mixed": pd.Series(["A", 10], dtype="object")}
    )
    numeric_category = pd.DataFrame(
        {"category": pd.Series([1, 2, 1], dtype="category")}
    )

    with pytest.raises(ValueError, match="Duplicate column names"):
        vzor.observed_schema(duplicate_columns)
    with pytest.raises(TypeError, match="column names must be strings"):
        vzor.observed_schema(non_string_columns)
    with pytest.raises(TypeError, match="Column 'mixed'"):
        vzor.observed_schema(mixed_object)
    with pytest.raises(TypeError, match="Column 'category'.*non-string category"):
        vzor.observed_schema(numeric_category)
    with pytest.raises(TypeError, match="expects a pandas.DataFrame"):
        vzor.observed_schema([1, 2, 3])


def test_public_exports_and_existing_profile_api_remain_available():
    df = pd.DataFrame({"id": [1, 2, 3]})

    assert callable(vzor.observed_schema)
    assert vzor.ObservedRange is not None
    assert vzor.ObservedColumnSchema is not None
    assert vzor.ObservedDatasetSchema is not None
    assert vzor.profile(df).column("id").logical_type == "integer"
    assert vzor.version() == "0.3.2"

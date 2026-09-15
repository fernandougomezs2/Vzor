from dataclasses import FrozenInstanceError

import pandas as pd
import pytest

import vzor


def test_public_api_returns_immutable_python_models_with_lookup() -> None:
    schema = vzor.suggest_schema(
        pd.DataFrame(
            {
                "age": [18, 25, 65],
                "region": pd.Categorical(["North", "South", "North"]),
            }
        )
    )

    assert isinstance(schema, vzor.SuggestedDatasetSchema)
    assert isinstance(schema.columns, tuple)
    assert schema.column_count == 2
    assert schema.column("age") is schema.columns[0]
    assert schema.column("region") is schema.columns[1]
    with pytest.raises(KeyError, match="Column 'missing' not found"):
        schema.column("missing")
    with pytest.raises(FrozenInstanceError):
        schema.columns = ()
    with pytest.raises(FrozenInstanceError):
        schema.columns[0].nullable = True
    with pytest.raises(FrozenInstanceError):
        schema.columns[0].constraints.allowed_values = ()


def test_numeric_types_do_not_infer_observed_ranges_as_constraints() -> None:
    schema = vzor.suggest_schema(
        pd.DataFrame(
            {
                "age": [18, 25, 65],
                "amount": [10.5, 20.0, 99.9],
            }
        )
    )

    for name, logical_type in (("age", "integer"), ("amount", "float")):
        column = schema.column(name)
        assert column.logical_type == logical_type
        assert column.nullable is False
        assert column.constraints.numeric_range is None
        assert column.constraints.allowed_values is None


def test_string_low_cardinality_and_boolean_do_not_infer_allowed_values() -> None:
    schema = vzor.suggest_schema(
        pd.DataFrame(
            {
                "region_text": ["North", "South", "North"],
                "active": [True, False, True],
            }
        )
    )

    string = schema.column("region_text")
    boolean = schema.column("active")
    assert string.logical_type == "string"
    assert string.constraints.allowed_values is None
    assert boolean.logical_type == "boolean"
    assert boolean.constraints.allowed_values is None
    assert boolean.constraints.numeric_range is None


def test_categorical_values_become_an_ordered_immutable_tuple() -> None:
    schema = vzor.suggest_schema(
        pd.DataFrame(
            {
                "region": pd.Categorical(
                    ["South", "North", "West", "South"]
                )
            }
        )
    )

    column = schema.column("region")
    assert column.logical_type == "categorical"
    assert column.constraints.numeric_range is None
    assert column.constraints.allowed_values == ("South", "North", "West")
    assert isinstance(column.constraints.allowed_values, tuple)


def test_empty_and_high_cardinality_categoricals_have_no_allowed_values() -> None:
    empty = vzor.suggest_schema(
        pd.DataFrame(
            {"category": pd.Series(pd.Categorical([None, None], categories=["A"]))}
        )
    )
    values = [f"value-{index}" for index in range(51)]
    high_cardinality = vzor.suggest_schema(
        pd.DataFrame({"category": pd.Categorical(values)})
    )

    assert empty.column("category").nullable is True
    assert empty.column("category").constraints.allowed_values is None
    assert high_cardinality.column("category").constraints.allowed_values is None


def test_datetime_and_unknown_have_empty_constraints() -> None:
    schema = vzor.suggest_schema(
        pd.DataFrame(
            {
                "created_at": pd.to_datetime(["2026-01-01", "2026-01-02"]),
                "unknown": pd.Series([None, None], dtype=object),
            }
        )
    )

    datetime = schema.column("created_at")
    unknown = schema.column("unknown")
    assert datetime.logical_type == "datetime"
    assert datetime.nullable is False
    assert datetime.constraints.numeric_range is None
    assert datetime.constraints.allowed_values is None
    assert unknown.logical_type == "unknown"
    assert unknown.nullable is True
    assert unknown.constraints.numeric_range is None
    assert unknown.constraints.allowed_values is None


def test_nullable_matches_observed_nullable() -> None:
    df = pd.DataFrame(
        {
            "nullable": pd.Series([1, None], dtype="Int64"),
            "not_nullable": pd.Series([1, 2], dtype="int64"),
        }
    )
    observed = vzor.observed_schema(df)
    suggested = vzor.suggest_schema(df)

    for observed_column, suggested_column in zip(
        observed.columns, suggested.columns, strict=True
    ):
        assert suggested_column.nullable == observed_column.observed_nullable


def test_empty_dataframe_produces_an_empty_schema_without_row_count() -> None:
    schema = vzor.suggest_schema(pd.DataFrame())

    assert schema == vzor.SuggestedDatasetSchema(columns=())
    assert schema.column_count == 0
    assert not hasattr(schema, "row_count")


def test_empty_typed_columns_are_supported() -> None:
    df = pd.DataFrame(
        {
            "integer": pd.Series(dtype="int64"),
            "float": pd.Series(dtype="float64"),
            "string": pd.Series(dtype="string"),
            "boolean": pd.Series(dtype="bool"),
            "categorical": pd.Series(pd.Categorical([])),
            "datetime": pd.Series(dtype="datetime64[ns]"),
        }
    )

    schema = vzor.suggest_schema(df)

    assert [column.logical_type for column in schema.columns] == [
        "integer",
        "float",
        "string",
        "boolean",
        "categorical",
        "datetime",
    ]
    assert all(column.nullable is False for column in schema.columns)
    assert all(column.constraints.numeric_range is None for column in schema.columns)
    assert all(column.constraints.allowed_values is None for column in schema.columns)


@pytest.mark.parametrize(
    ("value", "error", "message"),
    [
        ([], TypeError, "Vzor expects a pandas.DataFrame"),
        (pd.DataFrame({1: [1]}), TypeError, "column names must be strings"),
        (
            pd.DataFrame({"mixed": [1, "text"]}),
            TypeError,
            "mixed or unsupported object values",
        ),
    ],
)
def test_shared_adapter_errors_are_preserved(value, error, message: str) -> None:
    with pytest.raises(error, match=message):
        vzor.suggest_schema(value)


def test_duplicate_names_are_rejected_by_the_shared_adapter() -> None:
    df = pd.DataFrame([[1, 2]], columns=["duplicate", "duplicate"])

    with pytest.raises(ValueError, match="Duplicate column names are not supported"):
        vzor.suggest_schema(df)


def test_column_order_is_preserved_and_dataframe_index_is_ignored() -> None:
    df = pd.DataFrame(
        {"z": [1], "a": [2.0], "m": [True]},
        index=pd.Index(["external-row-id"], name="row_id"),
    )

    schema = vzor.suggest_schema(df)

    assert tuple(column.name for column in schema.columns) == ("z", "a", "m")
    assert schema.column_count == 3


def test_profile_observed_and_suggested_are_consistent_for_mixed_dataframe() -> None:
    df = pd.DataFrame(
        {
            "integer": pd.Series([1, 2, 3], dtype="int64"),
            "float": pd.Series([1.5, None, 3.5], dtype="float64"),
            "boolean": pd.Series([True, False, True], dtype="bool"),
            "string": pd.Series(["A", "B", "A"], dtype="string"),
            "categorical": pd.Categorical(["South", "North", "South"]),
            "datetime": pd.to_datetime(["2026-01-01", "2026-01-02", "2026-01-03"]),
            "unknown": pd.Series([None, None, None], dtype=object),
        }
    )

    profile = vzor.profile(df)
    observed = vzor.observed_schema(df)
    suggested = vzor.suggest_schema(df)

    assert profile.column_count == observed.column_count == suggested.column_count
    for profile_column, observed_column, suggested_column in zip(
        profile.columns, observed.columns, suggested.columns, strict=True
    ):
        assert suggested_column.name == observed_column.name == profile_column.name
        assert (
            suggested_column.logical_type
            == observed_column.logical_type
            == profile_column.logical_type
        )
        assert suggested_column.nullable == observed_column.observed_nullable

    for name in ("integer", "float", "boolean", "string", "datetime", "unknown"):
        constraints = suggested.column(name).constraints
        assert constraints.numeric_range is None
        assert constraints.allowed_values is None
    assert suggested.column("categorical").constraints.allowed_values == (
        "South",
        "North",
    )


def test_public_models_and_existing_api_remain_available() -> None:
    assert callable(vzor.suggest_schema)
    assert vzor.SuggestedNumericRange(min=0.0, max=None).max is None
    assert vzor.version() == "0.4.1"
    df = pd.DataFrame({"x": [1, 2, 3]})
    assert vzor.profile(df).column("x").logical_type == "integer"
    assert vzor.observed_schema(df).column("x").logical_type == "integer"
    assert vzor.suggest_schema(df).column("x").logical_type == "integer"

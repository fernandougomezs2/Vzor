import pandas as pd
import pytest

import vzor


def test_string_unique_count_preserves_null_like_empty_unicode_and_long_values() -> None:
    long_unicode = "東京🙂áéíóúñ" * 64
    values = [
        "",
        "NULL",
        "NaN",
        "None",
        "área",
        "niño",
        "🙂",
        long_unicode,
        None,
        "",
        "área",
        long_unicode,
    ]

    dataframe = pd.DataFrame({"label": pd.Series(values, dtype="string")})
    profile = vzor.profile(dataframe).column("label")
    observed = vzor.observed_schema(dataframe).column("label")

    expected = ("", "NULL", "NaN", "None", "área", "niño", "🙂", long_unicode)
    assert profile.count == len(values)
    assert profile.null_count == 1
    assert profile.unique_count == len(expected)
    assert observed.observed_unique_count == len(expected)
    assert observed.observed_values == expected


@pytest.mark.parametrize("count, retained", [(50, True), (51, False), (100, False)])
def test_string_observed_values_threshold_keeps_exact_cardinality(
    count: int, retained: bool
) -> None:
    values = [f"event-{index:04d}-{'x' * 64}" for index in range(count)]
    dataframe = pd.DataFrame({"event_id": pd.Series(values, dtype="string")})

    profile = vzor.profile(dataframe).column("event_id")
    observed = vzor.observed_schema(dataframe).column("event_id")

    assert profile.unique_count == count
    assert observed.observed_unique_count == count
    expected_values = tuple(values) if retained else None
    assert observed.observed_values == expected_values


def test_categorical_string_order_and_cardinality_are_unchanged() -> None:
    values = ["north", "south", "north", None, "east", "south", "west", "east"]
    dataframe = pd.DataFrame({"region": pd.Series(values, dtype="category")})

    profile = vzor.profile(dataframe).column("region")
    observed = vzor.observed_schema(dataframe).column("region")

    assert profile.null_count == 1
    assert profile.unique_count == 4
    assert observed.observed_values == ("north", "south", "east", "west")

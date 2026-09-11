from dataclasses import FrozenInstanceError

import pandas as pd
import pytest

import vzor


def numeric_stats() -> vzor.NumericStats:
    return vzor.NumericStats(
        min=1.0,
        max=4.0,
        mean=2.5,
        median=2.5,
        p25=1.75,
        p50=2.5,
        p75=3.25,
    )


def column_profile(name: str = "id") -> vzor.ColumnProfile:
    return vzor.ColumnProfile(
        name=name,
        logical_type="integer",
        count=4,
        null_count=0,
        unique_count=4,
        numeric_stats=numeric_stats(),
    )


def observed_column(
    name: str,
    values: tuple[str | bool, ...] | None,
) -> vzor.ObservedColumnSchema:
    return vzor.ObservedColumnSchema(
        name=name,
        logical_type="string",
        observed_nullable=True,
        observed_unique_count=0 if values == () else 2,
        observed_range=None,
        observed_values=values,
    )


def suggested_column(name: str, allowed_values=None) -> vzor.SuggestedColumnSchema:
    return vzor.SuggestedColumnSchema(
        name=name,
        logical_type="categorical",
        nullable=False,
        constraints=vzor.SuggestedConstraints(
            numeric_range=None,
            allowed_values=allowed_values,
        ),
    )


def test_numeric_stats_repr_is_multiline_and_uses_canonical_order() -> None:
    assert repr(numeric_stats()).splitlines() == [
        "NumericStats",
        "  min: 1.0",
        "  max: 4.0",
        "  mean: 2.5",
        "  median: 2.5",
        "  p25: 1.75",
        "  p50: 2.5",
        "  p75: 3.25",
    ]


def test_column_and_dataset_profile_repr_expand_nested_models_and_columns() -> None:
    column_text = repr(column_profile())
    assert column_text.startswith("ColumnProfile\n")
    for field in (
        "name: 'id'",
        "logical_type: 'integer'",
        "count: 4",
        "null_count: 0",
        "unique_count: 4",
        "numeric_stats:",
        "NumericStats",
    ):
        assert field in column_text

    profile = vzor.DatasetProfile(
        row_count=4,
        columns=(column_profile("first"), column_profile("second")),
    )
    profile_text = repr(profile)
    assert profile_text.startswith("DatasetProfile\n  row_count: 4\n  columns:\n")
    assert profile_text.count("- ColumnProfile") == 2
    assert profile_text.index("name: 'first'") < profile_text.index("name: 'second'")
    assert "columns=(" not in profile_text
    assert "ColumnProfile(" not in profile_text


def test_observed_range_column_and_dataset_repr_are_vertical_and_ordered() -> None:
    observed_range = vzor.ObservedRange(min=-1.25, max=10.75)
    assert repr(observed_range).splitlines() == [
        "ObservedRange",
        "  min: -1.25",
        "  max: 10.75",
    ]

    ranged = vzor.ObservedColumnSchema(
        name="amount",
        logical_type="float",
        observed_nullable=False,
        observed_unique_count=2,
        observed_range=observed_range,
        observed_values=None,
    )
    column_text = repr(ranged)
    expected_order = (
        "name:",
        "logical_type:",
        "observed_nullable:",
        "observed_unique_count:",
        "observed_range:",
        "observed_values:",
    )
    positions = [column_text.index(field) for field in expected_order]
    assert positions == sorted(positions)
    assert "ObservedRange\n" in column_text

    schema = vzor.ObservedDatasetSchema(
        row_count=2,
        columns=(ranged, observed_column("label", ("A", "B"))),
    )
    schema_text = repr(schema)
    assert schema_text.startswith("ObservedDatasetSchema\n  row_count: 2")
    assert schema_text.index("name: 'amount'") < schema_text.index("name: 'label'")
    assert schema_text.count("- ObservedColumnSchema") == 2


def test_observed_values_distinguish_none_empty_and_non_empty_tuples() -> None:
    schema = vzor.ObservedDatasetSchema(
        row_count=0,
        columns=(
            observed_column("none", None),
            observed_column("empty", ()),
            observed_column("values", ("México", " Niñez ", True)),
        ),
    )
    text = repr(schema)

    assert "name: 'none'" in text
    assert "observed_values: None" in text
    assert "name: 'empty'" in text
    assert "observed_values: ()" in text
    assert "observed_values:\n" in text
    assert "- 'México'" in text
    assert "- ' Niñez '" in text
    assert "- True" in text


def test_suggested_ranges_constraints_and_schemas_expand_vertically() -> None:
    numeric_range = vzor.SuggestedNumericRange(min=None, max=99.125)
    assert repr(numeric_range).splitlines() == [
        "SuggestedNumericRange",
        "  min: None",
        "  max: 99.125",
    ]

    constraints = vzor.SuggestedConstraints(
        numeric_range=numeric_range,
        allowed_values=("North", " South ", False),
    )
    constraints_text = repr(constraints)
    assert "numeric_range:\n    SuggestedNumericRange" in constraints_text
    assert "allowed_values:\n    - 'North'\n    - ' South '\n    - False" in constraints_text

    schema = vzor.SuggestedDatasetSchema(
        columns=(
            suggested_column("first", ("North", "South")),
            suggested_column("second"),
        )
    )
    schema_text = repr(schema)
    assert schema_text.startswith("SuggestedDatasetSchema\n  columns:")
    assert schema_text.count("- SuggestedColumnSchema") == 2
    assert schema_text.index("name: 'first'") < schema_text.index("name: 'second'")
    assert "allowed_values: None" in schema_text


def test_inspection_summary_lists_every_count_in_fixed_order() -> None:
    summary = vzor.InspectionSummary(
        row_count=4,
        column_count=5,
        nullable_columns=1,
        numeric_columns=2,
        categorical_columns=1,
        string_columns=1,
        boolean_columns=1,
        datetime_columns=0,
        unknown_columns=0,
    )
    assert repr(summary).splitlines() == [
        "InspectionSummary",
        "  row_count: 4",
        "  column_count: 5",
        "  nullable_columns: 1",
        "  numeric_columns: 2",
        "  categorical_columns: 1",
        "  string_columns: 1",
        "  boolean_columns: 1",
        "  datetime_columns: 0",
        "  unknown_columns: 0",
    ]


def test_inspection_report_is_vertical_uses_ux_order_and_prints_cleanly(capsys) -> None:
    dataframe = pd.DataFrame(
        {
            "id": [1, 2, 3],
            "Región": ["México", "Niñez", None],
        }
    )
    report = vzor.inspect(dataframe)
    text = repr(report)

    assert text.startswith("InspectionReport\n  summary:")
    sections = (
        "\n  summary:",
        "\n  profile:",
        "\n  observed_schema:",
        "\n  suggested_schema:",
    )
    positions = [text.index(section) for section in sections]
    assert positions == sorted(positions)
    assert text.count("\n") < 40
    assert "InspectionReport(" not in text
    assert "'Región'" in text
    assert "'México'" not in text
    assert "'Niñez'" not in text
    assert repr(report) == text
    assert str(report) == text

    print(report)
    captured = capsys.readouterr()
    assert captured.out == f"{text}\n"
    assert captured.err == ""


def test_custom_repr_does_not_change_equality_hash_or_frozen_behavior() -> None:
    first = vzor.DatasetProfile(row_count=4, columns=(column_profile(),))
    second = vzor.DatasetProfile(row_count=4, columns=(column_profile(),))

    assert first == second
    assert hash(first) == hash(second)
    with pytest.raises(FrozenInstanceError):
        first.row_count = 5

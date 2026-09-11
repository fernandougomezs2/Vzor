import pandas as pd
import pytest

import vzor


def dataframe_with_columns(count: int) -> pd.DataFrame:
    return pd.DataFrame({f"column_{index}": [index] for index in range(count)})


@pytest.mark.parametrize("count", (0, 4, 5))
def test_repr_keeps_collections_up_to_limit_complete(count: int) -> None:
    profile = vzor.profile(dataframe_with_columns(count))
    text = repr(profile)

    assert "more items" not in text
    assert text.count("- ColumnProfile") == count
    for index in range(count):
        assert f"name: 'column_{index}'" in text


@pytest.mark.parametrize(("count", "remaining"), ((6, 1), (11, 6)))
def test_repr_limits_large_column_collections_to_five(
    count: int,
    remaining: int,
) -> None:
    profile = vzor.profile(dataframe_with_columns(count))
    text = repr(profile)

    assert text.count("- ColumnProfile") == 5
    assert f"... {remaining} more items" in text
    for index in range(5):
        assert f"name: 'column_{index}'" in text
    assert "name: 'column_5'" not in text
    assert len(profile.columns) == count
    assert profile.column(f"column_{count - 1}").name == f"column_{count - 1}"


def test_repr_limits_observed_and_allowed_values_without_data_loss() -> None:
    values = tuple(f"value_{index}" for index in range(8))
    observed = vzor.ObservedColumnSchema(
        name="category",
        logical_type="categorical",
        observed_nullable=False,
        observed_unique_count=len(values),
        observed_range=None,
        observed_values=values,
    )
    suggested = vzor.SuggestedColumnSchema(
        name="category",
        logical_type="categorical",
        nullable=False,
        constraints=vzor.SuggestedConstraints(
            numeric_range=None,
            allowed_values=values,
        ),
    )

    for model in (observed, suggested):
        text = repr(model)
        assert "... 3 more items" in text
        assert "'value_4'" in text
        assert "'value_5'" not in text
    assert observed.observed_values == values
    assert suggested.constraints.allowed_values == values


def test_validation_repr_limits_issues_but_accessors_keep_every_issue() -> None:
    dataframe = dataframe_with_columns(8)
    report = vzor.validate(dataframe, vzor.SuggestedDatasetSchema(columns=()))
    original_summary = report.human_summary
    text = repr(report)

    assert text.count("- code=unexpected_column") == 5
    assert "... 3 more items" in text
    assert "column='column_4'" in text
    assert "column='column_5'" not in text
    assert "result:" not in text
    assert len(report.issues) == len(report.errors) == 8
    assert report.warnings == ()
    assert report.issues[-1].column == "column_7"
    assert report.human_summary == original_summary


def test_comparison_and_drift_repr_are_bounded_and_deterministic() -> None:
    before = dataframe_with_columns(8)
    after = pd.DataFrame(index=before.index)
    comparison = vzor.compare(before, after)
    drift = vzor.schema_drift(before, after)

    comparison_text = repr(comparison)
    drift_text = repr(drift)
    assert comparison_text.count("- name=") == 5
    assert drift_text.count("- code=column_removed") == 5
    assert "... 3 more items" in comparison_text
    assert "... 3 more items" in drift_text
    assert len(comparison.columns) == len(comparison.removed) == 8
    assert len(drift.issues) == len(drift.errors) == 8
    assert comparison.columns[-1].name == "column_7"
    assert drift.issues[-1].column == "column_7"
    assert repr(comparison) == comparison_text
    assert repr(drift) == drift_text
    assert comparison_text.startswith("ComparisonReport\n  summary:")
    assert drift_text.startswith("SchemaDriftReport\n  summary:")
    assert "before:" not in comparison_text
    assert "after:" not in comparison_text


def test_inspection_repr_is_compact_but_keeps_models_complete_and_deterministic() -> None:
    report = vzor.inspect(dataframe_with_columns(11))
    text = repr(report)

    assert len(text.splitlines()) <= 80
    assert text.count("... 6 more items") == 3
    for index in range(5):
        assert f"name='column_{index}'" in text
    assert "name='column_5'" not in text
    assert report.profile.column("column_10").name == "column_10"
    assert report.observed_schema.column("column_10").name == "column_10"
    assert report.suggested_schema.column("column_10").name == "column_10"
    assert repr(report) == text

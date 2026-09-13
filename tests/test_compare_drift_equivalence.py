import numpy as np
import pandas as pd
import pytest

import vzor


def _drift_issues(report: vzor.SchemaDriftReport) -> tuple[tuple[str, str, str], ...]:
    return tuple((issue.code, issue.severity, issue.column) for issue in report.issues)


@pytest.mark.parametrize(
    ("before", "after", "statuses", "drift"),
    [
        (
            pd.DataFrame({"id": [1, 2]}),
            pd.DataFrame({"id": [1, 2]}),
            ("unchanged",),
            (),
        ),
        (
            pd.DataFrame({"id": [1, 2]}),
            pd.DataFrame({"id": [1, 2, 1]}),
            ("unchanged",),
            (),
        ),
        (
            pd.DataFrame({"id": [1]}),
            pd.DataFrame({"id": [1], "added": [2]}),
            ("unchanged", "added"),
            (("column_added", "warning", "added"),),
        ),
        (
            pd.DataFrame({"id": [1], "removed": [2]}),
            pd.DataFrame({"id": [1]}),
            ("unchanged", "removed"),
            (("column_removed", "error", "removed"),),
        ),
        (
            pd.DataFrame({"value": [1, 2]}),
            pd.DataFrame({"value": ["one", "two"]}),
            ("changed",),
            (("logical_type_changed", "error", "value"),),
        ),
        (
            pd.DataFrame({"value": [1.0, 2.0]}),
            pd.DataFrame({"value": [1.0, np.nan]}),
            ("changed",),
            (("nullability_changed", "error", "value"),),
        ),
        (
            pd.DataFrame({"value": [1.0, np.nan]}),
            pd.DataFrame({"value": [1.0, 2.0]}),
            ("changed",),
            (("nullability_changed", "warning", "value"),),
        ),
        (
            pd.DataFrame({"value": [1, 1]}),
            pd.DataFrame({"value": [1, 2]}),
            ("changed",),
            (),
        ),
        (
            pd.DataFrame({"value": [1.0, 2.0]}),
            pd.DataFrame({"value": [1.0, 3.0]}),
            ("changed",),
            (),
        ),
        (
            pd.DataFrame({"region": pd.Categorical(["north", "south"])}),
            pd.DataFrame({"region": pd.Categorical(["north", "west"])}),
            ("changed",),
            (),
        ),
        (
            pd.DataFrame({"first": [1], "second": [2]}),
            pd.DataFrame({"second": [2], "first": [1]}),
            ("unchanged", "unchanged"),
            (),
        ),
        (
            pd.DataFrame({"original": [1]}),
            pd.DataFrame({"renamed": [1]}),
            ("removed", "added"),
            (
                ("column_removed", "error", "original"),
                ("column_added", "warning", "renamed"),
            ),
        ),
    ],
)
def test_compare_and_drift_preserve_factual_and_structural_contracts(
    before: pd.DataFrame,
    after: pd.DataFrame,
    statuses: tuple[str, ...],
    drift: tuple[tuple[str, str, str], ...],
) -> None:
    comparison = vzor.compare(before, after)
    schema_drift = vzor.schema_drift(before, after)

    assert tuple(column.status for column in comparison.columns) == statuses
    assert _drift_issues(schema_drift) == drift


def test_multiple_structural_and_factual_changes_keep_canonical_drift_order() -> None:
    before = pd.DataFrame(
        {"removed": [1], "typed": [1], "nullable": [1.0], "range": [1.0]}
    )
    after = pd.DataFrame(
        {
            "typed": ["one"],
            "nullable": [np.nan],
            "range": [2.0],
            "added": [1],
        }
    )

    comparison = vzor.compare(before, after)
    schema_drift = vzor.schema_drift(before, after)

    assert tuple(column.name for column in comparison.columns) == (
        "removed",
        "typed",
        "nullable",
        "range",
        "added",
    )
    assert _drift_issues(schema_drift) == (
        ("column_removed", "error", "removed"),
        ("logical_type_changed", "error", "typed"),
        ("nullability_changed", "error", "nullable"),
        ("column_added", "warning", "added"),
    )

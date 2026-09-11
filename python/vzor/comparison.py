"""Public comparison reporting backed by the existing Rust comparison engine."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from ._human_summary import format_comparison_summary
from ._pandas_adapter import _normalize_dataframe
from ._repr import _format_compact_comparison_report, _format_dataclass
from ._vzor_core import compare_datasets as _compare_datasets
from .observed_schema import ObservedColumnSchema, _build_observed_column_schema


@dataclass(frozen=True)
class ColumnComparison:
    """One factual before/after column comparison from the Rust core."""

    name: str
    status: str
    before: ObservedColumnSchema | None
    after: ObservedColumnSchema | None
    changes: tuple[str, ...]

    def __repr__(self) -> str:
        return _format_dataclass(self)


@dataclass(frozen=True)
class ComparisonResult:
    """Immutable Python representation of a Rust comparison result."""

    before_row_count: int
    after_row_count: int
    has_changes: bool
    row_count_changed: bool
    added_count: int
    removed_count: int
    changed_count: int
    unchanged_count: int
    column_count_before: int
    column_count_after: int
    columns: tuple[ColumnComparison, ...]

    def __repr__(self) -> str:
        return _format_dataclass(self)


@dataclass(frozen=True)
class ComparisonSummary:
    """Compact, factual summary derived from ``ComparisonResult``."""

    has_changes: bool
    row_count_changed: bool
    before_row_count: int
    after_row_count: int
    added_columns: int
    removed_columns: int
    changed_columns: int
    unchanged_columns: int

    def __repr__(self) -> str:
        return _format_dataclass(self)


@dataclass(frozen=True)
class ComparisonReport:
    """Comparison result and its reporting-oriented summary."""

    result: ComparisonResult
    summary: ComparisonSummary

    @property
    def columns(self) -> tuple[ColumnComparison, ...]:
        """Expose result columns without storing a second copy."""
        return self.result.columns

    @property
    def has_changes(self) -> bool:
        """Return whether any factual comparison change was detected."""
        return self.summary.has_changes

    @property
    def row_count_changed(self) -> bool:
        """Return whether the before and after row counts differ."""
        return self.summary.row_count_changed

    @property
    def before_row_count(self) -> int:
        """Return the row count of the before dataset."""
        return self.summary.before_row_count

    @property
    def after_row_count(self) -> int:
        """Return the row count of the after dataset."""
        return self.summary.after_row_count

    @property
    def added_columns(self) -> int:
        """Return the number of added columns."""
        return self.summary.added_columns

    @property
    def removed_columns(self) -> int:
        """Return the number of removed columns."""
        return self.summary.removed_columns

    @property
    def changed_columns(self) -> int:
        """Return the number of changed columns."""
        return self.summary.changed_columns

    @property
    def unchanged_columns(self) -> int:
        """Return the number of unchanged columns."""
        return self.summary.unchanged_columns

    @property
    def added(self) -> tuple[ColumnComparison, ...]:
        """Return added column comparisons in their original order."""
        return tuple(column for column in self.columns if column.status == "added")

    @property
    def removed(self) -> tuple[ColumnComparison, ...]:
        """Return removed column comparisons in their original order."""
        return tuple(column for column in self.columns if column.status == "removed")

    @property
    def changed(self) -> tuple[ColumnComparison, ...]:
        """Return changed column comparisons in their original order."""
        return tuple(column for column in self.columns if column.status == "changed")

    @property
    def unchanged(self) -> tuple[ColumnComparison, ...]:
        """Return unchanged column comparisons in their original order."""
        return tuple(column for column in self.columns if column.status == "unchanged")

    @property
    def human_summary(self) -> str:
        """Return a compact factual comparison summary."""
        return format_comparison_summary(
            self.summary.has_changes,
            self.summary.row_count_changed,
            self.summary.before_row_count,
            self.summary.after_row_count,
            self.summary.added_columns,
            self.summary.removed_columns,
            self.summary.changed_columns,
        )

    def to_html(self, path: str | Path) -> None:
        """Write the complete report as standalone UTF-8 HTML.

        Parent directories are not created. An existing file is replaced.
        """
        from ._html_report import write_html_report

        write_html_report(self, path)

    def __repr__(self) -> str:
        return _format_compact_comparison_report(self)


def compare(before: pd.DataFrame, after: pd.DataFrame) -> ComparisonReport:
    """Compare two DataFrames using Vzor's factual Rust comparison engine."""
    data = _compare_datasets(
        _normalize_dataframe(before),
        _normalize_dataframe(after),
    )
    result = _build_comparison_result(data)
    return ComparisonReport(
        result=result,
        summary=ComparisonSummary(
            has_changes=result.has_changes,
            row_count_changed=result.row_count_changed,
            before_row_count=result.before_row_count,
            after_row_count=result.after_row_count,
            added_columns=result.added_count,
            removed_columns=result.removed_count,
            changed_columns=result.changed_count,
            unchanged_columns=result.unchanged_count,
        ),
    )


def _build_comparison_result(data: dict[str, Any]) -> ComparisonResult:
    return ComparisonResult(
        before_row_count=data["before_row_count"],
        after_row_count=data["after_row_count"],
        has_changes=data["has_changes"],
        row_count_changed=data["row_count_changed"],
        added_count=data["added_count"],
        removed_count=data["removed_count"],
        changed_count=data["changed_count"],
        unchanged_count=data["unchanged_count"],
        column_count_before=data["column_count_before"],
        column_count_after=data["column_count_after"],
        columns=tuple(
            ColumnComparison(
                name=column["name"],
                status=column["status"],
                before=(
                    _build_observed_column_schema(column["before"])
                    if column["before"] is not None
                    else None
                ),
                after=(
                    _build_observed_column_schema(column["after"])
                    if column["after"] is not None
                    else None
                ),
                changes=tuple(column["changes"]),
            )
            for column in data["columns"]
        ),
    )

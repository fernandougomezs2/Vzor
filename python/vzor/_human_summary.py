"""Pure, deterministic human-readable summary formatters for Vzor reports."""

from __future__ import annotations


def format_validation_summary(
    is_valid: bool,
    error_count: int,
    warning_count: int,
) -> str:
    """Format the compact factual validation summary."""
    outcome = "passed" if is_valid else "failed"
    return (
        f"Validation {outcome}: "
        f"{_counted(error_count, 'error')}, "
        f"{_counted(warning_count, 'warning')}."
    )


def format_comparison_summary(
    has_changes: bool,
    row_count_changed: bool,
    before_row_count: int,
    after_row_count: int,
    added_columns: int,
    removed_columns: int,
    changed_columns: int,
) -> str:
    """Format the compact factual comparison summary."""
    if not has_changes:
        return "Comparison completed: no changes detected."

    if added_columns == removed_columns == changed_columns == 0:
        text = "Comparison completed: no column changes"
    else:
        text = (
            "Comparison completed: "
            f"{added_columns} added, "
            f"{removed_columns} removed, "
            f"{_counted(changed_columns, 'changed column')}"
        )

    if row_count_changed:
        return (
            f"{text}; row count changed from {before_row_count} to {after_row_count}."
        )
    return f"{text}."


def format_schema_drift_summary(
    has_drift: bool,
    error_count: int,
    warning_count: int,
) -> str:
    """Format the compact structural schema-drift summary."""
    if not has_drift:
        return "Schema drift check passed: no structural drift detected."
    return (
        "Schema drift detected: "
        f"{_counted(error_count, 'error')}, "
        f"{_counted(warning_count, 'warning')}."
    )


def format_inspection_summary(
    row_count: int,
    column_count: int,
    nullable_columns: int,
) -> str:
    """Format the compact factual inspection summary."""
    return (
        "Inspection completed: "
        f"{_counted(row_count, 'row')}, "
        f"{_counted(column_count, 'column')}, "
        f"{_counted(nullable_columns, 'nullable column')}."
    )


def _counted(count: int, noun: str) -> str:
    suffix = "" if count == 1 else "s"
    return f"{count} {noun}{suffix}"

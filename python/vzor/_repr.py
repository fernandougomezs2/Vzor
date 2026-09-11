"""Shared plain-text representation helpers for public Vzor models."""

from __future__ import annotations

from dataclasses import fields, is_dataclass
from typing import Any, Callable, Iterable

_INDENT = "  "
_MAX_SEQUENCE_ITEMS = 5


def _format_dataclass(
    value: Any,
    *,
    field_order: tuple[str, ...] | None = None,
    separate_fields: bool = False,
) -> str:
    """Render a dataclass vertically without changing its stored data."""
    return "\n".join(
        _dataclass_lines(
            value,
            level=0,
            field_order=field_order,
            separate_fields=separate_fields,
        )
    )


def _dataclass_lines(
    value: Any,
    *,
    level: int,
    field_order: tuple[str, ...] | None = None,
    separate_fields: bool = False,
) -> list[str]:
    field_names = (
        tuple(field.name for field in fields(value))
        if field_order is None
        else field_order
    )

    lines = [f"{_indent(level)}{type(value).__name__}"]
    for index, name in enumerate(field_names):
        if separate_fields and index > 0:
            lines.append("")
        lines.extend(_field_lines(name, getattr(value, name), level + 1))
    return lines


def _field_lines(name: str, value: Any, level: int) -> list[str]:
    prefix = f"{_indent(level)}{name}:"
    if is_dataclass(value) and not isinstance(value, type):
        return [prefix, *_dataclass_lines(value, level=level + 1)]
    if isinstance(value, tuple):
        if not value:
            return [f"{prefix} ()"]
        return [prefix, *_sequence_lines(value, level + 1)]
    return [f"{prefix} {_format_scalar(value)}"]


def _sequence_lines(values: tuple[Any, ...], level: int) -> list[str]:
    lines: list[str] = []
    for value in values[:_MAX_SEQUENCE_ITEMS]:
        if is_dataclass(value) and not isinstance(value, type):
            nested = _dataclass_lines(value, level=level)
            nested[0] = f"{_indent(level)}- {type(value).__name__}"
            lines.extend(nested)
        else:
            lines.append(f"{_indent(level)}- {_format_scalar(value)}")
    remaining = len(values) - _MAX_SEQUENCE_ITEMS
    if remaining > 0:
        lines.append(f"{_indent(level)}... {remaining} more items")
    return lines


def _format_scalar(value: Any) -> str:
    return repr(value)


def _indent(level: int) -> str:
    return _INDENT * level


def _format_compact_inspection_report(report: Any) -> str:
    """Render high-level inspection data without expanding full column models."""
    lines = ["InspectionReport", *_named_dataclass_lines("summary", report.summary, 1)]
    lines.extend(_inspection_section_lines("profile", report.profile, "profile", 1))
    lines.extend(
        _inspection_section_lines("observed_schema", report.observed_schema, "observed", 1)
    )
    lines.extend(
        _inspection_section_lines("suggested_schema", report.suggested_schema, "suggested", 1)
    )
    return "\n".join(lines)


def _format_compact_validation_report(report: Any) -> str:
    """Render validation metadata plus a bounded issue preview."""
    lines = ["ValidationReport", *_named_dataclass_lines("summary", report.summary, 1)]
    lines.append(f"{_indent(1)}issues:")
    lines.extend(
        _preview_lines(
            report.result.issues,
            2,
            lambda issue: (
                f"code={issue.code}, severity={issue.severity}, "
                f"column={issue.column!r}"
            ),
        )
    )
    return "\n".join(lines)


def _format_compact_comparison_report(report: Any) -> str:
    """Render comparison changes without embedding before/after snapshots."""
    lines = ["ComparisonReport", *_named_dataclass_lines("summary", report.summary, 1)]
    lines.append(f"{_indent(1)}columns:")
    lines.extend(
        _preview_lines(
            report.result.columns,
            2,
            lambda column: (
                f"name={column.name!r}, status={column.status}, "
                f"changes={column.changes!r}"
            ),
        )
    )
    return "\n".join(lines)


def _format_compact_schema_drift_report(report: Any) -> str:
    """Render schema-drift metadata plus a bounded issue preview."""
    lines = ["SchemaDriftReport", *_named_dataclass_lines("summary", report.summary, 1)]
    lines.append(f"{_indent(1)}issues:")
    lines.extend(
        _preview_lines(
            report.result.issues,
            2,
            lambda issue: (
                f"code={issue.code}, severity={issue.severity}, "
                f"column={issue.column!r}"
            ),
        )
    )
    return "\n".join(lines)


def _named_dataclass_lines(name: str, value: Any, level: int) -> list[str]:
    return [
        f"{_indent(level)}{name}:",
        *_dataclass_lines(value, level=level + 1),
    ]


def _inspection_section_lines(name: str, model: Any, kind: str, level: int) -> list[str]:
    lines = [f"{_indent(level)}{name}:"]
    if kind != "suggested":
        lines.append(f"{_indent(level + 1)}row_count: {model.row_count}")
    lines.append(f"{_indent(level + 1)}column_count: {model.column_count}")
    lines.append(f"{_indent(level + 1)}columns:")

    def describe(column: Any) -> str:
        if kind == "profile":
            return f"name={column.name!r}, logical_type={column.logical_type}"
        nullable = (
            column.observed_nullable if kind == "observed" else column.nullable
        )
        return (
            f"name={column.name!r}, logical_type={column.logical_type}, "
            f"nullable={nullable}"
        )

    lines.extend(_preview_lines(model.columns, level + 2, describe))
    return lines


def _preview_lines(
    values: Iterable[Any], level: int, describe: Callable[[Any], str]
) -> list[str]:
    items = tuple(values)
    lines = [f"{_indent(level)}- {describe(value)}" for value in items[:_MAX_SEQUENCE_ITEMS]]
    remaining = len(items) - _MAX_SEQUENCE_ITEMS
    if remaining > 0:
        lines.append(f"{_indent(level)}... {remaining} more items")
    return lines

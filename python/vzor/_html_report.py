"""Deterministic, self-contained HTML rendering for public Vzor reports."""

from __future__ import annotations

from dataclasses import fields
from html import escape
from pathlib import Path
from typing import Any, Iterable


_STYLE = """body {
  margin: 0;
  background: #f4f6f8;
  color: #17202a;
  font-family: system-ui, -apple-system, "Segoe UI", sans-serif;
  line-height: 1.5;
}
main {
  max-width: 1200px;
  margin: 0 auto;
  padding: 32px 24px 48px;
}
h1, h2 { color: #12355b; }
h1 { margin-bottom: 8px; }
section { margin-top: 28px; }
.summary {
  padding: 14px 16px;
  border-left: 4px solid #2878b5;
  background: #ffffff;
}
.table-wrap { overflow-x: auto; }
table {
  width: 100%;
  border-collapse: collapse;
  background: #ffffff;
}
th, td {
  padding: 9px 11px;
  border: 1px solid #d9e0e7;
  text-align: left;
  vertical-align: top;
}
th { background: #eaf0f5; }
tbody tr:nth-child(even) { background: #f8fafb; }
code {
  color: #243447;
  font-family: ui-monospace, "Cascadia Mono", Consolas, monospace;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}
"""


def write_html_report(report: Any, path: str | Path) -> None:
    """Write one complete report as deterministic UTF-8 HTML.

    Parent directories are never created. An existing file is replaced.
    """
    output = Path(path)
    if output.exists() and output.is_dir():
        raise IsADirectoryError(f"HTML report path is not a file: {output}")
    if not output.parent.is_dir():
        raise FileNotFoundError(
            f"HTML report directory not found: {output.parent}"
        )

    document = _render_document(report)
    with output.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(document)


def _render_document(report: Any) -> str:
    from .comparison import ComparisonReport
    from .inspection import InspectionReport
    from .schema_drift import SchemaDriftReport
    from .validation import ValidationReport

    if isinstance(report, InspectionReport):
        title = "Vzor Inspection Report"
        content = _inspection_content(report)
    elif isinstance(report, ValidationReport):
        title = "Vzor Validation Report"
        content = _validation_content(report)
    elif isinstance(report, ComparisonReport):
        title = "Vzor Comparison Report"
        content = _comparison_content(report)
    elif isinstance(report, SchemaDriftReport):
        title = "Vzor Schema Drift Report"
        content = _drift_content(report)
    else:
        raise TypeError(f"Unsupported Vzor report type: {type(report).__name__}")

    return "\n".join(
        (
            "<!doctype html>",
            '<html lang="en">',
            "<head>",
            '  <meta charset="utf-8">',
            '  <meta name="viewport" content="width=device-width, initial-scale=1">',
            f"  <title>{escape(title)}</title>",
            "  <style>",
            _indent_block(_STYLE.rstrip(), 4),
            "  </style>",
            "</head>",
            "<body>",
            "  <main>",
            f"    <h1>{escape(title)}</h1>",
            _indent_block(content, 4),
            "  </main>",
            "</body>",
            "</html>",
            "",
        )
    )


def _inspection_content(report: Any) -> str:
    profile_rows = (
        (
            _code(column.name),
            _code(column.logical_type),
            _code(column.count),
            _code(column.null_count),
            _code(column.unique_count),
            _code(_numeric_stats(column.numeric_stats)),
        )
        for column in report.profile.columns
    )
    observed_rows = (
        (
            _code(column.name),
            _code(column.logical_type),
            _code(column.observed_nullable),
            _code(column.observed_unique_count),
            _code(_numeric_range(column.observed_range)),
            _code(column.observed_values),
        )
        for column in report.observed_schema.columns
    )
    suggested_rows = (
        (
            _code(column.name),
            _code(column.logical_type),
            _code(column.nullable),
            _code(_numeric_range(column.constraints.numeric_range)),
            _code(column.constraints.allowed_values),
        )
        for column in report.suggested_schema.columns
    )
    return "\n".join(
        (
            _summary(report.human_summary),
            _section(
                "Dataset Summary",
                _key_value_table(
                    (field.name, getattr(report.summary, field.name))
                    for field in fields(report.summary)
                ),
            ),
            _section(
                "Column Profiles",
                _table(
                    ("Name", "Logical type", "Count", "Nulls", "Unique", "Numeric stats"),
                    profile_rows,
                ),
            ),
            _section(
                "Observed Schema",
                _table(
                    ("Name", "Logical type", "Nullable", "Unique", "Range", "Observed values"),
                    observed_rows,
                ),
            ),
            _section(
                "Suggested Schema",
                _table(
                    ("Name", "Logical type", "Nullable", "Numeric range", "Allowed values"),
                    suggested_rows,
                ),
            ),
        )
    )


def _validation_content(report: Any) -> str:
    rows = (
        (
            _code(issue.code),
            _code(issue.severity),
            _code(issue.column),
            _code(issue.expected),
            _code(issue.observed),
        )
        for issue in report.issues
    )
    return "\n".join(
        (
            _summary(report.human_summary),
            _section(
                "Validation Summary",
                _key_value_table(
                    (
                        ("is_valid", report.is_valid),
                        ("error_count", report.error_count),
                        ("warning_count", report.warning_count),
                    )
                ),
            ),
            _section(
                "Issues",
                _table(("Code", "Severity", "Column", "Expected", "Observed"), rows),
            ),
        )
    )


def _comparison_content(report: Any) -> str:
    rows = (
        (
            _code(column.name),
            _code(column.status),
            _code(column.changes),
            _code(_observed_snapshot(column.before)),
            _code(_observed_snapshot(column.after)),
        )
        for column in report.columns
    )
    return "\n".join(
        (
            _summary(report.human_summary),
            _section(
                "Comparison Summary",
                _key_value_table(
                    (
                        ("before_row_count", report.before_row_count),
                        ("after_row_count", report.after_row_count),
                        ("row_count_changed", report.row_count_changed),
                        ("added_columns", report.added_columns),
                        ("removed_columns", report.removed_columns),
                        ("changed_columns", report.changed_columns),
                        ("unchanged_columns", report.unchanged_columns),
                    )
                ),
            ),
            _section(
                "Column Comparisons",
                _table(("Name", "Status", "Changes", "Before", "After"), rows),
            ),
        )
    )


def _drift_content(report: Any) -> str:
    rows = (
        (_code(issue.code), _code(issue.severity), _code(issue.column))
        for issue in report.issues
    )
    return "\n".join(
        (
            _summary(report.human_summary),
            _section(
                "Schema Drift Summary",
                _key_value_table(
                    (
                        ("has_drift", report.has_drift),
                        ("error_count", report.error_count),
                        ("warning_count", report.warning_count),
                    )
                ),
            ),
            _section(
                "Drift Issues",
                _table(("Code", "Severity", "Column"), rows),
            ),
        )
    )


def _summary(value: str) -> str:
    return f'<p class="summary">{escape(value)}</p>'


def _section(title: str, content: str) -> str:
    return "\n".join(("<section>", f"  <h2>{escape(title)}</h2>", _indent_block(content, 2), "</section>"))


def _key_value_table(rows: Iterable[tuple[str, Any]]) -> str:
    return _table(
        ("Metric", "Value"),
        ((_code(name), _code(value)) for name, value in rows),
    )


def _table(headers: tuple[str, ...], rows: Iterable[tuple[str, ...]]) -> str:
    materialized = tuple(rows)
    header = "".join(f'<th scope="col">{escape(value)}</th>' for value in headers)
    body = ["<div class=\"table-wrap\">", "  <table>", "    <thead>", f"      <tr>{header}</tr>", "    </thead>", "    <tbody>"]
    if materialized:
        for row in materialized:
            body.append("      <tr>" + "".join(f"<td>{cell}</td>" for cell in row) + "</tr>")
    else:
        body.append(f'      <tr><td colspan="{len(headers)}"><code>None</code></td></tr>')
    body.extend(("    </tbody>", "  </table>", "</div>"))
    return "\n".join(body)


def _code(value: Any) -> str:
    return f"<code>{escape(_display(value), quote=True)}</code>"


def _display(value: Any) -> str:
    if value is None:
        return "None"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, tuple):
        return "[" + ", ".join(_display(item) for item in value) + "]"
    return str(value)


def _numeric_stats(value: Any) -> str:
    if value is None:
        return "None"
    return ", ".join(
        f"{field.name}={_display(getattr(value, field.name))}"
        for field in fields(value)
    )


def _numeric_range(value: Any) -> str:
    if value is None:
        return "None"
    return f"min={_display(value.min)}, max={_display(value.max)}"


def _observed_snapshot(value: Any) -> str:
    if value is None:
        return "None"
    return ", ".join(
        (
            f"logical_type={_display(value.logical_type)}",
            f"nullable={_display(value.observed_nullable)}",
            f"unique_count={_display(value.observed_unique_count)}",
            f"range={_numeric_range(value.observed_range)}",
            f"observed_values={_display(value.observed_values)}",
        )
    )


def _indent_block(value: str, spaces: int) -> str:
    prefix = " " * spaces
    return "\n".join(prefix + line for line in value.splitlines())

"""Public schema-drift reporting backed by the existing Rust drift engine."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from ._human_summary import format_schema_drift_summary
from ._pandas_adapter import _normalize_dataframe
from ._repr import _format_compact_schema_drift_report, _format_dataclass
from ._vzor_core import schema_drift_datasets as _schema_drift_datasets


@dataclass(frozen=True)
class SchemaDriftIssue:
    """One structural schema-drift issue emitted by the Rust core."""

    code: str
    severity: str
    column: str

    def __repr__(self) -> str:
        return _format_dataclass(self)


@dataclass(frozen=True)
class SchemaDriftResult:
    """Immutable Python representation of a Rust schema-drift result."""

    has_drift: bool
    warning_count: int
    error_count: int
    issues: tuple[SchemaDriftIssue, ...]

    def __repr__(self) -> str:
        return _format_dataclass(self)


@dataclass(frozen=True)
class SchemaDriftSummary:
    """Compact summary derived from ``SchemaDriftResult``."""

    has_drift: bool
    error_count: int
    warning_count: int

    @property
    def issue_count(self) -> int:
        """Return the number of issues without duplicating stored state."""
        return self.error_count + self.warning_count

    def __repr__(self) -> str:
        return _format_dataclass(
            self,
            field_order=(
                "has_drift",
                "error_count",
                "warning_count",
                "issue_count",
            ),
        )

@dataclass(frozen=True)
class SchemaDriftReport:
    """Schema-drift result and its reporting-oriented summary."""

    result: SchemaDriftResult
    summary: SchemaDriftSummary

    @property
    def issues(self) -> tuple[SchemaDriftIssue, ...]:
        """Expose result issues without storing a second copy."""
        return self.result.issues

    @property
    def has_drift(self) -> bool:
        """Return whether structural schema drift was detected."""
        return self.summary.has_drift

    @property
    def error_count(self) -> int:
        """Return the schema-drift error count."""
        return self.summary.error_count

    @property
    def warning_count(self) -> int:
        """Return the schema-drift warning count."""
        return self.summary.warning_count

    @property
    def issue_count(self) -> int:
        """Return the total schema-drift issue count."""
        return self.summary.issue_count

    @property
    def errors(self) -> tuple[SchemaDriftIssue, ...]:
        """Return error issues as a tuple in their original order."""
        return tuple(issue for issue in self.issues if issue.severity == "error")

    @property
    def warnings(self) -> tuple[SchemaDriftIssue, ...]:
        """Return warning issues as a tuple in their original order."""
        return tuple(issue for issue in self.issues if issue.severity == "warning")

    @property
    def human_summary(self) -> str:
        """Return a compact structural schema-drift summary."""
        return format_schema_drift_summary(
            self.summary.has_drift,
            self.summary.error_count,
            self.summary.warning_count,
        )

    def to_html(self, path: str | Path) -> None:
        """Write the complete report as standalone UTF-8 HTML.

        Parent directories are not created. An existing file is replaced.
        """
        from ._html_report import write_html_report

        write_html_report(self, path)

    def __repr__(self) -> str:
        return _format_compact_schema_drift_report(self)


def schema_drift(before: pd.DataFrame, after: pd.DataFrame) -> SchemaDriftReport:
    """Detect structural schema drift between two DataFrames."""
    data = _schema_drift_datasets(
        _normalize_dataframe(before),
        _normalize_dataframe(after),
    )
    result = _build_schema_drift_result(data)
    return SchemaDriftReport(
        result=result,
        summary=SchemaDriftSummary(
            has_drift=result.has_drift,
            error_count=result.error_count,
            warning_count=result.warning_count,
        ),
    )


def _build_schema_drift_result(data: dict[str, Any]) -> SchemaDriftResult:
    return SchemaDriftResult(
        has_drift=data["has_drift"],
        warning_count=data["warning_count"],
        error_count=data["error_count"],
        issues=tuple(SchemaDriftIssue(**issue) for issue in data["issues"]),
    )

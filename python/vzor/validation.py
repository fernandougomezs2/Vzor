"""Public validation reporting backed by the existing Rust validation engine."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from ._human_summary import format_validation_summary
from ._pandas_adapter import _normalize_dataframe
from ._repr import _format_compact_validation_report, _format_dataclass
from ._vzor_core import _validate_dataset_schema
from .suggested_schema import SuggestedDatasetSchema


@dataclass(frozen=True)
class ValidationIssue:
    """One factual validation issue emitted by the Rust core."""

    code: str
    severity: str
    column: str | None
    expected: str | bool | None
    observed: str | bool | None

    def __repr__(self) -> str:
        return _format_dataclass(self)


@dataclass(frozen=True)
class ValidationResult:
    """Immutable Python representation of a Rust validation result."""

    is_valid: bool
    error_count: int
    warning_count: int
    issues: tuple[ValidationIssue, ...]

    def __repr__(self) -> str:
        return _format_dataclass(self)


@dataclass(frozen=True)
class ValidationSummary:
    """Compact, deterministic summary derived from ``ValidationResult``."""

    is_valid: bool
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
                "is_valid",
                "error_count",
                "warning_count",
                "issue_count",
            ),
        )

@dataclass(frozen=True)
class ValidationReport:
    """Validation result and its reporting-oriented summary."""

    result: ValidationResult
    summary: ValidationSummary

    @property
    def issues(self) -> tuple[ValidationIssue, ...]:
        """Expose result issues without storing a second copy."""
        return self.result.issues

    @property
    def is_valid(self) -> bool:
        """Return the validation state derived from the structured summary."""
        return self.summary.is_valid

    @property
    def error_count(self) -> int:
        """Return the validation error count from the structured summary."""
        return self.summary.error_count

    @property
    def warning_count(self) -> int:
        """Return the validation warning count from the structured summary."""
        return self.summary.warning_count

    @property
    def issue_count(self) -> int:
        """Return the total issue count derived from the structured summary."""
        return self.summary.issue_count

    @property
    def errors(self) -> tuple[ValidationIssue, ...]:
        """Return error issues as a tuple in their original order."""
        return tuple(issue for issue in self.issues if issue.severity == "error")

    @property
    def warnings(self) -> tuple[ValidationIssue, ...]:
        """Return warning issues as a tuple in their original order."""
        return tuple(issue for issue in self.issues if issue.severity == "warning")

    @property
    def human_summary(self) -> str:
        """Return a compact factual validation summary."""
        return format_validation_summary(
            self.summary.is_valid,
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
        return _format_compact_validation_report(self)


def validate(df: pd.DataFrame, schema: SuggestedDatasetSchema) -> ValidationReport:
    """Validate a DataFrame against an existing suggested schema."""
    if not isinstance(schema, SuggestedDatasetSchema):
        raise TypeError("Vzor expects a SuggestedDatasetSchema")

    data = _validate_dataset_schema(
        _normalize_dataframe(df),
        _schema_columns(schema),
    )
    result = _build_validation_result(data)
    return ValidationReport(
        result=result,
        summary=ValidationSummary(
            is_valid=result.is_valid,
            error_count=result.error_count,
            warning_count=result.warning_count,
        ),
    )


def _schema_columns(schema: SuggestedDatasetSchema) -> list[tuple[Any, ...]]:
    return [
        (
            column.name,
            column.logical_type,
            column.nullable,
            None
            if column.constraints.numeric_range is None
            else (
                column.constraints.numeric_range.min,
                column.constraints.numeric_range.max,
            ),
            None
            if column.constraints.allowed_values is None
            else list(column.constraints.allowed_values),
        )
        for column in schema.columns
    ]


def _build_validation_result(data: dict[str, Any]) -> ValidationResult:
    return ValidationResult(
        is_valid=data["is_valid"],
        error_count=data["error_count"],
        warning_count=data["warning_count"],
        issues=tuple(ValidationIssue(**issue) for issue in data["issues"]),
    )

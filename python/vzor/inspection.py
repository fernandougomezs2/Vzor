"""High-level DataFrame inspection API."""

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from ._human_summary import format_inspection_summary
from ._pandas_adapter import _normalize_dataframe
from ._repr import _format_compact_inspection_report, _format_dataclass
from ._vzor_core import inspect_dataset as _inspect_dataset
from .models import DatasetProfile
from .observed_schema import (
    ObservedDatasetSchema,
    _build_observed_dataset_schema,
)
from .profile import _build_dataset_profile
from .suggested_schema import (
    SuggestedDatasetSchema,
    _build_suggested_dataset_schema,
)


@dataclass(frozen=True)
class InspectionSummary:
    """Compact summary derived from the inspection result."""

    row_count: int
    column_count: int
    nullable_columns: int
    numeric_columns: int
    categorical_columns: int
    string_columns: int
    boolean_columns: int
    datetime_columns: int
    unknown_columns: int

    def __repr__(self) -> str:
        return _format_dataclass(self)


@dataclass(frozen=True)
class InspectionReport:
    """High-level result combining profile, observed schema and suggested schema."""

    profile: DatasetProfile
    observed_schema: ObservedDatasetSchema
    suggested_schema: SuggestedDatasetSchema
    summary: InspectionSummary

    @property
    def row_count(self) -> int:
        """Return the inspected dataset row count."""
        return self.summary.row_count

    @property
    def column_count(self) -> int:
        """Return the inspected dataset column count."""
        return self.summary.column_count

    @property
    def nullable_columns(self) -> int:
        """Return the number of observed nullable columns."""
        return self.summary.nullable_columns

    @property
    def numeric_columns(self) -> int:
        """Return the number of integer and float columns."""
        return self.summary.numeric_columns

    @property
    def categorical_columns(self) -> int:
        """Return the number of categorical columns."""
        return self.summary.categorical_columns

    @property
    def string_columns(self) -> int:
        """Return the number of string columns."""
        return self.summary.string_columns

    @property
    def boolean_columns(self) -> int:
        """Return the number of boolean columns."""
        return self.summary.boolean_columns

    @property
    def datetime_columns(self) -> int:
        """Return the number of datetime columns."""
        return self.summary.datetime_columns

    @property
    def unknown_columns(self) -> int:
        """Return the number of unknown columns."""
        return self.summary.unknown_columns

    @property
    def human_summary(self) -> str:
        """Return a compact factual inspection summary."""
        return format_inspection_summary(
            self.summary.row_count,
            self.summary.column_count,
            self.summary.nullable_columns,
        )

    def to_html(self, path: str | Path) -> None:
        """Write the complete report as standalone UTF-8 HTML.

        Parent directories are not created. An existing file is replaced.
        """
        from ._html_report import write_html_report

        write_html_report(self, path)

    def __repr__(self) -> str:
        return _format_compact_inspection_report(self)


def inspect(df: pd.DataFrame) -> InspectionReport:
    """Inspect a DataFrame using Vzor's profiling and schema layers."""
    data = _inspect_dataset(_normalize_dataframe(df))
    profile = _build_dataset_profile(data["profile"])
    observed = _build_observed_dataset_schema(data["observed_schema"])
    suggested = _build_suggested_dataset_schema(data["suggested_schema"])

    return InspectionReport(
        profile=profile,
        observed_schema=observed,
        suggested_schema=suggested,
        summary=_build_summary(profile, observed),
    )


def _build_summary(
    profile: DatasetProfile,
    observed: ObservedDatasetSchema,
) -> InspectionSummary:
    logical_types = tuple(column.logical_type for column in profile.columns)

    return InspectionSummary(
        row_count=profile.row_count,
        column_count=profile.column_count,
        nullable_columns=sum(column.observed_nullable for column in observed.columns),
        numeric_columns=sum(
            logical_type in {"integer", "float"} for logical_type in logical_types
        ),
        categorical_columns=logical_types.count("categorical"),
        string_columns=logical_types.count("string"),
        boolean_columns=logical_types.count("boolean"),
        datetime_columns=logical_types.count("datetime"),
        unknown_columns=logical_types.count("unknown"),
    )

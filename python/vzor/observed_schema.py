"""Public observed-schema API and immutable result models."""

from dataclasses import dataclass
from typing import Any

import pandas as pd

from ._frame_adapter import normalize_dataframe
from ._repr import _format_dataclass
from ._vzor_core import observed_schema_dataset as _observed_schema_dataset


@dataclass(frozen=True)
class ObservedRange:
    """A numeric range seen in the data, not an accepted-value constraint."""

    min: float
    max: float

    def __repr__(self) -> str:
        return _format_dataclass(self)


@dataclass(frozen=True)
class ObservedColumnSchema:
    """Immutable observations about one column, without business constraints."""

    name: str
    logical_type: str
    observed_nullable: bool
    observed_unique_count: int
    observed_range: ObservedRange | None
    observed_values: tuple[str | bool, ...] | None

    def __repr__(self) -> str:
        return _format_dataclass(self)


@dataclass(frozen=True)
class ObservedDatasetSchema:
    """Immutable observed snapshot of a DataFrame, not a data contract."""

    row_count: int
    columns: tuple[ObservedColumnSchema, ...]

    def __repr__(self) -> str:
        return _format_dataclass(self)

    @property
    def column_count(self) -> int:
        return len(self.columns)

    def column(self, name: str) -> ObservedColumnSchema:
        """Return the observed column with the exact, case-sensitive name.

        Raises:
            KeyError: If no column with that name exists.
        """
        for column in self.columns:
            if column.name == name:
                return column
        raise KeyError(f"Column '{name}' not found")


def observed_schema(df: pd.DataFrame) -> ObservedDatasetSchema:
    """Return observed structure and values without inferring constraints."""
    data = _observed_schema_dataset(normalize_dataframe(df))
    return _build_observed_dataset_schema(data)


def _build_observed_dataset_schema(data: dict[str, Any]) -> ObservedDatasetSchema:
    columns = tuple(_build_observed_column_schema(column) for column in data["columns"])
    return ObservedDatasetSchema(row_count=data["row_count"], columns=columns)


def _build_observed_column_schema(data: dict[str, Any]) -> ObservedColumnSchema:
    range_data = data["observed_range"]
    observed_range = ObservedRange(**range_data) if range_data is not None else None
    values_data = data["observed_values"]
    observed_values = tuple(values_data) if values_data is not None else None

    return ObservedColumnSchema(
        name=data["name"],
        logical_type=data["logical_type"],
        observed_nullable=data["observed_nullable"],
        observed_unique_count=data["observed_unique_count"],
        observed_range=observed_range,
        observed_values=observed_values,
    )

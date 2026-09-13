"""Public suggested-schema API and immutable result models."""

from dataclasses import dataclass
from typing import Any

import pandas as pd

from ._frame_adapter import normalize_dataframe
from ._repr import _format_dataclass
from ._vzor_core import suggest_schema_dataset as _suggest_schema_dataset


@dataclass(frozen=True)
class SuggestedNumericRange:
    """A numeric range proposed as a constraint."""

    min: float | None
    max: float | None

    def __repr__(self) -> str:
        return _format_dataclass(self)


@dataclass(frozen=True)
class SuggestedConstraints:
    """Rules suggested by Vzor, not confirmed contract rules."""

    numeric_range: SuggestedNumericRange | None
    allowed_values: tuple[str | bool, ...] | None

    def __repr__(self) -> str:
        return _format_dataclass(self)


@dataclass(frozen=True)
class SuggestedColumnSchema:
    """Immutable suggested rules for one DataFrame column."""

    name: str
    logical_type: str
    nullable: bool
    constraints: SuggestedConstraints

    def __repr__(self) -> str:
        return _format_dataclass(self)


@dataclass(frozen=True)
class SuggestedDatasetSchema:
    """A schema proposed by Vzor, not an approved data contract."""

    columns: tuple[SuggestedColumnSchema, ...]

    def __repr__(self) -> str:
        return _format_dataclass(self)

    @property
    def column_count(self) -> int:
        return len(self.columns)

    def column(self, name: str) -> SuggestedColumnSchema:
        """Return the suggested column with the exact, case-sensitive name.

        Raises:
            KeyError: If no column with that name exists.
        """
        for column in self.columns:
            if column.name == name:
                return column
        raise KeyError(f"Column '{name}' not found")


def suggest_schema(df: pd.DataFrame) -> SuggestedDatasetSchema:
    """Generate a conservative initial schema proposal from observations."""
    data = _suggest_schema_dataset(normalize_dataframe(df))
    return _build_suggested_dataset_schema(data)


def _build_suggested_dataset_schema(data: dict[str, Any]) -> SuggestedDatasetSchema:
    columns = tuple(_build_suggested_column_schema(column) for column in data["columns"])
    return SuggestedDatasetSchema(columns=columns)


def _build_suggested_column_schema(data: dict[str, Any]) -> SuggestedColumnSchema:
    constraints_data = data["constraints"]
    range_data = constraints_data["numeric_range"]
    numeric_range = SuggestedNumericRange(**range_data) if range_data is not None else None
    values_data = constraints_data["allowed_values"]
    allowed_values = tuple(values_data) if values_data is not None else None
    constraints = SuggestedConstraints(
        numeric_range=numeric_range,
        allowed_values=allowed_values,
    )

    return SuggestedColumnSchema(
        name=data["name"],
        logical_type=data["logical_type"],
        nullable=data["nullable"],
        constraints=constraints,
    )

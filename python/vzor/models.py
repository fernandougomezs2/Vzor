"""Public profiling result models."""

from dataclasses import dataclass

from ._repr import _format_dataclass


@dataclass(frozen=True)
class NumericStats:
    """Basic statistics for the finite values of a numeric column."""

    min: float
    max: float
    mean: float
    median: float
    p25: float
    p50: float
    p75: float

    def __repr__(self) -> str:
        return _format_dataclass(self)


@dataclass(frozen=True)
class ColumnProfile:
    """Immutable profiling result for one DataFrame column."""

    name: str
    logical_type: str
    count: int
    null_count: int
    unique_count: int
    numeric_stats: NumericStats | None

    def __repr__(self) -> str:
        return _format_dataclass(self)


@dataclass(frozen=True)
class DatasetProfile:
    """Immutable profiling snapshot for a DataFrame."""

    row_count: int
    columns: tuple[ColumnProfile, ...]

    def __repr__(self) -> str:
        return _format_dataclass(self)

    @property
    def column_count(self) -> int:
        return len(self.columns)

    def column(self, name: str) -> ColumnProfile:
        """Return the column profile with the exact, case-sensitive name.

        Raises:
            KeyError: If no column with that name exists.
        """
        for column in self.columns:
            if column.name == name:
                return column
        raise KeyError(f"Column '{name}' not found")

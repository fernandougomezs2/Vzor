"""Public Python API for Vzor."""

from ._vzor_core import version
from .comparison import ComparisonReport, ComparisonSummary, compare
from .inspection import InspectionReport, InspectionSummary, inspect
from .models import ColumnProfile, DatasetProfile, NumericStats
from .observed_schema import (
    ObservedColumnSchema,
    ObservedDatasetSchema,
    ObservedRange,
    observed_schema,
)
from .profile import profile
from .suggested_schema import (
    SuggestedColumnSchema,
    SuggestedConstraints,
    SuggestedDatasetSchema,
    SuggestedNumericRange,
    suggest_schema,
)
from .schema_drift import SchemaDriftReport, SchemaDriftSummary, schema_drift
from .validation import ValidationReport, ValidationSummary, validate

__version__ = version()

__all__ = [
    "ColumnProfile",
    "ComparisonReport",
    "ComparisonSummary",
    "DatasetProfile",
    "InspectionReport",
    "InspectionSummary",
    "NumericStats",
    "ObservedColumnSchema",
    "ObservedDatasetSchema",
    "ObservedRange",
    "SchemaDriftReport",
    "SchemaDriftSummary",
    "SuggestedColumnSchema",
    "SuggestedConstraints",
    "SuggestedDatasetSchema",
    "SuggestedNumericRange",
    "ValidationReport",
    "ValidationSummary",
    "compare",
    "inspect",
    "observed_schema",
    "profile",
    "schema_drift",
    "suggest_schema",
    "validate",
    "version",
]

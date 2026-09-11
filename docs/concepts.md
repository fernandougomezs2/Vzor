# Core Concepts

## Profile

`vzor.profile(df)` returns a factual `DatasetProfile`: row count, logical
types, null counts, unique counts, and numeric statistics where applicable.

## Observed Schema

`vzor.observed_schema(df)` describes what Vzor saw in a DataFrame.

**Observed Schema = what was seen.** It is not a contract. Observed values and
ranges are observations, not automatic constraints.

## Suggested Schema

`vzor.suggest_schema(df)` returns a conservative `SuggestedDatasetSchema`.

**Suggested Schema = conservative suggestion.** It is not yet an approved Data
Contract. Nullability follows observation, numeric ranges are not automatically
enforced, and allowed values are only suggested for qualifying categorical
columns.

## Validation

`vzor.validate(df, schema)` answers: **does new data satisfy this suggested
schema?** It returns structured issues in deterministic order. Use
`report.errors`, `report.warning_count`, and `report.human_summary` for common
navigation.

## Comparison

`vzor.compare(before, after)` answers: **what changed?** It is factual, not a
severity assessment. A column can be added, removed, changed, or unchanged.
Reordering is not a change; renames are not inferred.

## Schema Drift

`vzor.schema_drift(before, after)` answers: **did the structural schema
change?** Added/removed columns, logical-type changes, and nullability changes
are structural. Row count, unique count, range, and observed-value changes are
not structural drift.

## Nulls and numeric values

The pandas adapter treats `None`, `pd.NA`, `pd.NaT`, and `np.nan` as null.
Empty strings, textual null-like values, `0`, and `False` remain values.
Numeric statistics use finite values only; infinities are non-null but excluded
from statistics.

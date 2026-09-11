# Vzor Agent Guide

## What Vzor Is

Vzor is a Python library with a Rust data-quality engine. It adds a local,
deterministic data trust layer to Python analytics.

Vzor complements pandas and Polars. It does not replace them.

This file is optional repository documentation. Vzor must not read, import, or
depend on `AGENTS.md`, and it must not affect runtime behavior.

- Profile once. Define the contract. Validate forever.
- Detect before correcting. Observe before restricting. Validate before trusting.
- Core functionality is local-first and should not require network access.

## What Vzor Is Not

Vzor does not clean, transform, or auto-fix datasets. It does not fill nulls,
drop duplicates, coerce types, rename columns, join data, filter rows, compute
business KPIs, generate dashboards, infer causes, or provide recommendations.

Do not suggest `drop_duplicates`, `fillna`, type coercion, or joins as Vzor
responsibilities. Use pandas or Polars for transformations. Vzor has no LLM in
its core.

## Public Python API

```python
import vzor

vzor.__version__                 # Package version metadata
vzor.version()                   # Rust core package version
vzor.profile(df)                 # DatasetProfile
vzor.observed_schema(df)         # ObservedDatasetSchema
vzor.suggest_schema(df)          # SuggestedDatasetSchema
vzor.inspect(df)                 # InspectionReport
vzor.validate(df, schema)        # ValidationReport
vzor.compare(before, after)      # ComparisonReport
vzor.schema_drift(before, after) # SchemaDriftReport
```

Do not invent public methods such as `vzor.clean`, `vzor.fix`, `vzor.load`,
`vzor.read_csv`, `vzor.contract`, or `vzor.analyze_join`.

## Public Report Objects

`InspectionReport`, `ValidationReport`, `ComparisonReport`, and
`SchemaDriftReport` are immutable dataclasses. Each has a structured `summary`,
a deterministic English `human_summary`, and a vertical `repr`. Convenience
properties are derived; do not mutate them or duplicate their state.

Their high-level plain-text `repr` is compact: it shows the full summary and
at most five structural preview items per collection, then `... N more items`.
It never truncates stored data; individual model `repr` values remain detailed.
Each report also exposes `to_html(path)`, which writes the complete deterministic
report as standalone UTF-8 HTML with embedded CSS. It does not create parent
directories and replaces an existing target file.

```python
report = vzor.validate(df, schema)
report.is_valid
report.error_count
report.errors
report.human_summary
report.to_html("validation.html")

comparison = vzor.compare(before, after)
comparison.has_changes
comparison.added
comparison.removed
comparison.changed
comparison.unchanged

drift = vzor.schema_drift(before, after)
drift.has_drift
drift.errors
drift.warnings

inspection = vzor.inspect(df)
inspection.row_count
inspection.column_count
inspection.human_summary
```

`DatasetProfile`, `ObservedDatasetSchema`, and `SuggestedDatasetSchema` expose
`column(name)`. Lookup is exact and case-sensitive, searches stored order, and
raises `KeyError("Column '<name>' not found")` when absent. Do not add fuzzy
matching or silent `None` lookups.

## Data Model Semantics

The pandas adapter treats `None`, `pd.NA`, `pd.NaT`, and `np.nan` as null.
Empty strings, the strings `"NULL"`, `"NaN"`, and `"None"`, `0`, and `False`
are not null automatically.

Numeric statistics use finite values only. `+inf` and `-inf` are non-null but
are excluded from statistics. Python normalization maps pandas `np.nan` to
null before the Rust core; raw-core non-finite handling is therefore distinct.
Percentiles use the current deterministic interpolation policy.

An observed schema is a factual observation, not a contract. Its values and
ranges describe what was seen and are not automatic restrictions. String and
categorical observed values are retained only under the current cardinality
policy.

A suggested schema is conservative and is not an approved data contract:

- `nullable` copies observed nullability.
- Numeric ranges are not automatically enforced.
- `allowed_values` are only suggested for qualifying categorical columns.
- Low-cardinality strings and booleans are not automatically enums.
- Vzor does not infer uniqueness, regexes, primary keys, or confidence scores.

## Validation Semantics

Rust validation variants are `MissingColumn`, `UnexpectedColumn`,
`TypeMismatch`, `NullNotAllowed`, `ValueNotAllowed`, and `RangeViolation`.
Public Python and CLI code strings are snake_case equivalents, for example
`missing_column` and `range_violation`.

Current engine-produced validation issues are errors. The result model also
supports warnings for forward-compatible structured handling.

- Missing columns and type mismatches stop further validation for that column.
- `NullNotAllowed` appears at most once per column.
- `ValueNotAllowed` appears once per distinct invalid value in first-appearance order.
- `RangeViolation` appears at most once per column.
- Nulls are ignored by allowed-value and range checks.
- Numeric ranges apply only when explicitly present in a suggested schema.
- Pandas-normalized nulls do not cause range violations; `+inf` and `-inf`
  follow explicit range constraints.
- Issue order is deterministic.

## Comparison Semantics

Comparison statuses are `Added`, `Removed`, `Changed`, and `Unchanged`.
Factual change variants are `LogicalTypeChanged`, `NullabilityChanged`,
`UniqueCountChanged`, `RangeChanged`, and `ObservedValuesChanged`.

Matching is by exact column name. Reordering alone is not a change. Renames are
not inferred and appear as Removed plus Added. Result order is all BEFORE
columns in original order followed by Added columns in AFTER order. Row-count
changes contribute to `has_changes`. Comparison is factual and has no severity
or compatibility interpretation.

## Schema Drift Semantics

Schema drift interprets only structural comparison changes:

- `ColumnAdded` -> Warning
- `ColumnRemoved` -> Error
- `LogicalTypeChanged` -> Error
- nullability `false -> true` -> Error
- nullability `true -> false` -> Warning

Row count, unique count, numeric range, and observed-value changes are not
schema drift. Renames are not inferred.

## Persistence Contracts

Only `SuggestedDatasetSchema` has persistence. Its JSON envelope uses
`format_version = 1`, preserves order, is pretty UTF-8 JSON, rejects unsupported
versions, and rejects non-finite numeric ranges. There is no current general
persistence format for reports or observed schemas.

## Agent-Ready Output Contracts

CLI structured output is deterministic and has this exact envelope:

```json
{
  "output_version": 1,
  "kind": "...",
  "human_summary": "...",
  "machine_payload": {}
}
```

Current kinds are `profile`, `inspection`, `suggested_schema`, `validation`,
`comparison`, and `schema_drift`. `machine_payload` is the source of truth.
Do not add timestamps, UUIDs, confidence values, quality scores, or
recommendations.

Stable external codes are:

- Validation: `missing_column -> VZOR_VALIDATION_MISSING_COLUMN`,
  `unexpected_column -> VZOR_VALIDATION_UNEXPECTED_COLUMN`,
  `type_mismatch -> VZOR_VALIDATION_TYPE_MISMATCH`,
  `null_not_allowed -> VZOR_VALIDATION_NULL_NOT_ALLOWED`,
  `value_not_allowed -> VZOR_VALIDATION_VALUE_NOT_ALLOWED`, and
  `range_violation -> VZOR_VALIDATION_RANGE_VIOLATION`.
- Comparison: `logical_type_changed -> VZOR_COMPARISON_LOGICAL_TYPE_CHANGED`,
  `nullability_changed -> VZOR_COMPARISON_NULLABILITY_CHANGED`,
  `unique_count_changed -> VZOR_COMPARISON_UNIQUE_COUNT_CHANGED`,
  `range_changed -> VZOR_COMPARISON_RANGE_CHANGED`, and
  `observed_values_changed -> VZOR_COMPARISON_OBSERVED_VALUES_CHANGED`.
- Drift: `column_added -> VZOR_DRIFT_COLUMN_ADDED`,
  `column_removed -> VZOR_DRIFT_COLUMN_REMOVED`,
  `logical_type_changed -> VZOR_DRIFT_LOGICAL_TYPE_CHANGED`, and
  `nullability_changed -> VZOR_DRIFT_NULLABILITY_CHANGED`.

## CLI

```text
vzor version
vzor profile <input>
vzor inspect <input>
vzor suggest-schema <input> [--output schema.json]
vzor validate <input> --schema schema.json
vzor compare <before> <after>
vzor drift <before> <after>
```

The CLI loads CSV through pandas and recognizes XLSX, XLS, and Parquet when the
corresponding optional pandas reader engine is installed. Vzor does not declare
those engines as runtime dependencies. This is CLI orchestration, not a public
ingestion API. There is no `vzor.read_csv()`.

Exit codes are stable:

- `0`: success or acceptable factual result
- `1`: validation failure, comparison changes, or schema drift
- `2`: operational or usage error

Successful structured results go only to stdout. Operational errors go only to
stderr. `vzor version` prints only the package version.

## Architecture

```text
Python: public API, pandas adaptation, immutable reports, CLI, presentation
  -> PyO3 bindings
Rust: profiling, schemas, validation, comparison, schema drift, persistence
```

The package is built with PyO3 and maturin. Do not reimplement Rust-owned core
logic in Python.

## Repository Structure

```text
crates/vzor-core/  Rust core and PyO3 bindings
python/vzor/       Public Python API, CLI, adapters, report presentation
tests/             Python regression and contract tests
examples/          Self-contained public-API usage examples
docs/              Detailed human documentation
README.md          Project introduction and quick start
pyproject.toml     Python package and maturin configuration
Cargo.toml         Rust workspace
```

## Development Rules

- Inspect implementation and tests before assuming an API exists.
- Do not expose private bindings through `vzor.__init__`.
- Do not add public aliases, magical accessors, or hidden behavior without a
  clear, tested need.
- Prefer frozen dataclasses, tuples, and properties derived from existing data.
- Preserve deterministic ordering and established vertical `repr` semantics.
- Keep `inspect(df)` parameterless.
- Do not turn observed data into restrictions automatically.
- Do not add cleaning, transformation, LLM, or network responsibilities.
- Do not change output/persistence versions or package version casually.

Before adding a dependency, demonstrate a real need, prefer stdlib/current
code, verify its license, prefer MIT or MIT/Apache-2.0, preserve user-level
installation, and keep the core usable offline. Do not claim a license for an
existing dependency without checking it.

## Testing Rules

Run:

```text
cargo fmt --check
cargo check --locked
cargo test --locked
pytest -q
```

At the start of v0.3.5, the baseline was 131 Rust tests and 250 Python tests.
These counts are not permanent. Do not reduce behavioral coverage; add
regression tests for every public bug fix or behavior change.

## Stability Rules

Treat these as stable unless an explicit, versioned change is requested:

- Public API names and established `repr` behavior
- Deterministic ordering
- CLI exit codes and stdout/stderr separation
- `output_version = 1`
- `format_version = 1`
- Stable external agent-output codes

## Future Roadmap Boundaries

The roadmap is directional, not current API. Do not implement future features
unless explicitly requested:

- v0.3: maturity, reporting, and UX
- v0.4: hardening, performance, scalability, and backends
- v0.5: Excel / Power BI exports
- v0.6: explicit Data Contracts
- v0.7: Join Risk Analysis

## Instructions for AI Agents

When working on Vzor:

1. Read this file before changing the project.
2. Inspect the current implementation before assuming an API exists.
3. Do not invent public methods.
4. Prefer existing abstractions over parallel ones.
5. Keep behavior deterministic.
6. Preserve existing contracts unless explicitly asked to change them.
7. Add tests for every public behavior change.
8. Do not add future-roadmap features unless explicitly requested.
9. Do not add data-cleaning or transformation responsibilities.
10. Report exactly what changed and what was intentionally left unchanged.

# Vzor

Vzor is a Python library with a Rust data-quality engine. It adds a data trust
layer to Python analytics.

Vzor complements pandas and Polars. It does not replace them.

> Profile once. Define the contract. Validate forever.

> Detect before correcting. Observe before restricting. Validate before trusting.

Vzor 0.4.2 is a maintenance-only release. It preserves the Rust core, Python
API, CLI, supported backends, and output contracts while adopting the standard
MIT License and correcting the package metadata published on PyPI.

## Why Vzor

Data work often needs a factual boundary between loading data and trusting it.
Vzor profiles datasets, observes their structure, suggests conservative schemas,
validates later inputs, compares snapshots, and detects structural schema drift.
Its results are deterministic and local-first.

## Supported environments

Vzor supports CPython 3.12 and 3.13 on 64-bit Windows and Linux. The default
backend is `pandas>=2.2.3,<4`; Polars is optional through
`pip install "vzor[polars]"` with `polars>=1.0,<2`.

The repository CI exercises the minimum and current supported pandas and
Polars releases for both Python versions. The release workflow builds and
smoke-tests four CPython-version-specific wheels for Windows and Linux x86-64,
validates their metadata, and publishes only those wheels through PyPI Trusted
Publishing. It does not build or publish a source distribution. Python 3.14 is
intentionally outside the tested support matrix.

## DataFrame backends

Vzor supports pandas by default and an optional direct Polars backend. Install
it with `pip install "vzor[polars]"`; no pandas conversion is required for a
`polars.DataFrame`. LazyFrame is intentionally unsupported.

The adapters preserve the same factual models across supported backends. Their
current numeric fast paths still build owned Rust values; they do not claim
zero-copy buffer transport.

Performance claims are meaningful only with a documented backend, dataset
profile, operation, hardware and memory context. Large-data stress evidence is
not a universal row-count support guarantee.

## What Vzor Does

- Profiles pandas DataFrames.
- Produces observed schemas and conservative suggested schemas.
- Validates DataFrames against a suggested schema.
- Compares factual before/after dataset observations.
- Detects structural schema drift.
- Provides a JSON agent-ready CLI for local files.

## What Vzor Does Not Do

Vzor does not clean, transform, or auto-fix data. It does not fill nulls, drop
duplicates, coerce types, rename columns, join datasets, calculate business
KPIs, generate dashboards, infer causes, or make recommendations. Use pandas,
Polars, or SQL for those responsibilities.

## Installation

Install Vzor from PyPI with pandas support:

```console
python -m pip install vzor
```

Install the optional Polars backend with:

```console
python -m pip install "vzor[polars]"
```

The published distributions are version-specific wheels for CPython 3.12 and
3.13 on Windows x86-64 and Linux x86-64. Source-development instructions and
the validated platform matrix are documented in the
[compatibility and wheel notes](https://github.com/fernandougomezs2/Vzor/blob/main/docs/v0.4.6-compatibility-ci-wheels.md).

## Quick Start

```python
import pandas as pd
import vzor

df = pd.DataFrame(
    {
        "customer_id": [1, 2, 3],
        "region": ["North", "South", "North"],
        "sales": [120.0, 95.5, 210.0],
    }
)

report = vzor.inspect(df)
print(report.human_summary)
print(report)

schema = vzor.suggest_schema(df)
validation = vzor.validate(df, schema)
print(validation.human_summary)
```

## Report Views

Every public report offers three complementary views:

```python
print(report)                         # compact summary with five-item previews
print(report.human_summary)           # short deterministic summary
report.to_html("vzor report.html")    # complete standalone report
```

`to_html` is available on inspection, validation, comparison, and schema-drift
reports. It writes deterministic UTF-8 HTML with embedded CSS and no network
resources. The parent directory must already exist; an existing file is
replaced. HTML always includes the complete report even when `repr` is bounded.

## Validation

Suggested schemas are conservative starting points, not approved Data Contracts.
For example, numeric ranges are not inferred as enforced constraints. A
categorical value that was not present in a qualifying baseline and an
unexpected column both produce factual validation issues:

```python
baseline = pd.DataFrame(
    {
        "customer_id": [1, 2, 3],
        "region": pd.Categorical(["North", "South", "North"]),
    }
)
schema = vzor.suggest_schema(baseline)

new_data = pd.DataFrame(
    {
        "customer_id": ["one", "two"],
        "region": pd.Categorical(["North", "West"]),
        "source_system": ["finance", "finance"],
    }
)
report = vzor.validate(new_data, schema)

print(report.human_summary)
print(report.is_valid, report.error_count)
for issue in report.errors:
    print(issue)
```

## Comparison

Comparison reports factual differences; it does not assign severity or infer
renames. Reordering alone is not a change, and a rename appears as removed plus
added.

```python
comparison = vzor.compare(before, after)
print(comparison.human_summary)

for column in comparison.added:
    print("added:", column.name)
for column in comparison.removed:
    print("removed:", column.name)
for column in comparison.changed:
    print("changed:", column.name, column.changes)
```

## Schema Drift

Schema drift is a structural interpretation of comparison. Added columns are
warnings; removed columns and logical-type changes are errors. Row count,
unique count, ranges, and observed values are not structural drift.

```python
drift = vzor.schema_drift(before, after)
print(drift.human_summary)
for issue in drift.errors:
    print(issue)
```

## CLI

The CLI emits deterministic agent-ready JSON by default. `machine_payload` is
the structured source of truth.

```text
vzor inspect data.csv
vzor suggest-schema data.csv --output schema.json
vzor validate new_data.csv --schema schema.json
vzor compare before.csv after.csv
vzor drift before.csv after.csv
```

Exit codes are `0` for success or an acceptable factual result, `1` for a
validation failure/comparison change/schema drift, and `2` for operational or
usage errors.

## Professional Workflow

```text
SQL / CSV / Excel / APIs
        ↓
pandas / Polars
        ↓
Vzor
        ↓
trust / validation / drift
        ↓
analysis / transformations
        ↓
Excel / Power BI / reporting
```

SQL extracts and filters source data. pandas or Polars clean and transform it.
Vzor validates trust and structure. pandas or SQL calculate KPIs. Excel and
Power BI present results.

## Design Principles

- Rust owns factual profiling, validation, comparison, drift, and persistence.
- Python owns the public API, pandas integration, CLI, and presentation.
- Observations are not automatic restrictions.
- Results are immutable and deterministic.
- The core remains local-first and does not require network access.

## Documentation

- [Getting Started](https://github.com/fernandougomezs2/Vzor/blob/main/docs/getting-started.md)
- [Core Concepts](https://github.com/fernandougomezs2/Vzor/blob/main/docs/concepts.md)
- [Professional Workflows](https://github.com/fernandougomezs2/Vzor/blob/main/docs/professional-workflows.md)
- [Licensing](https://github.com/fernandougomezs2/Vzor/blob/main/docs/licensing.md)
- [Publishing Guide](https://github.com/fernandougomezs2/Vzor/blob/main/docs/publishing.md)
- [Release Checklist](https://github.com/fernandougomezs2/Vzor/blob/main/docs/release-checklist.md)
- [Agent Guide](https://github.com/fernandougomezs2/Vzor/blob/main/AGENTS.md)
- [Changelog](https://github.com/fernandougomezs2/Vzor/blob/main/CHANGELOG.md)

## AI / Agent Usage

AI coding assistants can read
[AGENTS.md](https://github.com/fernandougomezs2/Vzor/blob/main/AGENTS.md) for a
concise description of Vzor's public API, architecture, contracts, and
development rules.

## Roadmap

The roadmap is directional, not current functionality:

- v0.3 — maturity, reporting, and UX — complete
- v0.4 — hardening, performance, scalability, and backends — complete
- v0.5 — Excel / Power BI exports — planned
- v0.6 — explicit Data Contracts — planned
- v0.7 — Join Risk Analysis — planned

These entries are future direction, not claims that the planned features are
available today.

## License

Vzor v0.4.2 and future releases are available under the standard
[MIT License](https://github.com/fernandougomezs2/Vzor/blob/main/LICENSE).
Previously published artifacts retain the license text distributed with those
artifacts; the v0.4.2 change does not rewrite historical tags or releases. See
the [licensing details](https://github.com/fernandougomezs2/Vzor/blob/main/docs/licensing.md)
and [third-party notices](https://github.com/fernandougomezs2/Vzor/blob/main/THIRD_PARTY_NOTICES.md).

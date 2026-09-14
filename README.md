# Vzor

Vzor is a Python library with a Rust data-quality engine. It adds a data trust
layer to Python analytics.

Vzor complements pandas and Polars. It does not replace them.

> Profile once. Define the contract. Validate forever.

> Detect before correcting. Observe before restricting. Validate before trusting.

Vzor 0.4.0 is a release candidate for the existing API: it preserves the
compact structural plain-text reports, complete standalone HTML, analytics,
and CLI contracts while adding reproducible core property coverage.

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
Polars releases for both Python versions. It builds CPython-version-specific
wheels for Windows and Linux x86-64, smoke-tests fresh installs, and publishes
the wheels only as workflow artifacts. This repository does not publish to
PyPI from CI. The Windows/CPython 3.12 evidence is local; Python 3.13 and Linux
are validated by the same remote CI lanes. Python 3.14 is intentionally outside
the tested support matrix.

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

Vzor is documented here as a local/source installation; this repository does
not claim a published PyPI package.

The local development baseline is Windows with Python 3.12 and a Rust toolchain
available to build the PyO3 extension. See
[the compatibility and wheel notes](docs/v0.4.6-compatibility-ci-wheels.md)
and the [v0.4.0 release checklist](docs/release-checklist-v0.4.0.md) for the
complete platform matrix and validation status.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install maturin
python -m maturin develop --release
```

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

- [Getting Started](docs/getting-started.md)
- [Core Concepts](docs/concepts.md)
- [Professional Workflows](docs/professional-workflows.md)
- [Agent Guide](AGENTS.md)
- [Changelog](CHANGELOG.md)
- [v0.4.0 Release Checklist](docs/release-checklist-v0.4.0.md)
- [v0.4.0 Release Notes](docs/release-notes-v0.4.0.md)

## AI / Agent Usage

AI coding assistants can read [AGENTS.md](AGENTS.md) for a concise description
of Vzor's public API, architecture, contracts, and development rules.

## Roadmap

The roadmap is directional, not current functionality:

- v0.3 — maturity, reporting, and UX — complete
- v0.4 — hardening, performance, scalability, and backends
- v0.5 — Excel / Power BI exports
- v0.6 — explicit Data Contracts
- v0.7 — Join Risk Analysis

## License

Vzor is available under the [MIT License](LICENSE). The Python and Rust package
metadata declare the same license.

# Getting Started

## Local installation

Vzor is currently documented as a source build. The verified environment is
Windows with Python 3.12 and a Rust toolchain.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install maturin
python -m maturin develop --release
```

## First DataFrame

```python
import pandas as pd
import vzor

df = pd.DataFrame(
    {
        "id": [1, 2, 3],
        "region": ["North", "South", "North"],
        "sales": [120.0, 95.5, 210.0],
    }
)

inspection = vzor.inspect(df)
print(inspection.human_summary)

schema = vzor.suggest_schema(df)
validation = vzor.validate(df, schema)
print(validation.human_summary)
```

`inspect` returns an immutable `InspectionReport`. Its `summary` is structured,
while `human_summary` is a short deterministic text.

## Compact text and complete HTML

```python
print(inspection)
inspection.to_html("inspection report.html")
```

High-level plain-text `repr` output shows the complete summary and at most five
structural preview items per collection, followed by `... N more items` when
needed. Individual model representations remain detailed. This affects
presentation only; all columns and issues remain available on the report and
through accessors such as `column(name)`. `to_html` writes the complete report
as deterministic, self-contained UTF-8 HTML with embedded CSS and no network
resources. The parent directory must exist, and an existing file is replaced.

## Compare and detect drift

```python
after = pd.DataFrame(
    {
        "id": [1, 2, 3, 4],
        "region": ["North", "South", "North", "West"],
        "active": [True, True, False, True],
    }
)

comparison = vzor.compare(df, after)
print(comparison.human_summary)

drift = vzor.schema_drift(df, after)
print(drift.human_summary)
```

`compare` reports factual changes. `schema_drift` reports only structural
changes; row-count changes alone are not drift.

## Basic CLI

```text
vzor inspect data.csv
vzor suggest-schema data.csv --output schema.json
vzor validate new_data.csv --schema schema.json
vzor compare before.csv after.csv
vzor drift before.csv after.csv
```

The CLI accepts CSV directly through pandas. XLSX, XLS, and Parquet are also
recognized, but require the corresponding optional pandas reader engine to be
installed by the user. Vzor does not add those engines as runtime dependencies.
The CLI emits agent-ready JSON by default. Exit codes are `0` for
success/acceptable results, `1` for factual negative results, and `2` for
operational or usage errors.

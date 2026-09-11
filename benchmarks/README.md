# Vzor benchmark baseline and memory inventory

This directory is a local-only, manual benchmark harness for the existing
Vzor 0.3.2 pandas backend. It is evidence-gathering infrastructure, not a
performance feature: it neither changes Vzor's runtime nor loads datasets for
the public library.

Large files live outside the repository. `benchmarks/datasets/`,
`benchmarks/results/`, and `*.parquet` are ignored by Git; `.gitkeep` only
preserves the empty results directory.

## Generate deterministic datasets

```powershell
python benchmarks/generate_stress_data.py `
  --rows 1000000 --columns 30 --seed 42 --profile baseline `
  --output-dir 'D:\Pruebas Vzor\datos estrés' --format parquet
```

The required options are `--rows`, `--columns`, `--seed`, `--profile`, and
`--output-dir`. `--format` is optional and defaults to `parquet`; `csv` is
available for small infrastructure checks. Use a pandas Parquet engine such as
PyArrow installed in the benchmark environment. It is intentionally not a
Vzor runtime dependency. The same seed, profile, rows, and columns produce the
same logical pandas dataset on the same supported NumPy/pandas environment.

Profiles are deliberately mixed and not tuned for Vzor:

| Profile | Dataset shape |
| --- | --- |
| `baseline` | Analytical mix: IDs, dates, categorical region/product, integer quantity, floats, nullable strings, and Boolean flags. |
| `numeric` | Predominantly `int64`, `float64`, and nullable Boolean columns. |
| `many_nulls` | Numeric, string, Boolean, and datetime columns at reproducible 0%, 10%, 50%, 90%, and 100% null rates. |
| `high_cardinality` | Near-row-count IDs, including almost entirely unique string identifiers. |
| `heavy_strings` | Repeated and nearly unique ASCII/Unicode strings of 16, 64, and 256 characters, with accents, multibyte text, nulls, and empty strings. |
| `categorical` | pandas `Categorical` columns with category universes of 5, 50, 1,000, and 10,000. |
| `wide` | A repeated mixed template suitable for 50, 100, or 250 columns. |

Targets are 100,000, 1,000,000, and 5,000,000 rows. The 5M / 30–50 column
baseline dataset is a stress-test target, for example
`D:\VzorBenchmarks\datasets\vzor_5000000_baseline_40c_seed42.parquet`; it is
never generated or run by pytest and does not imply a universal support claim.

## Run an operation benchmark

```powershell
python benchmarks/run_benchmark.py `
  --input 'D:\Pruebas Vzor\datos estrés\vzor_1000000_baseline_30c_seed42.parquet' `
  --operation inspect --repeats 3 --profile baseline --seed 42
```

Supported operations are `profile`, `inspect`, `validate`, `compare`, and
`schema_drift`. The clock surrounds only the named public Vzor call:

- Parquet/CSV loading is measured independently as `input_load_seconds` and,
  for Parquet, `parquet_load_seconds`.
- `validate` creates `schema = vzor.suggest_schema(df)` before the timer.
- `compare` and `schema_drift` use the same deterministic variant: one fewer
  row, an added column, a removed column, a string type conversion, and an
  introduced null. The pair requires at least three input columns.
- HTML generation and printing are outside the timed operation.

By default, every repeat starts a fresh Python child process (`--isolation
process`). This is a cold-process measurement: imports, the dataset load, and
the operation begin with no prior DataFrames in that child. Only the Vzor call
is timed. It avoids reuse of previous DataFrames and substantially reduces
allocator/cache contamination. `--isolation none` is available for debugging,
but its cumulative peak-memory value is less comparable.

The runner writes one pretty JSON file by default under `benchmarks/results/`;
use `--output path.json` to select another location. It stores every repeat and
min/median/max operation times, not merely the best time. `rows_per_second` is
`rows / elapsed_seconds` and is contextual rather than a standalone quality
metric.

## Memory and result interpretation

On Windows the exact memory metric is the operating system's cumulative
**Peak Working Set** for the isolated child process (`peak_working_set_bytes`,
also emitted in MiB). It includes the process's dataset load, Python objects,
Vzor call, allocator overhead, and any temporary allocations; it is not
labelled “peak RAM” and it does not isolate only the Rust operation. The runner
also records working set before and after the timed call where Windows exposes
it. `validate` preparation is excluded from elapsed time but can still
contribute to this cumulative child-process peak. On POSIX, the fallback is
cumulative `ru_maxrss` normalized to bytes and
labelled `peak_rss_bytes`.

Every result captures timestamp (benchmark artifact only), Vzor/Python/pandas
versions, backend, operating system and version, architecture, CPU model where
available, logical CPU count, total RAM, operation, profile, seed, dataset
path/name, rows/columns, compressed file size, and the dataset drive's total
and free capacity. Disk model is intentionally not guessed because it is not
reliably portable; record it beside results when it matters.

The JSON is benchmark-specific and is unrelated to Vzor's agent-ready output.
It contains fields such as `elapsed_seconds`, `rows_per_second`,
`peak_memory_bytes`, `parquet_load_seconds`, `dataset_file_size_bytes`, and a
`runs` array. Compare results only when the profile, generated parameters,
hardware, versions, and isolation mode are stated.

All scripts run offline: no telemetry, uploads, credentials, network calls, or
external services are used.

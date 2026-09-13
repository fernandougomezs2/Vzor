"""Run isolated Vzor operation benchmarks and persist JSON evidence."""

from __future__ import annotations

import argparse
import json
import statistics
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from benchmarks.system_info import process_memory, system_metadata


OPERATIONS = ("profile", "inspect", "validate", "compare", "schema_drift")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Measure one Vzor operation without including load time.")
    parser.add_argument("--input", type=Path, required=True, help="CSV or Parquet dataset path.")
    parser.add_argument("--operation", choices=OPERATIONS, required=True, help="Vzor operation to measure.")
    parser.add_argument("--backend", choices=("pandas", "polars"), default="pandas", help="DataFrame backend used to load the input.")
    parser.add_argument("--repeats", type=int, default=3, help="Independent runs (default: 3).")
    parser.add_argument("--profile", help="Optional dataset profile label recorded in JSON.")
    parser.add_argument("--seed", type=int, help="Optional generator seed recorded in JSON.")
    parser.add_argument("--output", type=Path, help="JSON result path; defaults under benchmarks/results.")
    parser.add_argument(
        "--isolation",
        choices=("process", "none"),
        default="process",
        help="Run every repeat in a clean child process (default: process).",
    )
    parser.add_argument("--child", action="store_true", help=argparse.SUPPRESS)
    return parser


def load_dataframe(path: Path, backend: str = "pandas") -> tuple[Any, float]:
    start = time.perf_counter()
    suffix = path.suffix.lower()
    if backend == "pandas" and suffix == ".parquet":
        dataframe = pd.read_parquet(path)
    elif backend == "pandas" and suffix == ".csv":
        dataframe = pd.read_csv(path)
    elif backend == "polars" and suffix == ".parquet":
        import polars as pl

        dataframe = pl.read_parquet(path)
    elif backend == "polars" and suffix == ".csv":
        import polars as pl

        dataframe = pl.read_csv(path)
    else:
        raise ValueError("input must be a .parquet or .csv file")
    return dataframe, time.perf_counter() - start


def comparison_variant(dataframe: pd.DataFrame) -> pd.DataFrame:
    """Return a deterministic structural variant for compare/drift benchmarks."""

    if len(dataframe.columns) < 3:
        raise ValueError("compare and schema_drift require at least three input columns")
    after = dataframe.iloc[:-1].copy()
    type_column = dataframe.columns[0]
    removed_column = dataframe.columns[-1]
    after[type_column] = after[type_column].astype("string")
    null_column = _nullability_column(after, excluded={type_column, removed_column})
    _introduce_null(after, null_column)
    after = after.drop(columns=[removed_column])
    after["benchmark_added_column"] = np.arange(len(after), dtype=np.int64)
    return after


def _nullability_column(dataframe: pd.DataFrame, excluded: set[str]) -> str:
    """Choose a column that can gain a null while retaining its logical type."""

    candidates = [name for name in dataframe.columns if name not in excluded]
    for predicate in (
        pd.api.types.is_bool_dtype,
        pd.api.types.is_float_dtype,
        pd.api.types.is_datetime64_any_dtype,
        lambda dtype: isinstance(dtype, pd.CategoricalDtype),
        pd.api.types.is_integer_dtype,
    ):
        for name in candidates:
            if predicate(dataframe[name].dtype):
                return name
    return candidates[0]


def _introduce_null(dataframe: pd.DataFrame, column: str) -> None:
    """Add one null without converting a supported column to mixed ``object``."""

    if not len(dataframe):
        return
    series = dataframe[column]
    if pd.api.types.is_bool_dtype(series.dtype):
        dataframe[column] = series.astype("boolean")
        dataframe.loc[dataframe.index[0], column] = pd.NA
    elif pd.api.types.is_integer_dtype(series.dtype):
        dataframe[column] = series.astype("Int64")
        dataframe.loc[dataframe.index[0], column] = pd.NA
    elif pd.api.types.is_float_dtype(series.dtype):
        dataframe.loc[dataframe.index[0], column] = np.nan
    elif pd.api.types.is_datetime64_any_dtype(series.dtype):
        dataframe.loc[dataframe.index[0], column] = pd.NaT
    else:
        dataframe.loc[dataframe.index[0], column] = None


def _operation_callable(operation: str, dataframe: pd.DataFrame):
    import vzor

    if operation == "profile":
        return lambda: vzor.profile(dataframe)
    if operation == "inspect":
        return lambda: vzor.inspect(dataframe)
    if operation == "validate":
        schema = vzor.suggest_schema(dataframe)
        return lambda: vzor.validate(dataframe, schema)
    after = comparison_variant(dataframe)
    if operation == "compare":
        return lambda: vzor.compare(dataframe, after)
    return lambda: vzor.schema_drift(dataframe, after)


def single_run(args: argparse.Namespace) -> dict[str, Any]:
    dataframe, load_seconds = load_dataframe(args.input, args.backend)
    if args.backend == "polars" and args.operation not in {"profile", "inspect"}:
        raise ValueError("Polars benchmark currently supports profile and inspect only")
    operation = _operation_callable(args.operation, dataframe)
    before_memory = process_memory()
    start = time.perf_counter()
    operation()
    elapsed = time.perf_counter() - start
    after_memory = process_memory()
    result = system_metadata(
        dataset_path=args.input,
        rows=len(dataframe),
        columns=len(dataframe.columns),
        operation=args.operation,
        profile=args.profile,
        seed=args.seed,
    )
    result.update(
        {
            "backend": args.backend,
            "parquet_load_seconds": load_seconds if args.input.suffix.lower() == ".parquet" else None,
            "input_load_seconds": load_seconds,
            "elapsed_seconds": elapsed,
            "rows_per_second": len(dataframe) / elapsed if elapsed else None,
            "memory_metric": after_memory["memory_metric"],
            "peak_memory_bytes": after_memory["peak_memory_bytes"],
            "peak_memory_mb": (
                round(after_memory["peak_memory_bytes"] / 1024**2, 3)
                if after_memory["peak_memory_bytes"] is not None
                else None
            ),
            "working_set_before_operation_bytes": before_memory["current_working_set_bytes"],
            "working_set_after_operation_bytes": after_memory["current_working_set_bytes"],
        }
    )
    return result


def _child_command(args: argparse.Namespace) -> list[str]:
    command = [
        sys.executable,
        str(Path(__file__).resolve()),
        "--input",
        str(args.input),
        "--operation",
        args.operation,
        "--backend",
        args.backend,
        "--repeats",
        "1",
        "--isolation",
        "none",
        "--child",
    ]
    if args.profile is not None:
        command.extend(["--profile", args.profile])
    if args.seed is not None:
        command.extend(["--seed", str(args.seed)])
    return command


def _isolated_run(args: argparse.Namespace) -> dict[str, Any]:
    completed = subprocess.run(_child_command(args), capture_output=True, text=True, check=False)
    if completed.returncode:
        raise RuntimeError(completed.stderr.strip() or completed.stdout.strip() or "benchmark child failed")
    try:
        return json.loads(completed.stdout)
    except json.JSONDecodeError as error:
        raise RuntimeError("benchmark child did not emit JSON") from error


def summarize_runs(runs: list[dict[str, Any]], isolation: str) -> dict[str, Any]:
    elapsed = [run["elapsed_seconds"] for run in runs]
    rows_per_second = [run["rows_per_second"] for run in runs if run["rows_per_second"] is not None]
    input_loads = [run["input_load_seconds"] for run in runs]
    parquet_loads = [run["parquet_load_seconds"] for run in runs if run["parquet_load_seconds"] is not None]
    peak_memory = [run["peak_memory_bytes"] for run in runs if run["peak_memory_bytes"] is not None]
    elapsed_median = statistics.median(elapsed)
    rows_per_second_median = statistics.median(rows_per_second) if rows_per_second else None
    peak_memory_max = max(peak_memory) if peak_memory else None
    output = dict(runs[0])
    output.update(
        {
            "isolation": isolation,
            "repeat_count": len(runs),
            "runs": runs,
            "elapsed_seconds": elapsed_median,
            "rows_per_second": rows_per_second_median,
            "input_load_seconds": statistics.median(input_loads),
            "parquet_load_seconds": statistics.median(parquet_loads) if parquet_loads else None,
            "peak_memory_bytes": peak_memory_max,
            "peak_memory_mb": round(peak_memory_max / 1024**2, 3) if peak_memory_max is not None else None,
            "elapsed_seconds_min": min(elapsed),
            "elapsed_seconds_median": elapsed_median,
            "elapsed_seconds_max": max(elapsed),
            "rows_per_second_median": rows_per_second_median,
        }
    )
    return output


def default_output_path(args: argparse.Namespace) -> Path:
    return Path(__file__).resolve().parent / "results" / f"{args.input.stem}_{args.operation}.json"


def run(args: argparse.Namespace) -> dict[str, Any]:
    if args.repeats <= 0:
        raise ValueError("repeats must be positive")
    if not args.input.is_file():
        raise FileNotFoundError(f"input file not found: {args.input}")
    if args.child:
        return single_run(args)
    runs = [single_run(args) if args.isolation == "none" else _isolated_run(args) for _ in range(args.repeats)]
    return summarize_runs(runs, args.isolation)


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        result = run(args)
    except (FileNotFoundError, ImportError, OSError, RuntimeError, ValueError) as error:
        parser.error(str(error))
    if args.child:
        print(json.dumps(result, sort_keys=True))
        return 0
    output = args.output or default_output_path(args)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

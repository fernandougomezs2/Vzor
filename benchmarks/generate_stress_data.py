"""CLI for deterministic, local benchmark dataset generation."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from benchmarks.scenarios import generate_dataframe, profile_names


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate a reproducible Vzor benchmark dataset.")
    parser.add_argument("--rows", type=int, required=True, help="Number of rows (non-negative).")
    parser.add_argument("--columns", type=int, required=True, help="Number of columns (positive).")
    parser.add_argument("--seed", type=int, required=True, help="Deterministic NumPy seed.")
    parser.add_argument("--profile", choices=profile_names(), required=True, help="Dataset profile.")
    parser.add_argument("--output-dir", type=Path, required=True, help="Directory to create/use.")
    parser.add_argument(
        "--format", choices=("parquet", "csv"), default="parquet", help="Output format (default: parquet)."
    )
    return parser


def output_path(output_dir: Path, rows: int, columns: int, seed: int, profile: str, file_format: str) -> Path:
    return output_dir / f"vzor_{rows}_{profile}_{columns}c_seed{seed}.{file_format}"


def generate(args: argparse.Namespace) -> Path:
    dataframe = generate_dataframe(args.rows, args.columns, args.seed, args.profile)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    path = output_path(args.output_dir, args.rows, args.columns, args.seed, args.profile, args.format)
    if args.format == "parquet":
        dataframe.to_parquet(path, index=False)
    else:
        dataframe.to_csv(path, index=False)
    return path


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        path = generate(args)
    except (ImportError, ValueError, OSError) as error:
        parser.error(str(error))
    print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

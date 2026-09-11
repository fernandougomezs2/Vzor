"""Command-line interface for Vzor."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Callable

import pandas as pd

from ._pandas_adapter import _normalize_dataframe
from .agent_output import build_agent_output
from ._vzor_core import (
    compare_datasets as _compare_datasets,
    save_suggested_schema_dataset as _save_suggested_schema_dataset,
    schema_drift_datasets as _schema_drift_datasets,
    validate_dataset_file as _validate_dataset_file,
    version,
)
from .inspection import inspect as inspect_dataframe
from .profile import profile
from .suggested_schema import suggest_schema

EXIT_OK = 0
EXIT_CONDITION = 1
EXIT_ERROR = 2
_SUPPORTED_INPUT_FORMATS = ".csv, .xlsx, .xls, .parquet"


class _CliOperationalError(Exception):
    """An expected CLI error that should be rendered without a traceback."""


def _configure_stream_encoding() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8")


def _load_dataframe(path: Path) -> pd.DataFrame:
    """Load one supported local dataset for CLI use."""
    _require_file(path, "input")
    suffix = path.suffix.lower()
    if suffix not in {".csv", ".xlsx", ".xls", ".parquet"}:
        extension = path.suffix or "(no extension)"
        raise _CliOperationalError(
            f"Unsupported input format: {extension}. Supported formats: {_SUPPORTED_INPUT_FORMATS}"
        )

    reader = (
        pd.read_csv
        if suffix == ".csv"
        else pd.read_excel
        if suffix in {".xlsx", ".xls"}
        else pd.read_parquet
    )
    try:
        return reader(path)
    except (ImportError, OSError, UnicodeError, pd.errors.EmptyDataError, pd.errors.ParserError) as error:
        raise _CliOperationalError(f"could not read input file: {path}: {error}") from error


def _require_file(path: Path, label: str) -> None:
    """Validate a file path before passing it to pandas or persistence."""
    if not path.exists():
        raise _CliOperationalError(f"{label} file not found: {path}")
    if not path.is_file():
        raise _CliOperationalError(f"{label} path is not a file: {path}")


def _require_output_path(path: Path) -> None:
    """Validate an explicit output path without creating parent directories."""
    if not path.parent.exists():
        raise _CliOperationalError(f"output directory not found: {path.parent}")
    if not path.parent.is_dir():
        raise _CliOperationalError(f"output parent is not a directory: {path.parent}")
    if path.exists() and not path.is_file():
        raise _CliOperationalError(f"output path is not a file: {path}")


def _emit_json(value: Any) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False))


def _command_version(_args: argparse.Namespace) -> int:
    print(version())
    return EXIT_OK


def _command_profile(args: argparse.Namespace) -> int:
    _emit_json(build_agent_output("profile", profile(_load_dataframe(args.input))))
    return EXIT_OK


def _command_inspect(args: argparse.Namespace) -> int:
    _emit_json(
        build_agent_output("inspection", inspect_dataframe(_load_dataframe(args.input)))
    )
    return EXIT_OK


def _command_suggest_schema(args: argparse.Namespace) -> int:
    dataframe = _load_dataframe(args.input)
    if args.output is not None:
        _require_output_path(args.output)
        try:
            _save_suggested_schema_dataset(
                _normalize_dataframe(dataframe),
                str(args.output),
            )
        except (OSError, ValueError) as error:
            raise _CliOperationalError(
                f"could not write schema file: {args.output}: {error}"
            ) from error
    else:
        _emit_json(build_agent_output("suggested_schema", suggest_schema(dataframe)))
    return EXIT_OK


def _command_validate(args: argparse.Namespace) -> int:
    dataframe = _load_dataframe(args.input)
    _require_file(args.schema, "schema")
    try:
        result = _validate_dataset_file(
            _normalize_dataframe(dataframe),
            str(args.schema),
        )
    except (OSError, ValueError) as error:
        raise _CliOperationalError(f"could not load schema file: {args.schema}: {error}") from error
    _emit_json(build_agent_output("validation", result))
    return EXIT_OK if result["is_valid"] else EXIT_CONDITION


def _command_compare(args: argparse.Namespace) -> int:
    before = _load_dataframe(args.before)
    after = _load_dataframe(args.after)
    result = _compare_datasets(
        _normalize_dataframe(before),
        _normalize_dataframe(after),
    )
    _emit_json(build_agent_output("comparison", result))
    return EXIT_CONDITION if result["has_changes"] else EXIT_OK


def _command_drift(args: argparse.Namespace) -> int:
    before = _load_dataframe(args.before)
    after = _load_dataframe(args.after)
    result = _schema_drift_datasets(
        _normalize_dataframe(before),
        _normalize_dataframe(after),
    )
    _emit_json(build_agent_output("schema_drift", result))
    return EXIT_CONDITION if result["has_drift"] else EXIT_OK


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="vzor",
        description="Vzor — deterministic data trust and quality tools for local analytics.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(
        dest="command",
        required=True,
        title="commands",
        description="Commands emit deterministic agent-ready JSON to stdout unless noted.",
    )

    version_parser = subparsers.add_parser(
        "version",
        help="Show the Vzor package version.",
        description="Print only the Vzor package version.",
    )
    version_parser.set_defaults(handler=_command_version)

    profile_parser = subparsers.add_parser(
        "profile",
        help="Profile a dataset.",
        description="Profile a local dataset and emit agent-ready JSON.\n\nExit codes:\n  0  Profile completed\n  2  Operational or usage error",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    profile_parser.add_argument("input", type=Path, help="Dataset file (.csv, .xlsx, .xls, or .parquet).")
    profile_parser.set_defaults(handler=_command_profile)

    inspect_parser = subparsers.add_parser(
        "inspect",
        help="Inspect dataset structure and summary.",
        description="Inspect a local dataset and emit agent-ready JSON.\n\nExit codes:\n  0  Inspection completed\n  2  Operational or usage error",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    inspect_parser.add_argument("input", type=Path, help="Dataset file (.csv, .xlsx, .xls, or .parquet).")
    inspect_parser.set_defaults(handler=_command_inspect)

    suggest_parser = subparsers.add_parser(
        "suggest-schema",
        help="Generate a conservative suggested schema.",
        description="Generate a conservative suggested schema from a local dataset.\n\nExit codes:\n  0  Schema generated\n  2  Operational or usage error",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    suggest_parser.add_argument("input", type=Path, help="Dataset file (.csv, .xlsx, .xls, or .parquet).")
    suggest_parser.add_argument(
        "--output",
        type=Path,
        help="Write official versioned schema JSON here; stdout remains empty.",
    )
    suggest_parser.set_defaults(handler=_command_suggest_schema)

    validate_parser = subparsers.add_parser(
        "validate",
        help="Validate a dataset against a persisted schema.",
        description="Validate a dataset against a persisted Vzor suggested schema.\n\nExit codes:\n  0  Validation passed\n  1  Validation failed\n  2  Operational or usage error",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    validate_parser.add_argument("input", type=Path, help="Dataset file (.csv, .xlsx, .xls, or .parquet).")
    validate_parser.add_argument(
        "--schema",
        type=Path,
        required=True,
        help="Persisted Vzor suggested-schema JSON file.",
    )
    validate_parser.set_defaults(handler=_command_validate)

    compare_parser = subparsers.add_parser(
        "compare",
        help="Compare two datasets.",
        description="Compare before and after datasets and emit agent-ready JSON.\n\nExit codes:\n  0  No changes detected\n  1  Changes detected\n  2  Operational or usage error",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    compare_parser.add_argument("before", type=Path, help="Before dataset file.")
    compare_parser.add_argument("after", type=Path, help="After dataset file.")
    compare_parser.set_defaults(handler=_command_compare)

    drift_parser = subparsers.add_parser(
        "drift",
        help="Detect structural schema drift between two datasets.",
        description="Detect structural schema drift between before and after datasets.\n\nExit codes:\n  0  No structural drift detected\n  1  Structural drift detected\n  2  Operational or usage error",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    drift_parser.add_argument("before", type=Path, help="Before dataset file.")
    drift_parser.add_argument("after", type=Path, help="After dataset file.")
    drift_parser.set_defaults(handler=_command_drift)

    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the Vzor CLI and return its process exit code."""
    _configure_stream_encoding()
    parser = _build_parser()
    args = parser.parse_args(argv)
    handler: Callable[[argparse.Namespace], int] = args.handler

    try:
        return handler(args)
    except _CliOperationalError as error:
        print(f"vzor: error: {error}", file=sys.stderr)
        return EXIT_ERROR
    except (OverflowError, TypeError, ValueError) as error:
        print(f"vzor: error: {error}", file=sys.stderr)
        return EXIT_ERROR


if __name__ == "__main__":
    raise SystemExit(main())

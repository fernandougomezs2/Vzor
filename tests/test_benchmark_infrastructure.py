from __future__ import annotations

import json
import os
import sys
from types import SimpleNamespace

import pandas as pd
import pytest

from benchmarks import generate_stress_data, run_benchmark
from benchmarks.scenarios import generate_dataframe, profile_names
from benchmarks.system_info import process_memory, system_metadata


def test_generator_is_deterministic_for_small_baseline() -> None:
    first = generate_dataframe(12, 8, 42, "baseline")
    second = generate_dataframe(12, 8, 42, "baseline")
    pd.testing.assert_frame_equal(first, second)


def test_profiles_are_explicit_and_generate_small_frames() -> None:
    assert profile_names() == (
        "baseline", "numeric", "many_nulls", "high_cardinality", "heavy_strings", "categorical", "wide"
    )
    for name in profile_names():
        assert generate_dataframe(4, 3, 7, name).shape == (4, 3)


@pytest.mark.parametrize("rows, columns", [(-1, 1), (1, 0)])
def test_generator_rejects_invalid_dimensions(rows: int, columns: int) -> None:
    with pytest.raises(ValueError):
        generate_dataframe(rows, columns, 1, "baseline")


def test_generator_parser_rejects_unknown_profile() -> None:
    with pytest.raises(SystemExit):
        generate_stress_data.build_parser().parse_args(
            ["--rows", "1", "--columns", "1", "--seed", "1", "--profile", "unknown", "--output-dir", "out"]
        )


def test_generator_creates_output_directory_and_csv(tmp_path) -> None:
    output_directory = tmp_path / "espacio estrés"
    args = generate_stress_data.build_parser().parse_args(
        ["--rows", "3", "--columns", "2", "--seed", "42", "--profile", "numeric", "--output-dir", str(output_directory), "--format", "csv"]
    )
    path = generate_stress_data.generate(args)
    assert path.is_file()
    assert pd.read_csv(path).shape == (3, 2)


def test_runner_parser_rejects_invalid_operation() -> None:
    with pytest.raises(SystemExit):
        run_benchmark.build_parser().parse_args(["--input", "data.csv", "--operation", "missing"])


def test_result_summary_has_repeat_statistics() -> None:
    runs = [
        {"elapsed_seconds": 3.0, "rows_per_second": 10.0, "input_load_seconds": 0.3, "parquet_load_seconds": 0.3, "peak_memory_bytes": 30, "operation": "profile"},
        {"elapsed_seconds": 1.0, "rows_per_second": 30.0, "input_load_seconds": 0.1, "parquet_load_seconds": 0.1, "peak_memory_bytes": 10, "operation": "profile"},
        {"elapsed_seconds": 2.0, "rows_per_second": 20.0, "input_load_seconds": 0.2, "parquet_load_seconds": 0.2, "peak_memory_bytes": 20, "operation": "profile"},
    ]
    result = run_benchmark.summarize_runs(runs, "process")
    assert result["repeat_count"] == 3
    assert result["elapsed_seconds_min"] == 1.0
    assert result["elapsed_seconds_median"] == 2.0
    assert result["elapsed_seconds_max"] == 3.0
    assert result["rows_per_second_median"] == 20.0
    assert result["elapsed_seconds"] == 2.0
    assert result["rows_per_second"] == 20.0
    assert result["peak_memory_bytes"] == 30
    assert json.loads(json.dumps(result))["isolation"] == "process"


def test_comparison_variant_has_controlled_structural_changes() -> None:
    before = generate_dataframe(5, 5, 42, "baseline")
    after = run_benchmark.comparison_variant(before)
    assert len(after) == len(before) - 1
    assert "benchmark_added_column" in after
    assert before.columns[-1] not in after
    assert str(after.dtypes.iloc[0]).startswith("string")
    assert any(after[column].isna().any() for column in after.columns[1:])


def test_process_memory_returns_a_documented_metric() -> None:
    memory = process_memory()
    assert memory["memory_metric"] in {"peak_working_set_bytes", "peak_rss_bytes"}
    assert "peak_memory_bytes" in memory
    if os.name == "nt":
        assert memory["peak_memory_bytes"] is not None


def test_system_metadata_contains_dataset_context(tmp_path, monkeypatch) -> None:
    dataset = tmp_path / "datos estrés.csv"
    dataset.write_text("value\n1\n", encoding="utf-8")
    monkeypatch.setitem(sys.modules, "vzor", SimpleNamespace(__version__="0.4.1"))
    metadata = system_metadata(
        dataset_path=dataset, rows=1, columns=1, operation="inspect", profile="baseline", seed=42
    )
    assert metadata["dataset_name"] == dataset.name
    assert metadata["dataset_file_size_bytes"] == dataset.stat().st_size
    assert metadata["backend"] == "pandas"
    assert metadata["vzor_version"] == "0.4.1"
    assert "dataset_disk_total_bytes" in metadata


def test_runner_writes_json_output(tmp_path, monkeypatch) -> None:
    output = tmp_path / "result.json"
    fake_result = {"operation": "profile", "elapsed_seconds": 0.01}
    monkeypatch.setattr(run_benchmark, "run", lambda args: fake_result)
    exit_code = run_benchmark.main(
        ["--input", str(tmp_path / "input.csv"), "--operation", "profile", "--output", str(output)]
    )
    assert exit_code == 0
    assert json.loads(output.read_text(encoding="utf-8")) == fake_result

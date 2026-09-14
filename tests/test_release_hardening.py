"""Release-hardening regressions for public v0.4 behavior.

These examples deliberately exercise public Python entry points.  Broad value
generation belongs to the pure Rust property targets, keeping this suite fast
and free from an additional Python test dependency.
"""

from html import escape
import math

import numpy as np
import pandas as pd
import pytest

import vzor
from vzor.cli import main


def test_extreme_float_profile_is_deterministic_and_keeps_finite_statistics() -> None:
    dataframe = pd.DataFrame(
        {
            "extreme": [
                -np.finfo("float64").max,
                -1.0,
                np.nan,
                0.0,
                1.0,
                np.finfo("float64").max,
                np.inf,
                -np.inf,
            ]
        }
    )

    first = vzor.profile(dataframe)
    second = vzor.profile(dataframe)
    column = first.column("extreme")

    assert first == second
    assert column.count == len(dataframe)
    assert column.null_count == 1
    assert column.unique_count <= column.count
    assert column.numeric_stats is not None
    for value in (
        column.numeric_stats.min,
        column.numeric_stats.max,
        column.numeric_stats.mean,
        column.numeric_stats.p25,
        column.numeric_stats.p50,
        column.numeric_stats.p75,
    ):
        assert math.isfinite(value)
    assert column.numeric_stats.min <= column.numeric_stats.p25 <= column.numeric_stats.p50
    assert column.numeric_stats.p50 <= column.numeric_stats.p75 <= column.numeric_stats.max


def test_all_report_html_writers_escape_untrusted_column_names_and_are_deterministic(tmp_path) -> None:
    malicious = '<img src=x onerror="alert(1)">'
    reports = {
        "inspection": vzor.inspect(pd.DataFrame({malicious: [malicious]})),
        "validation": vzor.validate(
            pd.DataFrame({malicious: [1]}),
            vzor.SuggestedDatasetSchema(columns=()),
        ),
        "comparison": vzor.compare(pd.DataFrame({malicious: [1]}), pd.DataFrame()),
        "drift": vzor.schema_drift(pd.DataFrame({malicious: [1]}), pd.DataFrame()),
    }

    for name, report in reports.items():
        first = tmp_path / f"{name} first.html"
        second = tmp_path / f"{name} second.html"
        report.to_html(first)
        report.to_html(second)
        content = first.read_text(encoding="utf-8")

        assert first.read_bytes() == second.read_bytes()
        assert escape(malicious, quote=True) in content
        assert malicious not in content
        assert "<script" not in content.lower()
        assert "https://" not in content.lower()


@pytest.mark.parametrize(
    "content",
    (
        "",
        "[]",
        "{}",
        '{"format_version":1}',
        '{"format_version":1,"schema":null}',
        '{"format_version":"1","schema":{"columns":[]}}',
        '{"format_version":1,"schema":{"columns":"not-a-list"}}',
    ),
)
def test_cli_rejects_malformed_persistence_without_structured_stdout(
    tmp_path, capsys, content: str
) -> None:
    dataset = tmp_path / "source.csv"
    schema = tmp_path / "invalid schema.json"
    dataset.write_text("id\n1\n", encoding="utf-8")
    schema.write_text(content, encoding="utf-8")

    assert main(["validate", str(dataset), "--schema", str(schema)]) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.startswith(f"vzor: error: could not load schema file: {schema}: ")


def test_public_reports_remain_deterministic_for_mixed_edge_types() -> None:
    pandas_frame = pd.DataFrame(
        {
            "integer": pd.Series([0, -1, 2**63 - 1], dtype="int64"),
            "boolean": pd.Series([True, False, pd.NA], dtype="boolean"),
            "string": pd.Series(["", "NULL", "Región"], dtype="string"),
            "categorical": pd.Series(pd.Categorical(["A", "B", "A"])),
            "datetime": pd.to_datetime(["2026-01-01", None, "2026-01-03"]),
        }
    )

    first = (
        vzor.inspect(pandas_frame),
        vzor.validate(pandas_frame, vzor.suggest_schema(pandas_frame)),
        vzor.compare(pandas_frame, pandas_frame),
        vzor.schema_drift(pandas_frame, pandas_frame),
    )
    second = (
        vzor.inspect(pandas_frame),
        vzor.validate(pandas_frame, vzor.suggest_schema(pandas_frame)),
        vzor.compare(pandas_frame, pandas_frame),
        vzor.schema_drift(pandas_frame, pandas_frame),
    )

    assert first == second
    assert first[1].is_valid
    assert not first[2].has_changes
    assert not first[3].has_drift

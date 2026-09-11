from html import escape

import pandas as pd
import pytest

import vzor


def assert_standalone_html(content: str, title: str) -> None:
    lowered = content.lower()
    assert content.startswith("<!doctype html>\n")
    assert f"<h1>{title}</h1>" in content
    assert '<meta charset="utf-8">' in content
    assert "<style>" in content
    assert "<table>" in content
    assert "http://" not in lowered
    assert "https://" not in lowered
    assert "cdn" not in lowered
    assert "<script" not in lowered


def test_inspection_html_is_complete_safe_utf8_and_deterministic(tmp_path) -> None:
    malicious = '<script>alert("x")</script>'
    dataframe = pd.DataFrame(
        {
            malicious: ["<b>unsafe</b>"],
            "Región": ["México"],
            **{f"column_{index}": [index] for index in range(6)},
        }
    )
    report = vzor.inspect(dataframe)
    first = tmp_path / "inspection report one.html"
    second = tmp_path / "inspection report two.html"

    assert "... 3 more items" in repr(report)
    assert report.to_html(first) is None
    report.to_html(second)
    first_bytes = first.read_bytes()
    content = first_bytes.decode("utf-8")

    assert first_bytes == second.read_bytes()
    assert_standalone_html(content, "Vzor Inspection Report")
    assert report.human_summary in content
    assert "column_5" in content
    assert "Región" in content
    assert "México" in content
    assert escape(malicious, quote=True) in content
    assert escape("<b>unsafe</b>", quote=True) in content
    assert malicious not in content


def test_validation_html_contains_every_issue_and_overwrites_file(tmp_path) -> None:
    dataframe = pd.DataFrame({f"unexpected_{index}": [index] for index in range(8)})
    report = vzor.validate(dataframe, vzor.SuggestedDatasetSchema(columns=()))
    output = tmp_path / "validation.html"
    output.write_text("old content", encoding="utf-8")

    report.to_html(output)
    content = output.read_text(encoding="utf-8")

    assert_standalone_html(content, "Vzor Validation Report")
    assert report.human_summary in content
    assert len(report.issues) == 8
    for issue in report.issues:
        assert issue.column in content
    assert "old content" not in content


def test_comparison_html_contains_all_columns_and_snapshots(tmp_path) -> None:
    before = pd.DataFrame({f"before_{index}": [index] for index in range(7)})
    after = pd.DataFrame({f"after_{index}": [index] for index in range(7)})
    report = vzor.compare(before, after)
    output = tmp_path / "comparison.html"

    report.to_html(output)
    content = output.read_text(encoding="utf-8")

    assert_standalone_html(content, "Vzor Comparison Report")
    assert report.human_summary in content
    assert len(report.columns) == 14
    for column in report.columns:
        assert column.name in content
    assert "logical_type=integer" in content
    assert "column_removed" not in content


def test_schema_drift_html_contains_every_issue(tmp_path) -> None:
    before = pd.DataFrame({f"removed_{index}": [index] for index in range(7)})
    after = pd.DataFrame({f"added_{index}": [index] for index in range(7)})
    report = vzor.schema_drift(before, after)
    output = tmp_path / "drift.html"

    report.to_html(output)
    content = output.read_text(encoding="utf-8")

    assert_standalone_html(content, "Vzor Schema Drift Report")
    assert report.human_summary in content
    assert len(report.issues) == 14
    for issue in report.issues:
        assert issue.column in content
        assert issue.code in content


def test_html_supports_relative_paths_and_rejects_invalid_targets(
    tmp_path,
    monkeypatch,
) -> None:
    report = vzor.inspect(pd.DataFrame({"id": [1]}))
    working = tmp_path / "working directory"
    working.mkdir()
    monkeypatch.chdir(working)

    report.to_html("relative report.html")
    assert (working / "relative report.html").is_file()

    missing = working / "missing parent" / "report.html"
    with pytest.raises(FileNotFoundError, match="HTML report directory not found"):
        report.to_html(missing)
    assert not missing.parent.exists()

    with pytest.raises(IsADirectoryError, match="HTML report path is not a file"):
        report.to_html(working)

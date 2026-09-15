import json
import subprocess
import sys

import pytest

import vzor.cli as cli
from vzor.cli import main


def write_csv(path, content: str) -> None:
    path.write_text(content, encoding="utf-8")


def read_json_output(capsys):
    captured = capsys.readouterr()
    assert captured.err == ""
    return json.loads(captured.out)


def assert_agent_output(output, kind: str):
    assert list(output) == [
        "output_version",
        "kind",
        "human_summary",
        "machine_payload",
    ]
    assert output["output_version"] == 1
    assert output["kind"] == kind
    assert isinstance(output["human_summary"], str)
    assert isinstance(output["machine_payload"], dict)
    return output["machine_payload"]


def test_help_lists_every_command(capsys) -> None:
    with pytest.raises(SystemExit) as exit_info:
        main(["--help"])

    assert exit_info.value.code == 0
    help_text = capsys.readouterr().out
    assert "Vzor" in help_text
    assert "data trust and quality" in help_text
    assert "commands" in help_text
    for command in (
        "version",
        "profile",
        "inspect",
        "suggest-schema",
        "validate",
        "compare",
        "drift",
    ):
        assert command in help_text


@pytest.mark.parametrize(
    ("command", "expected_text"),
    [
        ("profile", "Profile a local dataset"),
        ("inspect", "Inspect a local dataset"),
        ("suggest-schema", "Generate a conservative suggested schema"),
        ("validate", "Validate a dataset against a persisted Vzor suggested schema"),
        ("compare", "Compare before and after datasets"),
        ("drift", "Detect structural schema drift"),
    ],
)
def test_command_help_is_clear_and_lists_exit_codes(capsys, command: str, expected_text: str) -> None:
    with pytest.raises(SystemExit) as exit_info:
        main([command, "--help"])

    captured = capsys.readouterr()
    assert exit_info.value.code == 0
    assert captured.err == ""
    assert expected_text in captured.out
    assert "Exit codes:" in captured.out
    assert "Operational or usage error" in captured.out


def test_version_has_exact_stdout_and_no_stderr(capsys) -> None:
    assert main(["version"]) == 0
    captured = capsys.readouterr()
    assert captured.out == "0.4.1\n"
    assert captured.err == ""


def test_profile_inspect_and_suggest_schema_emit_json(tmp_path, capsys) -> None:
    dataset = tmp_path / "ventas septiembre.csv"
    write_csv(dataset, "id,Región\n1,México\n2,Niñez\n")

    assert main(["profile", str(dataset)]) == 0
    profile_output = read_json_output(capsys)
    profile = assert_agent_output(profile_output, "profile")
    assert profile["row_count"] == 2
    assert [column["name"] for column in profile["columns"]] == ["id", "Región"]

    assert main(["inspect", str(dataset)]) == 0
    inspection_output = read_json_output(capsys)
    inspection = assert_agent_output(inspection_output, "inspection")
    assert set(inspection) == {
        "profile",
        "observed_schema",
        "suggested_schema",
        "summary",
    }
    assert inspection["summary"]["row_count"] == 2

    assert main(["suggest-schema", str(dataset)]) == 0
    suggested_output = read_json_output(capsys)
    suggested = assert_agent_output(suggested_output, "suggested_schema")
    assert [column["name"] for column in suggested["columns"]] == ["id", "Región"]
    assert "México" in json.dumps(inspection_output, ensure_ascii=False)


def test_suggest_output_uses_official_persistence_and_validate_exit_codes(
    tmp_path, capsys
) -> None:
    valid = tmp_path / "valid.csv"
    invalid = tmp_path / "invalid.csv"
    schema = tmp_path / "schema.json"
    write_csv(valid, "id\n1\n2\n")
    write_csv(invalid, "id\nbad\n")

    assert main(["suggest-schema", str(valid), "--output", str(schema)]) == 0
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""
    persisted = json.loads(schema.read_text(encoding="utf-8"))
    assert set(persisted) == {"format_version", "schema"}
    assert "output_version" not in persisted
    assert "human_summary" not in persisted
    assert "machine_payload" not in persisted
    assert persisted["format_version"] == 1
    assert persisted["schema"]["columns"][0]["logical_type"] == "integer"

    assert main(["validate", str(valid), "--schema", str(schema)]) == 0
    valid_output = read_json_output(capsys)
    valid_result = assert_agent_output(valid_output, "validation")
    assert valid_output["human_summary"] == "Validation passed: 0 errors, 0 warnings."
    assert valid_result["is_valid"] is True
    assert valid_result["error_count"] == 0

    assert main(["validate", str(invalid), "--schema", str(schema)]) == 1
    invalid_output = read_json_output(capsys)
    invalid_result = assert_agent_output(invalid_output, "validation")
    assert invalid_result["is_valid"] is False
    assert invalid_result["issues"][0]["code"] == "type_mismatch"
    assert (
        invalid_result["issues"][0]["stable_code"]
        == "VZOR_VALIDATION_TYPE_MISMATCH"
    )


def test_suggest_output_path_errors_are_clean_and_do_not_create_directories(
    tmp_path, capsys
) -> None:
    dataset = tmp_path / "data.csv"
    missing_output = tmp_path / "missing" / "schema.json"
    directory_output = tmp_path / "directory-output"
    write_csv(dataset, "id\n1\n")
    directory_output.mkdir()

    assert main(["suggest-schema", str(dataset), "--output", str(missing_output)]) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == f"vzor: error: output directory not found: {missing_output.parent}\n"
    assert not missing_output.parent.exists()

    assert main(["suggest-schema", str(dataset), "--output", str(directory_output)]) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == f"vzor: error: output path is not a file: {directory_output}\n"


def test_compare_and_drift_apply_condition_exit_codes(tmp_path, capsys) -> None:
    before = tmp_path / "before.csv"
    same = tmp_path / "same.csv"
    more_rows = tmp_path / "more.csv"
    removed = tmp_path / "removed.csv"
    write_csv(before, "id,legacy\n1,x\n")
    write_csv(same, "id,legacy\n1,x\n")
    write_csv(more_rows, "id,legacy\n1,x\n2,y\n")
    write_csv(removed, "id\n1\n")

    assert main(["compare", str(before), str(same)]) == 0
    same_output = read_json_output(capsys)
    same_result = assert_agent_output(same_output, "comparison")
    assert same_output["human_summary"] == "Comparison completed: no changes detected."
    assert same_result["has_changes"] is False
    assert same_result["unchanged_count"] == 2

    assert main(["compare", str(before), str(more_rows)]) == 1
    changed_output = read_json_output(capsys)
    changed_result = assert_agent_output(changed_output, "comparison")
    assert changed_result["has_changes"] is True
    assert changed_result["row_count_changed"] is True

    assert main(["drift", str(before), str(more_rows)]) == 0
    no_drift_output = read_json_output(capsys)
    no_drift = assert_agent_output(no_drift_output, "schema_drift")
    assert no_drift_output["human_summary"] == "Schema drift not detected."
    assert no_drift["has_drift"] is False

    assert main(["drift", str(before), str(removed)]) == 1
    drift_output = read_json_output(capsys)
    drift = assert_agent_output(drift_output, "schema_drift")
    assert drift["has_drift"] is True
    assert drift["issues"] == [
        {
            "code": "column_removed",
            "stable_code": "VZOR_DRIFT_COLUMN_REMOVED",
            "severity": "error",
            "column": "legacy",
        }
    ]


def test_operational_errors_use_stderr_and_exit_two(tmp_path, capsys) -> None:
    missing = tmp_path / "missing.csv"
    assert main(["profile", str(missing)]) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == f"vzor: error: input file not found: {missing}\n"

    unsupported = tmp_path / "data.txt"
    write_csv(unsupported, "x\n1\n")
    assert main(["profile", str(unsupported)]) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == (
        "vzor: error: Unsupported input format: .txt. "
        "Supported formats: .csv, .xlsx, .xls, .parquet\n"
    )


def test_missing_schema_and_unreadable_input_are_clean_operational_errors(
    tmp_path, monkeypatch, capsys
) -> None:
    dataset = tmp_path / "data.csv"
    schema = tmp_path / "missing schema.json"
    write_csv(dataset, "id\n1\n")

    assert main(["validate", str(dataset), "--schema", str(schema)]) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == f"vzor: error: schema file not found: {schema}\n"

    def unreadable(_path):
        raise PermissionError("access denied")

    monkeypatch.setattr(cli.pd, "read_csv", unreadable)
    assert main(["profile", str(dataset)]) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == f"vzor: error: could not read input file: {dataset}: access denied\n"


def test_missing_arguments_use_argparse_stderr_and_exit_two(capsys) -> None:
    with pytest.raises(SystemExit) as exit_info:
        main(["validate"])

    captured = capsys.readouterr()
    assert exit_info.value.code == 2
    assert captured.out == ""
    assert captured.err.startswith("usage: vzor validate")
    assert "vzor validate: error:" in captured.err


def test_invalid_schema_and_unsupported_version_exit_two(tmp_path, capsys) -> None:
    dataset = tmp_path / "data.csv"
    invalid = tmp_path / "invalid.json"
    unsupported = tmp_path / "unsupported.json"
    write_csv(dataset, "id\n1\n")
    invalid.write_text("not-json", encoding="utf-8")
    unsupported.write_text(
        '{"format_version":999,"schema":{"columns":[]}}',
        encoding="utf-8",
    )

    assert main(["validate", str(dataset), "--schema", str(invalid)]) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.startswith(f"vzor: error: could not load schema file: {invalid}: ")

    assert main(["validate", str(dataset), "--schema", str(unsupported)]) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "Unsupported suggested schema format version: 999" in captured.err


def test_profile_output_is_deterministic(tmp_path, capsys) -> None:
    dataset = tmp_path / "deterministic.csv"
    write_csv(dataset, "x\n1\n2\n3\n")

    assert main(["profile", str(dataset)]) == 0
    first = capsys.readouterr()
    assert first.err == ""
    assert main(["profile", str(dataset)]) == 0
    second = capsys.readouterr()
    assert second.err == ""
    assert first.out == second.out


def test_unknown_internal_code_is_an_operational_error(
    tmp_path, monkeypatch, capsys
) -> None:
    dataset = tmp_path / "data.csv"
    schema = tmp_path / "schema.json"
    write_csv(dataset, "id\n1\n")
    schema.write_text('{"format_version":1,"schema":{"columns":[]}}', encoding="utf-8")

    monkeypatch.setattr(
        cli,
        "_validate_dataset_file",
        lambda _dataset, _schema: {
            "is_valid": False,
            "error_count": 1,
            "warning_count": 0,
            "issues": [
                {
                    "code": "future_validation_code",
                    "severity": "error",
                    "column": "id",
                    "expected": None,
                    "observed": None,
                }
            ],
        },
    )

    assert main(["validate", str(dataset), "--schema", str(schema)]) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == "vzor: error: Unknown validation code: future_validation_code\n"


@pytest.mark.parametrize(
    ("filename", "reader_name"),
    [
        ("data.xlsx", "read_excel"),
        ("data.xls", "read_excel"),
        ("data.parquet", "read_parquet"),
    ],
)
def test_optional_input_formats_dispatch_to_pandas(
    tmp_path, monkeypatch, filename: str, reader_name: str
) -> None:
    path = tmp_path / filename
    path.touch()
    sentinel = object()

    def fake_reader(received_path):
        assert received_path == path
        return sentinel

    monkeypatch.setattr(cli.pd, reader_name, fake_reader)
    assert cli._load_dataframe(path) is sentinel


def test_module_entry_point_runs_in_a_subprocess() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "vzor.cli", "version"],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )

    assert result.returncode == 0
    assert result.stdout == "0.4.1\n"
    assert result.stderr == ""

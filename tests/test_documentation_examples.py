from pathlib import Path
import subprocess
import sys

import vzor


ROOT = Path(__file__).resolve().parents[1]


def test_readme_links_and_documentation_structure_exist() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")

    for relative_path in (
        "docs/getting-started.md",
        "docs/concepts.md",
        "docs/professional-workflows.md",
        "AGENTS.md",
        "LICENSE",
        "CHANGELOG.md",
    ):
        assert f"]({relative_path})" in readme
        assert (ROOT / relative_path).is_file()
    assert "pip install vzor" not in readme
    assert "vzor.export_excel(" not in readme
    assert "vzor.contract(" not in readme
    assert "vzor.analyze_join(" not in readme
    assert "[MIT License](LICENSE)" in readme
    assert 'report.to_html("vzor report.html")' in readme


def test_documented_public_api_exists() -> None:
    documentation = "\n".join(
        (ROOT / path).read_text(encoding="utf-8")
        for path in (
            "README.md",
            "docs/getting-started.md",
            "docs/concepts.md",
            "docs/professional-workflows.md",
        )
    )

    for name in (
        "profile",
        "observed_schema",
        "suggest_schema",
        "inspect",
        "validate",
        "compare",
        "schema_drift",
    ):
        assert callable(getattr(vzor, name))
        assert f"vzor.{name}" in documentation


def test_basic_workflow_example_runs_using_only_public_api() -> None:
    example = ROOT / "examples" / "basic_workflow.py"
    source = example.read_text(encoding="utf-8")
    result = subprocess.run(
        [sys.executable, str(example)],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )

    assert "import vzor" in source
    assert "_vzor_core" not in source
    assert result.returncode == 0, result.stderr
    assert result.stderr == ""
    assert "Inspection completed:" in result.stdout
    assert "Validation failed:" in result.stdout
    assert "Comparison completed:" in result.stdout
    assert "Schema drift detected:" in result.stdout

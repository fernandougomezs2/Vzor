from pathlib import Path


def test_agents_guide_documents_current_contracts_without_fiction() -> None:
    guide = Path(__file__).resolve().parents[1] / "AGENTS.md"
    text = guide.read_text(encoding="utf-8")

    assert guide.is_file()
    for heading in (
        "# Vzor Agent Guide",
        "## Public Python API",
        "## Validation Semantics",
        "## Comparison Semantics",
        "## Schema Drift Semantics",
        "## Persistence Contracts",
        "## Agent-Ready Output Contracts",
        "## Instructions for AI Agents",
    ):
        assert heading in text
    for api in (
        "vzor.profile(df)",
        "vzor.observed_schema(df)",
        "vzor.suggest_schema(df)",
        "vzor.inspect(df)",
        "vzor.validate(df, schema)",
        "vzor.compare(before, after)",
        "vzor.schema_drift(before, after)",
    ):
        assert api in text
    assert '"output_version": 1' in text
    assert "format_version = 1" in text
    assert 'report.to_html("validation.html")' in text
    assert "full summary and" in text
    assert "at most five structural preview items" in text
    assert "does not clean, transform, or auto-fix" in text
    for fictional_api in ("vzor.clean(df)", "vzor.fix(df)", "vzor.read_csv(df)"):
        assert fictional_api not in text

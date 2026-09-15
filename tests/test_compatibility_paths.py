from __future__ import annotations

import json
import os
import stat

import pandas as pd
import pytest

import vzor
from vzor.cli import main


def test_unicode_and_space_paths_cover_cli_html_and_persistence(tmp_path, capsys) -> None:
    directory = tmp_path / "Vzor prueba_日本語"
    directory.mkdir()
    dataset = directory / "datos_áéíóú_测试.csv"
    schema = directory / "schema ñ.json"
    inspection_html = directory / "reporte_inspección_ñ_日本語.html"
    validation_html = directory / "reporte_validación_ñ_日本語.html"
    comparison_html = directory / "reporte_comparación_ñ_日本語.html"
    drift_html = directory / "reporte_drift_ñ_日本語.html"
    pd.DataFrame({"id": [1, 2], "name": ["á", "東京"]}).to_csv(dataset, index=False)

    assert main(["version"]) == 0
    capsys.readouterr()
    assert main(["profile", str(dataset)]) == 0
    capsys.readouterr()
    assert main(["inspect", str(dataset)]) == 0
    capsys.readouterr()
    assert main(["suggest-schema", str(dataset), "--output", str(schema)]) == 0
    capsys.readouterr()
    assert json.loads(schema.read_text(encoding="utf-8"))["format_version"] == 1
    assert main(["validate", str(dataset), "--schema", str(schema)]) == 0
    capsys.readouterr()
    assert main(["compare", str(dataset), str(dataset)]) == 0
    capsys.readouterr()
    assert main(["drift", str(dataset), str(dataset)]) == 0
    capsys.readouterr()

    dataframe = pd.read_csv(dataset)
    schema_object = vzor.suggest_schema(dataframe)
    reports = (
        (vzor.inspect(dataframe), inspection_html, "Inspection completed"),
        (vzor.validate(dataframe, schema_object), validation_html, "Validation"),
        (vzor.compare(dataframe, dataframe), comparison_html, "Comparison"),
        (vzor.schema_drift(dataframe, dataframe), drift_html, "Schema drift"),
    )
    for report, path, expected in reports:
        report.to_html(path)
        assert expected in path.read_text(encoding="utf-8")


@pytest.mark.skipif(os.name == "nt", reason="POSIX permission semantics are exercised in Linux CI")
def test_html_write_to_read_only_directory_has_a_clear_os_error(tmp_path) -> None:
    directory = tmp_path / "read only"
    directory.mkdir()
    destination = directory / "report.html"
    directory.chmod(stat.S_IRUSR | stat.S_IXUSR)
    try:
        with pytest.raises(PermissionError):
            vzor.inspect(pd.DataFrame({"id": [1]})).to_html(destination)
    finally:
        directory.chmod(stat.S_IRWXU)


def test_public_version_and_exports_remain_compatibility_surface() -> None:
    assert vzor.__version__ == vzor.version() == "0.4.1"
    assert "normalize_dataframe" not in vzor.__all__

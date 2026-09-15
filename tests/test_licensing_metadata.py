from pathlib import Path
import tomllib


ROOT = Path(__file__).resolve().parents[1]


def test_project_license_metadata_uses_the_custom_license_file() -> None:
    pyproject_text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    pyproject = tomllib.loads(pyproject_text)
    cargo = tomllib.loads(
        (ROOT / "crates" / "vzor-core" / "Cargo.toml").read_text(encoding="utf-8")
    )

    assert pyproject["project"]["license"] == {"file": "LICENSE"}
    assert "MIT" not in pyproject_text
    assert "OSI Approved" not in pyproject_text
    assert cargo["package"]["license-file"] == "../../LICENSE"
    assert "license" not in cargo["package"]
    assert (ROOT / "LICENSE").read_text(encoding="utf-8").startswith(
        "Vzor Community and SaaS License 1.0\n"
    )

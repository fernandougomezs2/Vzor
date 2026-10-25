from pathlib import Path
import tomllib


ROOT = Path(__file__).resolve().parents[1]
MIT_LICENSE = """MIT License

Copyright (c) 2026 Vzor contributors

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""


def test_project_license_metadata_uses_pep_639_mit_metadata() -> None:
    pyproject_text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    pyproject = tomllib.loads(pyproject_text)
    cargo = tomllib.loads(
        (ROOT / "crates" / "vzor-core" / "Cargo.toml").read_text(encoding="utf-8")
    )

    assert pyproject["build-system"]["requires"] == ["maturin>=1.9.3,<2"]
    assert pyproject["project"]["license"] == "MIT"
    assert pyproject["project"]["license-files"] == [
        "LICENSE",
        "THIRD_PARTY_NOTICES.md",
        "THIRD_PARTY_LICENSES/Apache-2.0-with-LLVM-exception.txt",
    ]
    assert cargo["package"]["license"] == "MIT"
    assert "license-file" not in cargo["package"]
    assert (ROOT / "LICENSE").read_text(encoding="utf-8") == MIT_LICENSE
    notices = (ROOT / "THIRD_PARTY_NOTICES.md").read_text(encoding="utf-8")
    assert "memoffset 0.9.1" in notices
    assert "Unicode License V3" in notices
    apache_license = (
        ROOT / "THIRD_PARTY_LICENSES" / "Apache-2.0-with-LLVM-exception.txt"
    ).read_text(encoding="utf-8")
    assert "LLVM Exceptions to the Apache 2.0 License" in apache_license


def test_project_urls_match_public_pypi_destinations() -> None:
    project = tomllib.loads(
        (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    )["project"]

    assert project["urls"] == {
        "Repository": "https://github.com/fernandougomezs2/Vzor",
        "Documentation": "https://github.com/fernandougomezs2/Vzor#readme",
        "Issues": "https://github.com/fernandougomezs2/Vzor/issues",
        "Changelog": "https://github.com/fernandougomezs2/Vzor/blob/main/CHANGELOG.md",
    }

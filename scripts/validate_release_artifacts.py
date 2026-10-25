"""Validate release-wheel names, package metadata, and Vzor licensing."""

from __future__ import annotations

import sys
from email.parser import BytesParser
from pathlib import Path
from zipfile import ZipFile


EXPECTED_PROJECT_URLS = {
    "Repository": "https://github.com/fernandougomezs2/Vzor",
    "Issues": "https://github.com/fernandougomezs2/Vzor/issues",
    "Documentation": "https://github.com/fernandougomezs2/Vzor#readme",
    "Changelog": "https://github.com/fernandougomezs2/Vzor/blob/main/CHANGELOG.md",
}


def main() -> int:
    if len(sys.argv) != 3:
        raise SystemExit("Usage: validate_release_artifacts.py DIST_DIRECTORY RELEASE_TAG")

    dist_directory = Path(sys.argv[1])
    tag = sys.argv[2]
    if not tag.startswith("v") or len(tag) == 1:
        raise SystemExit(f"Release tag {tag!r} must begin with 'v' and include a version.")
    package_version = tag[1:]
    expected_license = (
        Path(__file__).resolve().parents[1] / "LICENSE"
    ).read_text(encoding="utf-8").replace("\r\n", "\n")

    expected = {
        f"vzor-{package_version}-cp312-cp312-win_amd64.whl",
        f"vzor-{package_version}-cp313-cp313-win_amd64.whl",
        f"vzor-{package_version}-cp312-cp312-manylinux_2_28_x86_64.whl",
        f"vzor-{package_version}-cp313-cp313-manylinux_2_28_x86_64.whl",
    }
    distribution_files = sorted(path for path in dist_directory.iterdir() if path.is_file())
    actual = {path.name for path in distribution_files}
    if actual != expected or len(distribution_files) != len(actual):
        raise SystemExit(f"Expected exactly {sorted(expected)!r}; found {sorted(actual)!r}.")

    for wheel in distribution_files:
        with ZipFile(wheel) as archive:
            names = archive.namelist()
            metadata_paths = [name for name in names if name.endswith(".dist-info/METADATA")]
            license_paths = [name for name in names if name.endswith(".dist-info/licenses/LICENSE")]
            notice_paths = [
                name
                for name in names
                if name.endswith(".dist-info/licenses/THIRD_PARTY_NOTICES.md")
            ]
            apache_paths = [
                name
                for name in names
                if name.endswith(
                    ".dist-info/licenses/THIRD_PARTY_LICENSES/Apache-2.0-with-LLVM-exception.txt"
                )
            ]
            if (
                len(metadata_paths) != 1
                or len(license_paths) != 1
                or len(notice_paths) != 1
                or len(apache_paths) != 1
            ):
                raise SystemExit(
                    f"{wheel.name} must contain METADATA, LICENSE, and third-party legal files."
                )
            metadata_bytes = archive.read(metadata_paths[0])
            metadata = BytesParser().parsebytes(metadata_bytes)
            if metadata["Name"] != "vzor" or metadata["Version"] != package_version:
                raise SystemExit(f"{wheel.name} has unexpected package identity.")
            if metadata["Metadata-Version"] != "2.4":
                raise SystemExit(f"{wheel.name} must use Core Metadata 2.4.")
            if metadata["License-Expression"] != "MIT" or metadata["License"] is not None:
                raise SystemExit(f"{wheel.name} must declare only License-Expression: MIT.")
            if metadata.get_all("License-File", []) != [
                "LICENSE",
                "THIRD_PARTY_NOTICES.md",
                "THIRD_PARTY_LICENSES/Apache-2.0-with-LLVM-exception.txt",
            ]:
                raise SystemExit(f"{wheel.name} has unexpected License-File metadata.")
            project_urls = {}
            for value in metadata.get_all("Project-URL", []):
                label, url = value.split(", ", 1)
                project_urls[label] = url
            if project_urls != EXPECTED_PROJECT_URLS:
                raise SystemExit(f"{wheel.name} has unexpected project URLs: {project_urls!r}.")
            license_text = archive.read(license_paths[0]).decode("utf-8").replace("\r\n", "\n")
            if license_text != expected_license:
                raise SystemExit(f"{wheel.name} does not contain the MIT License text.")
            notice_text = archive.read(notice_paths[0]).decode("utf-8")
            if "memoffset 0.9.1" not in notice_text or "Unicode License V3" not in notice_text:
                raise SystemExit(f"{wheel.name} has incomplete third-party notices.")
            apache_text = archive.read(apache_paths[0]).decode("utf-8")
            if "LLVM Exceptions to the Apache 2.0 License" not in apache_text:
                raise SystemExit(f"{wheel.name} lacks the target-lexicon license exception.")
        print(f"Validated {wheel.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Validate release-wheel names, package metadata, and Vzor licensing."""

from __future__ import annotations

import sys
from email.parser import BytesParser
from pathlib import Path
from zipfile import ZipFile


def main() -> int:
    if len(sys.argv) != 3:
        raise SystemExit("Usage: validate_release_artifacts.py DIST_DIRECTORY RELEASE_TAG")

    dist_directory = Path(sys.argv[1])
    tag = sys.argv[2]
    if not tag.startswith("v") or len(tag) == 1:
        raise SystemExit(f"Release tag {tag!r} must begin with 'v' and include a version.")
    package_version = tag[1:]

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
            if len(metadata_paths) != 1 or len(license_paths) != 1:
                raise SystemExit(f"{wheel.name} must contain one METADATA and one packaged LICENSE.")
            metadata_bytes = archive.read(metadata_paths[0])
            metadata = BytesParser().parsebytes(metadata_bytes)
            metadata_text = metadata_bytes.decode("utf-8")
            if metadata["Name"] != "vzor" or metadata["Version"] != package_version:
                raise SystemExit(f"{wheel.name} has unexpected package identity.")
            if "LICENSE" not in metadata.get_all("License-File", []):
                raise SystemExit(f"{wheel.name} lacks License-File: LICENSE.")
            if "MIT" in metadata_text or "OSI Approved" in metadata_text:
                raise SystemExit(f"{wheel.name} contains prohibited Vzor license metadata.")
            license_text = archive.read(license_paths[0]).decode("utf-8").replace("\r\n", "\n")
            if not license_text.startswith(
                "Vzor Community and SaaS License 1.0\n"
            ):
                raise SystemExit(f"{wheel.name} does not contain the Vzor license text.")
        print(f"Validated {wheel.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

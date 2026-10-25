# Licensing Vzor

Vzor v0.4.2 and future releases are distributed under the standard MIT
License. The repository's [LICENSE](../LICENSE) file is the governing text for
the current release.

The MIT License permits use, copying, modification, distribution,
sublicensing, and sale, subject to retaining its copyright and permission
notice. It includes the standard warranty and liability disclaimer.

## Historical releases

Relicensing v0.4.2 does not rewrite Git history or retroactively replace the
license bundled with an artifact that was already published. Each historical
source tag and wheel remains governed by the license text included in that
artifact:

- v0.4.1 was published under the Vzor Community and SaaS License 1.0.
- Earlier releases retain the license files shipped with their corresponding
  source tags and distribution artifacts.

Users should inspect the `LICENSE` file inside the exact historical artifact
they use. No historical tag or release is moved or replaced by v0.4.2.

## Third-party software

The MIT License covers Vzor's own source code. Vzor's dependencies remain
under their respective licenses; relicensing Vzor does not change those terms.
The project does not vendor third-party source code, and its dependency
versions remain recorded in `Cargo.lock` and `pyproject.toml`. Binary wheels
also include [third-party notices](../THIRD_PARTY_NOTICES.md) for their locked
Rust dependency graph.

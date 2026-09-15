# Release Checklist

Use this checklist for every new Vzor release. The historical
v0.4.0 checklist remains a record of that release.

1. Bump package and Cargo versions coherently.
2. Run `cargo fmt --check`, `cargo check --locked`, `cargo test --locked`, and
   `pytest -q`.
3. Run the full CI matrix.
4. Build and smoke-test the four supported wheels.
5. Inspect wheel licensing metadata and the packaged LICENSE.
6. Merge the approved release commit into `main`.
7. Create and push one immutable tag matching `v` plus the package version.
8. Approve the `pypi` environment in the release workflow if protection is
   enabled.
9. Confirm the release workflow validates artifacts and publishes to PyPI once.
10. Perform a remote clean-install smoke test with pandas and Polars.

Never overwrite PyPI artifacts, move a release tag, or publish from a branch.

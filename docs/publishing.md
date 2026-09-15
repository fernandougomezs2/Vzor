# Publishing Vzor to PyPI

Vzor publishes from GitHub Actions using PyPI Trusted Publishing. No PyPI API
token, password, or repository secret is used.

## Trusted Publisher configuration

The PyPI pending publisher for this repository must use these exact values:

- Project name: `Vzor` (PyPI normalizes this to `vzor`; installation is
  `pip install vzor`).
- Owner: `fernandougomezs2`.
- Repository: `Vzor`.
- Workflow filename: `release.yml`.
- Environment: `pypi`.

In GitHub, enable manual protection for the `pypi` environment with required
reviewers when that option is available. This must be configured by a repository
administrator; the workflow does not change environment protection itself.

## Before a release

1. Confirm package, Cargo, and runtime versions agree.
2. Run `cargo fmt --check`, `cargo check --locked`, `cargo test --locked`, and
   `pytest -q`.
3. Confirm CI and wheel workflows are green for CPython 3.12/3.13 on Windows
   and Linux x86-64.
4. Inspect wheel metadata: it must carry `License-File: LICENSE`, include the
   Vzor Community and SaaS License 1.0, and not describe Vzor as MIT or
   OSI-approved.
5. Merge the release preparation into `main`, then create and push exactly one
   matching tag, for example `v0.4.2` for package version `0.4.2`.

## How publication works

`release.yml` runs for pushed `v*` tags and can also be manually dispatched
only from a tag. Its first job rejects a branch ref or a tag that differs from
`v` plus the package version. It builds the four supported wheels, clean-tests
them with pandas and Polars, validates downloaded artifacts and README metadata
with Twine, then uses OIDC to publish once from the `pypi` environment.

For an already-existing valid tag, merge this workflow into the default branch,
open Actions → **Publish to PyPI**, choose that tag as the ref, and run the
workflow. The tag/version guard and the environment approval remain in effect.

## After publication

Use a separate clean machine or VM to run:

```bash
python3 -m venv vzor-test
source vzor-test/bin/activate
python -m pip install --upgrade pip
pip install vzor
python -c "import vzor; print(vzor.__version__)"
pip install "vzor[polars]"
```

Then run a small pandas `profile`/`inspect` smoke test and a Polars `profile`
smoke test.

PyPI distributions cannot be overwritten or deleted for reuse. If a published
version has a problem, do not retry an upload or move its tag: release a new
version after fixing and validating it.

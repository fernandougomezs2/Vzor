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

## Publish a historical tag

For a tag created before `release.yml` existed, run **Publish to PyPI** from
`main`; do not select the historical tag as the workflow ref. Enter the tag in
the required `release_tag` input, for example `v0.4.1`. The workflow verifies
that the remote tag exists, checks out that tag explicitly, validates its
version and license, and builds all wheels from that tag.

`dry_run` defaults to true. Use it first to validate the checkout, builds,
artifact metadata, and Twine checks without publishing. A real publication
requires setting `dry_run` to false and approving the `pypi` environment.

Because the manual run itself is from `main`, configure the GitHub `pypi`
environment's deployment branches and tags to allow both `main` and `v*`.
Keep required reviewers enabled. This is the safe option: the manual trigger,
required `release_tag`, tag/version guard, explicit tag checkout, artifact
checks, and environment approval prevent an accidental main build.

## Publish a new tag

Future tags that already contain `release.yml` continue to use the normal
`push` trigger for `v*`. In that mode the workflow resolves the release tag
from the push event, checks out that tag, and publishes only after the same
checks and environment approval.

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

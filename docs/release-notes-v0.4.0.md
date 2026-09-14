# Vzor 0.4.0 Release Notes

Vzor 0.4.0 closes the hardening, performance, backend, compatibility, wheel,
and release-readiness work tracked throughout v0.4. It remains a local,
deterministic data-trust layer for pandas and optional Polars DataFrames.

## Highlights

- CPython 3.12 and 3.13 support is defined for Windows and Linux x86-64.
- pandas remains required at `>=2.2.3,<4`; the direct Polars backend remains an
  optional `vzor[polars]` extra at `>=1.0,<2`.
- CI covers both Python versions and platforms, pandas/Polars minimum and
  current lanes, mixed backends, clean installs, source builds, CLI,
  persistence, and standalone HTML reports.
- Wheels are built per CPython ABI for Windows and manylinux 2.28 x86-64 and
  are smoke-tested in clean virtual environments. No ABI3 claim is made.
- The Rust core now has fixed-seed property-based hardening coverage for
  profiling, numeric statistics, comparison, drift, validation, ordering,
  malformed inputs, and persistence parsing.

## Compatibility promises retained

The existing public API, deterministic ordering, report repr/HTML behavior,
CLI exit codes, `output_version = 1`, and `format_version = 1` are unchanged.
Vzor does not clean, transform, infer business rules, or provide a public data
ingestion API.

## Deliberately not included

This release does not add macOS, ARM, musl, Python 3.14, ABI3, Excel/Power BI
exports, data contracts, join analysis, a Git tag, a GitHub Release, or PyPI
publication. Those require separate scope and evidence.

The completed CI run identifiers, exact wheel tags, and artifact validation are
recorded in the [v0.4.0 release checklist](release-checklist-v0.4.0.md): CI
run 34892189850 passed 14/14 and Wheels run 34892228846 passed 4/4. All four
downloaded artifacts were inspected and their clean-venv smoke profiles passed.

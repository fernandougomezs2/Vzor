# Vzor v0.4.0 Release Checklist

## Release identity

- [x] Package metadata and Rust core are `0.4.0`.
- [x] `output_version = 1` remains unchanged.
- [x] Suggested-schema `format_version = 1` remains unchanged.
- [x] Python support remains CPython `>=3.12,<3.14`.
- [x] Runtime requirements remain `pandas>=2.2.3,<4` and optional
  `polars>=1.0,<2`.
- [x] No public API, CLI command, exit code, report model, or persistence
  contract was added or removed.

## Hardening gate

- [x] Eight fixed-seed, bounded Rust property targets run through
  `cargo test --locked` without PyO3/Python/filesystem/network calls.
- [x] Rust core tests: 141 passed locally.
- [x] Public Python tests: 344 passed locally, 1 Windows-inapplicable POSIX
  permission check skipped.
- [x] `cargo fmt --check`, `cargo check --locked`, and strict Clippy are clean.
- [x] `maturin develop --release --locked` builds the local CPython 3.12
  extension.
- [x] Public edge coverage includes floats, integer limits, strings, Unicode,
  datetime/categorical/empty inputs, duplicate names, persistence errors, CLI
  errors, HTML escaping and deterministic reports.

## Remote compatibility and wheel gate

- [x] Windows x86-64 / CPython 3.12 core and wheel smoke.
- [x] Windows x86-64 / CPython 3.13 core and wheel smoke.
- [x] Linux x86-64 / CPython 3.12 core and wheel smoke.
- [x] Linux x86-64 / CPython 3.13 core and wheel smoke.
- [x] pandas minimum/current, Polars minimum/current, mixed backend and fresh
  wheel installs with and without Polars.
- [x] Download and inspect all four remote wheels; perform their clean-venv
  smoke profiles.

The exact-commit remote gate completed successfully: [CI run 34892189850](https://github.com/fernandougomezs2/Vzor/actions/runs/34892189850)
passed 14/14 jobs, and [Wheels run 34892228846](https://github.com/fernandougomezs2/Vzor/actions/runs/34892228846)
passed 4/4. CI covers Windows/Linux x86-64 with CPython 3.12/3.13, pandas
2.2.3 and 3.0.5, Polars 1.0.0 and latest `<2`, mixed backend, and fresh
installs with and without Polars.

| Platform | Wheel | Wheel bytes | Artifact bytes | Clean-venv smoke |
| --- | --- | ---: | ---: | --- |
| Linux x86-64 / 3.12 | `vzor-0.4.0-cp312-cp312-manylinux_2_28_x86_64.whl` | 433,100 | 431,036 | passed |
| Linux x86-64 / 3.13 | `vzor-0.4.0-cp313-cp313-manylinux_2_28_x86_64.whl` | 432,675 | 430,651 | passed |
| Windows x86-64 / 3.12 | `vzor-0.4.0-cp312-cp312-win_amd64.whl` | 282,764 | 280,855 | passed |
| Windows x86-64 / 3.13 | `vzor-0.4.0-cp313-cp313-win_amd64.whl` | 282,284 | 280,355 | passed |

Each downloaded artifact contained one 24-entry wheel. Inspection found no
build target, virtual environment, cache, benchmark, or dataset entries.

## Publication guard

- [x] No Git tag was created.
- [x] No GitHub Release was created.
- [x] No package was published to PyPI.
- [x] CI workflows upload artifacts only and have no publishing step.

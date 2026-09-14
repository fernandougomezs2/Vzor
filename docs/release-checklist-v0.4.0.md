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

- [ ] Windows x86-64 / CPython 3.12 core and wheel smoke.
- [ ] Windows x86-64 / CPython 3.13 core and wheel smoke.
- [ ] Linux x86-64 / CPython 3.12 core and wheel smoke.
- [ ] Linux x86-64 / CPython 3.13 core and wheel smoke.
- [ ] pandas minimum/current, Polars minimum/current, mixed backend and fresh
  wheel installs with and without Polars.
- [ ] Download and inspect all four remote wheels; perform their clean-venv
  smoke profiles.

The remaining boxes are an external gate, not a known code failure. They are
completed only with successful GitHub Actions evidence for this exact commit.

## Publication guard

- [x] No Git tag was created.
- [x] No GitHub Release was created.
- [x] No package was published to PyPI.
- [x] CI workflows upload artifacts only and have no publishing step.

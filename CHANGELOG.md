# Changelog

## 0.4.0

### Changed

- v0.4.7 adds fixed-seed Rust property-based hardening targets and public edge
  regressions for extreme numeric inputs, HTML escaping, malformed persistence,
  CLI errors, and deterministic mixed-type reports. It also removes a Clippy
  redundant PyO3 borrow without changing behavior. The test-only `proptest`
  dependency is not linked into the extension or published wheels.
- v0.4.6 formalizes the CPython 3.12/3.13, Windows/Linux x86-64, pandas, and
  optional Polars compatibility policy in package metadata and documentation.
  It adds non-publishing CI and wheel workflows, fresh-install smoke coverage,
  and path/CLI/HTML/persistence compatibility regression coverage. Base-only
  installs now preserve the existing `TypeError` contract for unsupported
  inputs when the optional Polars package is absent. The final remote matrix
  passed on Windows/Linux and CPython 3.12/3.13, including pandas and Polars
  minimum/current lanes, fresh installs, and binary wheel smoke tests.
- v0.4.5 adds local-only large-data benchmark guardrails and memory metadata,
  including available physical memory and peak delta above the loaded frame.
- v0.4.4 sends safe non-null Polars numeric and Boolean series through the
  existing raw typed PyO3 path, avoiding its per-value Python normalizer while
  retaining checked fallback semantics for every other dtype.
- v0.4.3 adds an optional direct Polars DataFrame backend through private
  normalization, including mixed pandas/Polars compare and schema drift.
- v0.4.2-E completes the hardening audit and reruns the local final benchmark
  matrix. It records measured performance and memory changes without changing
  runtime behavior, public contracts, dependencies, or package versions.
- v0.4.2-D shares factual column traversal internally and lets schema drift
  avoid profile, observed-schema, and comparison-snapshot work it does not
  expose, while preserving structural error and ordering contracts.
- v0.4.2-C makes exact unique counting borrow input string slices while it
  profiles, removing the per-distinct-string `HashSet<String>` clone. Observed
  values retain their existing bounded, owned output behavior.
- v0.4.2-B removes the private whole-column normalized Python list and PyO3
  `Vec<Py<PyAny>>` materialization between pandas and Rust. It preserves the
  existing dtype, null, overflow, error, API, and output contracts.
- v0.4.2-A makes Rust profiling borrow `DatasetInput` for the observed,
  suggested, and inspection pipelines, eliminating their redundant deep input
  clones without changing public behavior.

### Added

- Local-only, reproducible benchmark and memory-inventory infrastructure for
  the v0.4.1 measurement subphase. It is outside Vzor's runtime and does not
  change package or output-format versions.

## 0.3.2

### Changed

- High-level report representations are compact structural summaries with
  five-item previews. Full report data, detailed individual model `repr`,
  `human_summary`, and deterministic HTML exports are unchanged.

## 0.3.1

### Added

- Complete, deterministic standalone HTML export through `report.to_html(path)`
  for all four public report types.

### Changed

- Plain-text representations show at most five items per collection while the
  underlying reports and HTML output retain every item.

## 0.3.0

### Added

- Python reporting API and deterministic human-readable summaries.
- Convenience properties for reports and existing exact column lookup.
- `AGENTS.md`, user documentation, and a self-contained workflow example.
- A formal MIT license.

### Changed

- CLI help and operational error messages are clearer without changing JSON or
  exit-code contracts.
- Package metadata now includes the README and license file.

### Fixed

- Package version metadata is exposed as `vzor.__version__`.
- The Rust version function now derives its value from the Cargo manifest.

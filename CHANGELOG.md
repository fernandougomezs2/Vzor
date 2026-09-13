# Changelog

## Unreleased

### Changed

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

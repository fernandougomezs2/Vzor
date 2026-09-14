mod bindings;
pub mod comparison;
pub mod persistence;
pub mod profiling;
pub mod schema;
pub mod schema_drift;
pub mod validation;

#[cfg(test)]
mod hardening_tests;

use pyo3::prelude::*;

#[pyfunction]
fn version() -> &'static str {
    env!("CARGO_PKG_VERSION")
}

#[pymodule]
fn _vzor_core(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(version, m)?)?;
    bindings::register(m)?;
    Ok(())
}

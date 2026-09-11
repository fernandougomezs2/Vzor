/// Temporary internal representation of values used by the profiling core.
///
/// This is intentionally independent of pandas, NumPy and Arrow. It is not
/// the definitive transport representation for the Python integration.
#[derive(Debug, Clone, PartialEq)]
pub enum ProfileValue {
    Null,
    Integer(i64),
    Float(f64),
    Boolean(bool),
    String(String),
}

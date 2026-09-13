mod engine;
mod models;

pub use engine::compare_observed_schemas;
pub(crate) use engine::visit_comparison_columns;
pub use models::{ColumnComparison, ComparisonChangeCode, ComparisonResult, ComparisonStatus};

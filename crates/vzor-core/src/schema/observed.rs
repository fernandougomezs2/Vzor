use crate::profiling::LogicalType;

/// Numeric range observed in a dataset, not a business constraint.
#[derive(Debug, Clone, PartialEq)]
pub struct ObservedRange {
    pub min: f64,
    pub max: f64,
}

impl ObservedRange {
    pub fn new(min: f64, max: f64) -> Self {
        Self { min, max }
    }
}

/// Low-cardinality values retained as observations in an observed schema.
///
/// This is distinct from `ProfileValue`, which is temporary profiling input.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum ObservedValue {
    String(String),
    Boolean(bool),
}

/// Observations about one column, without any business constraints.
#[derive(Debug, Clone, PartialEq)]
pub struct ObservedColumnSchema {
    pub name: String,
    pub logical_type: LogicalType,
    pub observed_nullable: bool,
    pub observed_unique_count: usize,
    pub observed_range: Option<ObservedRange>,
    pub observed_values: Option<Vec<ObservedValue>>,
}

impl ObservedColumnSchema {
    pub fn new(
        name: String,
        logical_type: LogicalType,
        observed_nullable: bool,
        observed_unique_count: usize,
        observed_range: Option<ObservedRange>,
        observed_values: Option<Vec<ObservedValue>>,
    ) -> Self {
        Self {
            name,
            logical_type,
            observed_nullable,
            observed_unique_count,
            observed_range,
            observed_values,
        }
    }
}

/// Structural snapshot of a dataset observed by Vzor, not a data contract.
#[derive(Debug, Clone, PartialEq)]
pub struct ObservedDatasetSchema {
    pub row_count: usize,
    pub columns: Vec<ObservedColumnSchema>,
}

impl ObservedDatasetSchema {
    pub fn new(row_count: usize, columns: Vec<ObservedColumnSchema>) -> Self {
        Self { row_count, columns }
    }

    /// Returns the number of columns derived from the stored collection.
    pub fn column_count(&self) -> usize {
        self.columns.len()
    }

    /// Returns an observed column by its exact name.
    pub fn column(&self, name: &str) -> Option<&ObservedColumnSchema> {
        self.columns.iter().find(|column| column.name == name)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn column(
        name: &str,
        logical_type: LogicalType,
        observed_nullable: bool,
        observed_unique_count: usize,
    ) -> ObservedColumnSchema {
        ObservedColumnSchema::new(
            name.to_string(),
            logical_type,
            observed_nullable,
            observed_unique_count,
            None,
            None,
        )
    }

    #[test]
    fn observed_range_preserves_min_and_max() {
        let range = ObservedRange::new(-10.5, 99.0);

        assert_eq!(range.min, -10.5);
        assert_eq!(range.max, 99.0);
    }

    #[test]
    fn numeric_column_schema_preserves_observations_without_values() {
        let range = ObservedRange::new(10.0, 500.0);
        let schema = ObservedColumnSchema::new(
            "sales".to_string(),
            LogicalType::Float,
            false,
            42,
            Some(range.clone()),
            None,
        );

        assert_eq!(schema.name, "sales");
        assert_eq!(schema.logical_type, LogicalType::Float);
        assert!(!schema.observed_nullable);
        assert_eq!(schema.observed_unique_count, 42);
        assert_eq!(schema.observed_range, Some(range));
        assert_eq!(schema.observed_values, None);
    }

    #[test]
    fn categorical_column_schema_keeps_observed_values_and_nullability() {
        let values = vec![
            ObservedValue::String("North".to_string()),
            ObservedValue::String("South".to_string()),
        ];
        let schema = ObservedColumnSchema::new(
            "region".to_string(),
            LogicalType::Categorical,
            true,
            2,
            None,
            Some(values.clone()),
        );

        assert!(schema.observed_nullable);
        assert_eq!(schema.observed_unique_count, 2);
        assert_eq!(schema.observed_range, None);
        assert_eq!(schema.observed_values, Some(values));
    }

    #[test]
    fn unknown_logical_type_is_supported() {
        let schema = column("empty_object", LogicalType::Unknown, true, 0);

        assert_eq!(schema.logical_type, LogicalType::Unknown);
        assert!(schema.observed_nullable);
        assert_eq!(schema.observed_unique_count, 0);
    }

    #[test]
    fn empty_observed_dataset_schema_is_supported() {
        let schema = ObservedDatasetSchema::new(0, Vec::new());

        assert_eq!(schema.row_count, 0);
        assert_eq!(schema.column_count(), 0);
        assert!(schema.columns.is_empty());
        assert_eq!(schema.column("missing"), None);
    }

    #[test]
    fn dataset_schema_preserves_order_and_supports_column_lookup() {
        let schema = ObservedDatasetSchema::new(
            3,
            vec![
                column("id", LogicalType::Integer, false, 3),
                ObservedColumnSchema::new(
                    "active".to_string(),
                    LogicalType::Boolean,
                    false,
                    2,
                    None,
                    Some(vec![
                        ObservedValue::Boolean(true),
                        ObservedValue::Boolean(false),
                    ]),
                ),
                column("region", LogicalType::Categorical, true, 2),
            ],
        );

        assert_eq!(schema.row_count, 3);
        assert_eq!(schema.column_count(), 3);
        assert_eq!(schema.columns[0].name, "id");
        assert_eq!(schema.columns[1].name, "active");
        assert_eq!(schema.columns[2].name, "region");
        assert_eq!(
            schema.column("active").map(|column| &column.logical_type),
            Some(&LogicalType::Boolean)
        );
        assert_eq!(schema.column("missing"), None);
    }
}

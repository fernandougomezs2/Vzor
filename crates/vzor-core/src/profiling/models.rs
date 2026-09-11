/// Logical meaning inferred for a column, independent of its physical dtype.
#[derive(Debug, Clone, PartialEq, Eq, serde::Serialize, serde::Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum LogicalType {
    Integer,
    Float,
    Boolean,
    String,
    Datetime,
    Categorical,
    Unknown,
}

/// Basic statistics calculated from finite, non-null numeric values.
#[derive(Debug, Clone, PartialEq)]
pub struct NumericStats {
    pub min: f64,
    pub max: f64,
    pub mean: f64,
    pub median: f64,
    pub p25: f64,
    pub p50: f64,
    pub p75: f64,
}

/// Profiling result for one column.
#[derive(Debug, Clone, PartialEq)]
pub struct ColumnProfile {
    pub name: String,
    pub logical_type: LogicalType,
    pub count: usize,
    pub null_count: usize,
    pub unique_count: usize,
    pub numeric_stats: Option<NumericStats>,
}

impl ColumnProfile {
    pub fn new(
        name: String,
        logical_type: LogicalType,
        count: usize,
        null_count: usize,
        unique_count: usize,
        numeric_stats: Option<NumericStats>,
    ) -> Self {
        Self {
            name,
            logical_type,
            count,
            null_count,
            unique_count,
            numeric_stats,
        }
    }
}

/// Profiling results for a complete dataset.
#[derive(Debug, Clone, PartialEq)]
pub struct DatasetProfile {
    pub row_count: usize,
    pub columns: Vec<ColumnProfile>,
}

impl DatasetProfile {
    pub fn new(row_count: usize, columns: Vec<ColumnProfile>) -> Self {
        Self { row_count, columns }
    }

    /// Returns the number of columns derived from the stored collection.
    pub fn column_count(&self) -> usize {
        self.columns.len()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn logical_type_can_be_created_and_compared() {
        assert_eq!(LogicalType::Integer, LogicalType::Integer);
        assert_ne!(LogicalType::Integer, LogicalType::String);
        assert_eq!(LogicalType::Datetime, LogicalType::Datetime);
    }

    #[test]
    fn column_profile_preserves_its_fields() {
        let profile = ColumnProfile::new(
            "customer_id".to_string(),
            LogicalType::Integer,
            100,
            2,
            98,
            None,
        );

        assert_eq!(profile.name, "customer_id");
        assert_eq!(profile.logical_type, LogicalType::Integer);
        assert_eq!(profile.count, 100);
        assert_eq!(profile.null_count, 2);
        assert_eq!(profile.unique_count, 98);
        assert_eq!(profile.numeric_stats, None);
    }

    #[test]
    fn dataset_profile_preserves_rows_and_columns() {
        let columns = vec![ColumnProfile::new(
            "active".to_string(),
            LogicalType::Boolean,
            3,
            0,
            2,
            None,
        )];
        let profile = DatasetProfile::new(3, columns.clone());

        assert_eq!(profile.row_count, 3);
        assert_eq!(profile.columns, columns);
        assert_eq!(profile.column_count(), 1);
    }

    #[test]
    fn empty_dataset_profile_is_supported() {
        let profile = DatasetProfile::new(0, Vec::new());

        assert_eq!(profile.row_count, 0);
        assert!(profile.columns.is_empty());
        assert_eq!(profile.column_count(), 0);
    }
}

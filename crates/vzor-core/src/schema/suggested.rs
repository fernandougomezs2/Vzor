use crate::profiling::LogicalType;

/// A value Vzor suggests as permitted by a column's proposed constraint.
#[derive(Debug, Clone, PartialEq, Eq, serde::Serialize, serde::Deserialize)]
#[serde(tag = "kind", content = "value", rename_all = "snake_case")]
pub enum SuggestedValue {
    String(String),
    Boolean(bool),
}

/// A numeric range proposed as a constraint, rather than values observed in data.
#[derive(Debug, Clone, PartialEq, serde::Serialize, serde::Deserialize)]
pub struct SuggestedNumericRange {
    pub min: Option<f64>,
    pub max: Option<f64>,
}

impl SuggestedNumericRange {
    pub fn new(min: Option<f64>, max: Option<f64>) -> Self {
        Self { min, max }
    }
}

/// Constraints proposed by Vzor for a column, not an approved data contract.
#[derive(Debug, Clone, PartialEq, serde::Serialize, serde::Deserialize)]
pub struct SuggestedConstraints {
    pub numeric_range: Option<SuggestedNumericRange>,
    pub allowed_values: Option<Vec<SuggestedValue>>,
}

impl SuggestedConstraints {
    pub fn new(
        numeric_range: Option<SuggestedNumericRange>,
        allowed_values: Option<Vec<SuggestedValue>>,
    ) -> Self {
        Self {
            numeric_range,
            allowed_values,
        }
    }
}

/// Suggested rules for one column, not observations or an approved contract.
#[derive(Debug, Clone, PartialEq, serde::Serialize, serde::Deserialize)]
pub struct SuggestedColumnSchema {
    pub name: String,
    pub logical_type: LogicalType,
    pub nullable: bool,
    pub constraints: SuggestedConstraints,
}

impl SuggestedColumnSchema {
    pub fn new(
        name: String,
        logical_type: LogicalType,
        nullable: bool,
        constraints: SuggestedConstraints,
    ) -> Self {
        Self {
            name,
            logical_type,
            nullable,
            constraints,
        }
    }
}

/// A schema proposed by Vzor for a dataset, not an approved data contract.
#[derive(Debug, Clone, PartialEq, serde::Serialize, serde::Deserialize)]
pub struct SuggestedDatasetSchema {
    pub columns: Vec<SuggestedColumnSchema>,
}

impl SuggestedDatasetSchema {
    pub fn new(columns: Vec<SuggestedColumnSchema>) -> Self {
        Self { columns }
    }

    /// Returns the number of columns derived from the stored collection.
    pub fn column_count(&self) -> usize {
        self.columns.len()
    }

    /// Returns a suggested column by its exact name.
    pub fn column(&self, name: &str) -> Option<&SuggestedColumnSchema> {
        self.columns.iter().find(|column| column.name == name)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn empty_constraints() -> SuggestedConstraints {
        SuggestedConstraints::new(None, None)
    }

    fn column(name: &str, logical_type: LogicalType, nullable: bool) -> SuggestedColumnSchema {
        SuggestedColumnSchema::new(
            name.to_string(),
            logical_type,
            nullable,
            empty_constraints(),
        )
    }

    #[test]
    fn suggested_numeric_range_supports_all_limit_combinations() {
        assert_eq!(
            SuggestedNumericRange::new(Some(1.0), Some(10.0)),
            SuggestedNumericRange {
                min: Some(1.0),
                max: Some(10.0),
            }
        );
        assert_eq!(
            SuggestedNumericRange::new(Some(0.0), None),
            SuggestedNumericRange {
                min: Some(0.0),
                max: None,
            }
        );
        assert_eq!(
            SuggestedNumericRange::new(None, Some(100.0)),
            SuggestedNumericRange {
                min: None,
                max: Some(100.0),
            }
        );
        assert_eq!(
            SuggestedNumericRange::new(None, None),
            SuggestedNumericRange {
                min: None,
                max: None,
            }
        );
    }

    #[test]
    fn suggested_values_support_strings_and_booleans() {
        assert_eq!(
            SuggestedValue::String("North".to_string()),
            SuggestedValue::String("North".to_string())
        );
        assert_eq!(SuggestedValue::Boolean(true), SuggestedValue::Boolean(true));
    }

    #[test]
    fn suggested_constraints_may_be_empty_or_contain_each_constraint_kind() {
        assert_eq!(empty_constraints().numeric_range, None);
        assert_eq!(empty_constraints().allowed_values, None);

        let range = SuggestedNumericRange::new(Some(0.0), None);
        let ranged = SuggestedConstraints::new(Some(range.clone()), None);
        assert_eq!(ranged.numeric_range, Some(range));
        assert_eq!(ranged.allowed_values, None);

        let values = vec![
            SuggestedValue::String("North".to_string()),
            SuggestedValue::String("South".to_string()),
        ];
        let enumerated = SuggestedConstraints::new(None, Some(values.clone()));
        assert_eq!(enumerated.numeric_range, None);
        assert_eq!(enumerated.allowed_values, Some(values));
    }

    #[test]
    fn suggested_columns_support_every_logical_type_and_nullability() {
        let integer = SuggestedColumnSchema::new(
            "id".to_string(),
            LogicalType::Integer,
            false,
            SuggestedConstraints::new(
                Some(SuggestedNumericRange::new(Some(1.0), Some(999.0))),
                None,
            ),
        );
        let float = column("amount", LogicalType::Float, false);
        let string = column("label", LogicalType::String, true);
        let boolean = SuggestedColumnSchema::new(
            "active".to_string(),
            LogicalType::Boolean,
            false,
            SuggestedConstraints::new(
                None,
                Some(vec![
                    SuggestedValue::Boolean(true),
                    SuggestedValue::Boolean(false),
                ]),
            ),
        );
        let categorical = column("region", LogicalType::Categorical, true);
        let datetime = column("created_at", LogicalType::Datetime, false);
        let unknown = column("unresolved", LogicalType::Unknown, true);

        assert_eq!(integer.logical_type, LogicalType::Integer);
        assert!(!integer.nullable);
        assert_eq!(float.logical_type, LogicalType::Float);
        assert_eq!(string.logical_type, LogicalType::String);
        assert!(string.nullable);
        assert_eq!(boolean.logical_type, LogicalType::Boolean);
        assert_eq!(categorical.logical_type, LogicalType::Categorical);
        assert_eq!(datetime.logical_type, LogicalType::Datetime);
        assert_eq!(unknown.logical_type, LogicalType::Unknown);
    }

    #[test]
    fn suggested_dataset_supports_empty_schemas_and_preserves_column_order() {
        let empty = SuggestedDatasetSchema::new(Vec::new());
        assert_eq!(empty.column_count(), 0);
        assert!(empty.columns.is_empty());
        assert_eq!(empty.column("missing"), None);

        let schema = SuggestedDatasetSchema::new(vec![
            column("id", LogicalType::Integer, false),
            column("region", LogicalType::Categorical, true),
            column("active", LogicalType::Boolean, false),
        ]);

        assert_eq!(schema.column_count(), schema.columns.len());
        assert_eq!(schema.columns[0].name, "id");
        assert_eq!(schema.columns[1].name, "region");
        assert_eq!(schema.columns[2].name, "active");
        assert_eq!(
            schema.column("region").map(|column| &column.logical_type),
            Some(&LogicalType::Categorical)
        );
        assert_eq!(schema.column("missing"), None);
        assert_eq!(schema.column_count(), 3);
    }
}

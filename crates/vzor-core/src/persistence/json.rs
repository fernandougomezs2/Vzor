use std::{fs, path::Path};

use crate::schema::SuggestedDatasetSchema;

use super::{PersistedSuggestedSchema, PersistenceError, SUGGESTED_SCHEMA_FORMAT_VERSION};

/// Converts a suggested schema to stable, pretty, versioned JSON.
///
/// JSON has no lossless representation for non-finite floating-point values,
/// so schemas containing them return a serialization error.
pub fn serialize_suggested_schema(
    schema: &SuggestedDatasetSchema,
) -> Result<String, PersistenceError> {
    validate_finite_ranges(schema)?;
    let persisted = PersistedSuggestedSchema {
        format_version: SUGGESTED_SCHEMA_FORMAT_VERSION,
        schema: schema.clone(),
    };

    serde_json::to_string_pretty(&persisted)
        .map_err(|error| PersistenceError::Serialization(error.to_string()))
}

/// Reconstructs a suggested schema from versioned JSON and validates its format
/// version. Unknown JSON fields are tolerated for forward compatibility.
pub fn deserialize_suggested_schema(
    content: &str,
) -> Result<SuggestedDatasetSchema, PersistenceError> {
    let persisted = serde_json::from_str::<PersistedSuggestedSchema>(content)
        .map_err(|error| PersistenceError::Deserialization(error.to_string()))?;

    if persisted.format_version != SUGGESTED_SCHEMA_FORMAT_VERSION {
        return Err(PersistenceError::UnsupportedFormatVersion(
            persisted.format_version,
        ));
    }

    Ok(persisted.schema)
}

/// Writes a complete UTF-8, pretty JSON suggested-schema file.
pub fn save_suggested_schema(
    schema: &SuggestedDatasetSchema,
    path: impl AsRef<Path>,
) -> Result<(), PersistenceError> {
    let content = serialize_suggested_schema(schema)?;
    fs::write(path, content).map_err(|error| PersistenceError::Io(error.to_string()))
}

/// Reads and deserializes a versioned suggested-schema JSON file.
pub fn load_suggested_schema(
    path: impl AsRef<Path>,
) -> Result<SuggestedDatasetSchema, PersistenceError> {
    let content =
        fs::read_to_string(path).map_err(|error| PersistenceError::Io(error.to_string()))?;

    deserialize_suggested_schema(&content)
}

fn validate_finite_ranges(schema: &SuggestedDatasetSchema) -> Result<(), PersistenceError> {
    for column in &schema.columns {
        if let Some(range) = column.constraints.numeric_range.as_ref() {
            if range.min.is_some_and(|value| !value.is_finite())
                || range.max.is_some_and(|value| !value.is_finite())
            {
                return Err(PersistenceError::Serialization(format!(
                    "numeric range for column `{}` contains a non-finite value",
                    column.name
                )));
            }
        }
    }

    Ok(())
}

#[cfg(test)]
mod tests {
    use std::{
        fs,
        sync::atomic::{AtomicUsize, Ordering},
    };

    use super::*;
    use crate::{
        profiling::LogicalType,
        schema::{
            SuggestedColumnSchema, SuggestedConstraints, SuggestedNumericRange, SuggestedValue,
        },
    };

    static TEMP_FILE_COUNTER: AtomicUsize = AtomicUsize::new(0);

    fn constraints(
        numeric_range: Option<SuggestedNumericRange>,
        allowed_values: Option<Vec<SuggestedValue>>,
    ) -> SuggestedConstraints {
        SuggestedConstraints::new(numeric_range, allowed_values)
    }

    fn column(
        name: &str,
        logical_type: LogicalType,
        nullable: bool,
        constraints: SuggestedConstraints,
    ) -> SuggestedColumnSchema {
        SuggestedColumnSchema::new(name.to_string(), logical_type, nullable, constraints)
    }

    fn complex_schema() -> SuggestedDatasetSchema {
        SuggestedDatasetSchema::new(vec![
            column(
                "c",
                LogicalType::Integer,
                false,
                constraints(
                    Some(SuggestedNumericRange::new(Some(0.0), Some(100.0))),
                    None,
                ),
            ),
            column(
                "a",
                LogicalType::Float,
                true,
                constraints(Some(SuggestedNumericRange::new(Some(-1.5), None)), None),
            ),
            column(
                "b",
                LogicalType::String,
                false,
                constraints(
                    None,
                    Some(vec![
                        SuggestedValue::String("Z".to_string()),
                        SuggestedValue::String("A".to_string()),
                        SuggestedValue::String("M".to_string()),
                    ]),
                ),
            ),
            column(
                "active",
                LogicalType::Boolean,
                true,
                constraints(
                    None,
                    Some(vec![
                        SuggestedValue::Boolean(true),
                        SuggestedValue::Boolean(false),
                    ]),
                ),
            ),
            column(
                "created_at",
                LogicalType::Datetime,
                false,
                constraints(Some(SuggestedNumericRange::new(None, Some(9.0))), None),
            ),
            column(
                "Región",
                LogicalType::Categorical,
                true,
                constraints(
                    None,
                    Some(vec![
                        SuggestedValue::String("México".to_string()),
                        SuggestedValue::Boolean(true),
                        SuggestedValue::String("Niñez".to_string()),
                    ]),
                ),
            ),
            column(
                "unresolved",
                LogicalType::Unknown,
                true,
                constraints(None, None),
            ),
        ])
    }

    fn temporary_path(label: &str) -> std::path::PathBuf {
        let sequence = TEMP_FILE_COUNTER.fetch_add(1, Ordering::Relaxed);
        std::env::temp_dir().join(format!(
            "vzor_persistence_{label}_{}_{}.json",
            std::process::id(),
            sequence,
        ))
    }

    #[test]
    fn serialization_is_pretty_deterministic_and_preserves_the_schema() {
        let schema = complex_schema();
        let original = schema.clone();

        let first = serialize_suggested_schema(&schema).expect("schema serializes");
        let second = serialize_suggested_schema(&schema).expect("schema serializes");

        assert_eq!(schema, original);
        assert_eq!(first, second);
        assert!(first.contains('\n'));
        assert!(first.contains("\"format_version\": 1"));
        assert!(first.contains("\"schema\""));
        assert!(first.contains("\"columns\""));
        assert!(first.contains("\"logical_type\": \"integer\""));
        assert!(first.contains("\"nullable\""));
        assert!(first.contains("\"constraints\""));
        assert!(first.contains("\"kind\": \"string\""));
        assert!(first.contains("\"kind\": \"boolean\""));
        assert_eq!(deserialize_suggested_schema(&first), Ok(schema));
    }

    #[test]
    fn round_trip_preserves_ranges_values_orders_utf8_and_empty_schema() {
        let schema = complex_schema();
        let restored = deserialize_suggested_schema(
            &serialize_suggested_schema(&schema).expect("schema serializes"),
        )
        .expect("schema deserializes");

        assert_eq!(restored, schema);
        assert_eq!(
            restored
                .columns
                .iter()
                .map(|column| &column.name)
                .collect::<Vec<_>>(),
            vec![
                "c",
                "a",
                "b",
                "active",
                "created_at",
                "Región",
                "unresolved"
            ]
        );
        assert_eq!(
            restored.columns[2].constraints.allowed_values,
            Some(vec![
                SuggestedValue::String("Z".to_string()),
                SuggestedValue::String("A".to_string()),
                SuggestedValue::String("M".to_string()),
            ])
        );
        assert_eq!(
            deserialize_suggested_schema(
                &serialize_suggested_schema(&SuggestedDatasetSchema::new(vec![]))
                    .expect("empty schema serializes"),
            ),
            Ok(SuggestedDatasetSchema::new(vec![]))
        );
    }

    #[test]
    fn file_round_trip_and_overwrite_preserve_the_latest_schema() {
        let path = temporary_path("round_trip");
        let first = SuggestedDatasetSchema::new(vec![column(
            "first",
            LogicalType::Integer,
            false,
            constraints(None, None),
        )]);
        let second = complex_schema();

        save_suggested_schema(&first, &path).expect("first schema saves");
        save_suggested_schema(&second, &path).expect("second schema overwrites");

        assert_eq!(load_suggested_schema(&path), Ok(second));
        fs::remove_file(path).expect("temporary schema is removed");
    }

    #[test]
    fn expected_deserialization_errors_are_structured() {
        assert!(matches!(
            deserialize_suggested_schema("not-json"),
            Err(PersistenceError::Deserialization(_))
        ));
        assert!(matches!(
            deserialize_suggested_schema(r#"{"schema":{"columns":[]}}"#),
            Err(PersistenceError::Deserialization(_))
        ));
        assert!(matches!(
            deserialize_suggested_schema(r#"{"format_version":1}"#),
            Err(PersistenceError::Deserialization(_))
        ));
        assert!(matches!(
            deserialize_suggested_schema(
                r#"{"format_version":1,"schema":{"columns":[{"name":"id","logical_type":"integer","nullable":"yes","constraints":{"numeric_range":null,"allowed_values":null}}]}}"#
            ),
            Err(PersistenceError::Deserialization(_))
        ));
    }

    #[test]
    fn unsupported_version_and_unknown_fields_follow_the_format_policy() {
        assert_eq!(
            deserialize_suggested_schema(r#"{"format_version":999,"schema":{"columns":[]}}"#),
            Err(PersistenceError::UnsupportedFormatVersion(999))
        );
        assert_eq!(
            deserialize_suggested_schema(
                r#"{"format_version":1,"future_metadata":{"source":"future"},"schema":{"columns":[]}}"#
            ),
            Ok(SuggestedDatasetSchema::new(vec![]))
        );
    }

    #[test]
    fn missing_files_and_non_finite_ranges_return_errors() {
        let missing = temporary_path("missing");
        assert!(matches!(
            load_suggested_schema(missing),
            Err(PersistenceError::Io(_))
        ));

        let non_finite = SuggestedDatasetSchema::new(vec![column(
            "value",
            LogicalType::Float,
            false,
            constraints(Some(SuggestedNumericRange::new(Some(f64::NAN), None)), None),
        )]);
        assert!(matches!(
            serialize_suggested_schema(&non_finite),
            Err(PersistenceError::Serialization(_))
        ));
    }
}

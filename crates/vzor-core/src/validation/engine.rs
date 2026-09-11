use std::collections::{HashMap, HashSet};

use crate::{
    profiling::{ColumnInput, DatasetInput, LogicalType, ProfileValue},
    schema::{
        SuggestedColumnSchema, SuggestedDatasetSchema, SuggestedNumericRange, SuggestedValue,
    },
};

use super::{
    ValidationCode, ValidationIssue, ValidationResult, ValidationSeverity, ValidationValue,
};

/// Validates normalized dataset input against a suggested schema.
///
/// Dataset violations become structured issues rather than execution errors. The
/// engine is deterministic, works only with normalized Rust structures, and
/// does not recompute profiling information. Suggested schemas do not yet have
/// approved-contract semantics.
pub fn validate_dataset(input: &DatasetInput, schema: &SuggestedDatasetSchema) -> ValidationResult {
    let input_by_name = input
        .columns
        .iter()
        .map(|column| (column.name.as_str(), column))
        .collect::<HashMap<_, _>>();
    let schema_names = schema
        .columns
        .iter()
        .map(|column| column.name.as_str())
        .collect::<HashSet<_>>();
    let mut issues = Vec::new();

    // Schema order is the stable ordering policy for expected columns and
    // their rules. Missing columns and type mismatches stop validation of the
    // affected column to avoid meaningless cascades.
    for schema_column in &schema.columns {
        match input_by_name.get(schema_column.name.as_str()) {
            None => issues.push(issue(
                ValidationCode::MissingColumn,
                &schema_column.name,
                None,
                None,
            )),
            Some(input_column) => validate_column(input_column, schema_column, &mut issues),
        }
    }

    // Unexpected columns are emitted last, in input order.
    for input_column in &input.columns {
        if !schema_names.contains(input_column.name.as_str()) {
            issues.push(issue(
                ValidationCode::UnexpectedColumn,
                &input_column.name,
                None,
                None,
            ));
        }
    }

    ValidationResult::new(issues)
}

fn validate_column(
    input_column: &ColumnInput,
    schema_column: &SuggestedColumnSchema,
    issues: &mut Vec<ValidationIssue>,
) {
    if input_column.logical_type != schema_column.logical_type {
        issues.push(issue(
            ValidationCode::TypeMismatch,
            &schema_column.name,
            Some(ValidationValue::LogicalType(
                schema_column.logical_type.clone(),
            )),
            Some(ValidationValue::LogicalType(
                input_column.logical_type.clone(),
            )),
        ));
        return;
    }

    if !schema_column.nullable && has_nulls(&input_column.values) {
        issues.push(issue(
            ValidationCode::NullNotAllowed,
            &schema_column.name,
            None,
            None,
        ));
    }

    if let Some(allowed_values) = schema_column.constraints.allowed_values.as_deref() {
        for invalid_value in validate_allowed_values(
            &input_column.values,
            &schema_column.logical_type,
            allowed_values,
        ) {
            issues.push(issue(
                ValidationCode::ValueNotAllowed,
                &schema_column.name,
                None,
                Some(invalid_value),
            ));
        }
    }

    if let Some(range) = schema_column.constraints.numeric_range.as_ref() {
        if validate_numeric_range(&input_column.values, &schema_column.logical_type, range) {
            issues.push(issue(
                ValidationCode::RangeViolation,
                &schema_column.name,
                None,
                None,
            ));
        }
    }
}

fn issue(
    code: ValidationCode,
    column: &str,
    expected: Option<ValidationValue>,
    observed: Option<ValidationValue>,
) -> ValidationIssue {
    ValidationIssue::new(
        code,
        ValidationSeverity::Error,
        Some(column.to_string()),
        expected,
        observed,
    )
}

fn has_nulls(values: &[ProfileValue]) -> bool {
    values
        .iter()
        .any(|value| matches!(value, ProfileValue::Null))
}

fn validate_allowed_values(
    values: &[ProfileValue],
    logical_type: &LogicalType,
    allowed_values: &[SuggestedValue],
) -> Vec<ValidationValue> {
    let allowed_values = allowed_values_for(logical_type, allowed_values);
    if allowed_values.is_empty() {
        return Vec::new();
    }

    let mut seen = HashSet::new();
    let mut invalid_values = Vec::new();

    for value in values {
        let Some(value) = allowed_value_from_profile(value) else {
            continue;
        };

        if !value_matches_allowed(&value, &allowed_values) && seen.insert(value.clone()) {
            invalid_values.push(value.into_validation_value());
        }
    }

    invalid_values
}

fn allowed_values_for(
    logical_type: &LogicalType,
    allowed_values: &[SuggestedValue],
) -> HashSet<AllowedValue> {
    match logical_type {
        LogicalType::String => allowed_values
            .iter()
            .filter_map(|value| match value {
                SuggestedValue::String(value) => Some(AllowedValue::String(value.clone())),
                SuggestedValue::Boolean(_) => None,
            })
            .collect(),
        LogicalType::Boolean => allowed_values
            .iter()
            .filter_map(|value| match value {
                SuggestedValue::String(_) => None,
                SuggestedValue::Boolean(value) => Some(AllowedValue::Boolean(*value)),
            })
            .collect(),
        LogicalType::Categorical => allowed_values
            .iter()
            .map(allowed_value_from_suggested)
            .collect(),
        LogicalType::Integer
        | LogicalType::Float
        | LogicalType::Datetime
        | LogicalType::Unknown => HashSet::new(),
    }
}

fn allowed_value_from_suggested(value: &SuggestedValue) -> AllowedValue {
    match value {
        SuggestedValue::String(value) => AllowedValue::String(value.clone()),
        SuggestedValue::Boolean(value) => AllowedValue::Boolean(*value),
    }
}

fn value_matches_allowed(value: &AllowedValue, allowed_values: &HashSet<AllowedValue>) -> bool {
    allowed_values.contains(value)
}

fn validate_numeric_range(
    values: &[ProfileValue],
    logical_type: &LogicalType,
    range: &SuggestedNumericRange,
) -> bool {
    if !matches!(logical_type, LogicalType::Integer | LogicalType::Float) {
        return false;
    }

    values.iter().filter_map(numeric_value).any(|value| {
        range.min.is_some_and(|min| value < min) || range.max.is_some_and(|max| value > max)
    })
}

fn numeric_value(value: &ProfileValue) -> Option<f64> {
    match value {
        ProfileValue::Integer(value) => Some(*value as f64),
        ProfileValue::Float(value) if !value.is_nan() => Some(*value),
        ProfileValue::Float(_)
        | ProfileValue::Null
        | ProfileValue::Boolean(_)
        | ProfileValue::String(_) => None,
    }
}

#[derive(Clone, PartialEq, Eq, Hash)]
enum AllowedValue {
    String(String),
    Boolean(bool),
}

impl AllowedValue {
    fn into_validation_value(self) -> ValidationValue {
        match self {
            Self::String(value) => ValidationValue::String(value),
            Self::Boolean(value) => ValidationValue::Boolean(value),
        }
    }
}

fn allowed_value_from_profile(value: &ProfileValue) -> Option<AllowedValue> {
    match value {
        ProfileValue::String(value) => Some(AllowedValue::String(value.clone())),
        ProfileValue::Boolean(value) => Some(AllowedValue::Boolean(*value)),
        ProfileValue::Null | ProfileValue::Integer(_) | ProfileValue::Float(_) => None,
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::schema::{SuggestedConstraints, SuggestedNumericRange};

    fn input_column(
        name: &str,
        logical_type: LogicalType,
        values: Vec<ProfileValue>,
    ) -> ColumnInput {
        ColumnInput::new(name.to_string(), logical_type, values)
    }

    fn schema_column(
        name: &str,
        logical_type: LogicalType,
        nullable: bool,
        numeric_range: Option<SuggestedNumericRange>,
        allowed_values: Option<Vec<SuggestedValue>>,
    ) -> SuggestedColumnSchema {
        SuggestedColumnSchema::new(
            name.to_string(),
            logical_type,
            nullable,
            SuggestedConstraints::new(numeric_range, allowed_values),
        )
    }

    fn schema(columns: Vec<SuggestedColumnSchema>) -> SuggestedDatasetSchema {
        SuggestedDatasetSchema::new(columns)
    }

    fn range(min: Option<f64>, max: Option<f64>) -> SuggestedNumericRange {
        SuggestedNumericRange::new(min, max)
    }

    #[test]
    fn empty_input_and_schema_are_valid() {
        let result = validate_dataset(&DatasetInput::new(Vec::new()), &schema(Vec::new()));

        assert!(result.issues.is_empty());
        assert!(result.is_valid());
    }

    #[test]
    fn valid_dataset_has_no_issues() {
        let input = DatasetInput::new(vec![
            input_column("id", LogicalType::Integer, vec![ProfileValue::Integer(1)]),
            input_column(
                "region",
                LogicalType::Categorical,
                vec![ProfileValue::String("North".to_string())],
            ),
        ]);
        let schema = schema(vec![
            schema_column("id", LogicalType::Integer, false, None, None),
            schema_column(
                "region",
                LogicalType::Categorical,
                false,
                None,
                Some(vec![SuggestedValue::String("North".to_string())]),
            ),
        ]);

        let result = validate_dataset(&input, &schema);

        assert!(result.issues.is_empty());
        assert!(result.is_valid());
    }

    #[test]
    fn matching_is_by_name_not_column_position() {
        let input = DatasetInput::new(vec![
            input_column(
                "region",
                LogicalType::String,
                vec![ProfileValue::String("North".to_string())],
            ),
            input_column("id", LogicalType::Integer, vec![ProfileValue::Integer(1)]),
            input_column("sales", LogicalType::Float, vec![ProfileValue::Float(10.0)]),
        ]);
        let schema = schema(vec![
            schema_column("id", LogicalType::Integer, false, None, None),
            schema_column("sales", LogicalType::Float, false, None, None),
            schema_column("region", LogicalType::String, false, None, None),
        ]);

        assert!(validate_dataset(&input, &schema).is_valid());
    }

    #[test]
    fn missing_column_stops_validation_for_that_column() {
        let input = DatasetInput::new(vec![input_column(
            "id",
            LogicalType::Integer,
            vec![ProfileValue::Integer(1)],
        )]);
        let schema = schema(vec![
            schema_column("id", LogicalType::Integer, false, None, None),
            schema_column(
                "sales",
                LogicalType::Float,
                false,
                Some(range(Some(0.0), Some(10.0))),
                None,
            ),
        ]);

        let result = validate_dataset(&input, &schema);

        assert_eq!(result.issues.len(), 1);
        assert_eq!(result.issues[0].code, ValidationCode::MissingColumn);
        assert_eq!(result.issues[0].column.as_deref(), Some("sales"));
        assert_eq!(result.issues[0].expected, None);
        assert_eq!(result.issues[0].observed, None);
    }

    #[test]
    fn unexpected_columns_are_reported_in_input_order() {
        let input = DatasetInput::new(vec![
            input_column("id", LogicalType::Integer, vec![]),
            input_column("legacy", LogicalType::String, vec![]),
            input_column("temporary", LogicalType::Boolean, vec![]),
        ]);
        let schema = schema(vec![schema_column(
            "id",
            LogicalType::Integer,
            false,
            None,
            None,
        )]);

        let result = validate_dataset(&input, &schema);

        assert_eq!(
            result
                .issues
                .iter()
                .map(|issue| (issue.code, issue.column.as_deref()))
                .collect::<Vec<_>>(),
            vec![
                (ValidationCode::UnexpectedColumn, Some("legacy")),
                (ValidationCode::UnexpectedColumn, Some("temporary")),
            ]
        );
    }

    #[test]
    fn type_mismatch_reports_both_types_and_stops_the_column() {
        let input = DatasetInput::new(vec![input_column(
            "age",
            LogicalType::String,
            vec![ProfileValue::Null, ProfileValue::String("old".to_string())],
        )]);
        let schema = schema(vec![schema_column(
            "age",
            LogicalType::Integer,
            false,
            Some(range(Some(0.0), Some(120.0))),
            Some(vec![SuggestedValue::String("not applicable".to_string())]),
        )]);

        let result = validate_dataset(&input, &schema);

        assert_eq!(result.issues.len(), 1);
        assert_eq!(result.issues[0].code, ValidationCode::TypeMismatch);
        assert_eq!(
            result.issues[0].expected,
            Some(ValidationValue::LogicalType(LogicalType::Integer))
        );
        assert_eq!(
            result.issues[0].observed,
            Some(ValidationValue::LogicalType(LogicalType::String))
        );
    }

    #[test]
    fn non_nullable_column_emits_one_null_issue() {
        let input = DatasetInput::new(vec![input_column(
            "id",
            LogicalType::Integer,
            vec![
                ProfileValue::Null,
                ProfileValue::Integer(1),
                ProfileValue::Null,
            ],
        )]);
        let schema = schema(vec![schema_column(
            "id",
            LogicalType::Integer,
            false,
            None,
            None,
        )]);

        let result = validate_dataset(&input, &schema);

        assert_eq!(result.issues.len(), 1);
        assert_eq!(result.issues[0].code, ValidationCode::NullNotAllowed);
    }

    #[test]
    fn nullable_column_allows_nulls() {
        let input = DatasetInput::new(vec![input_column(
            "id",
            LogicalType::Integer,
            vec![ProfileValue::Null, ProfileValue::Integer(1)],
        )]);
        let schema = schema(vec![schema_column(
            "id",
            LogicalType::Integer,
            true,
            None,
            None,
        )]);

        assert!(validate_dataset(&input, &schema).is_valid());
    }

    #[test]
    fn allowed_string_values_accept_valid_input() {
        let input = DatasetInput::new(vec![input_column(
            "state",
            LogicalType::String,
            vec![
                ProfileValue::String("A".to_string()),
                ProfileValue::String("B".to_string()),
                ProfileValue::String("A".to_string()),
            ],
        )]);
        let schema = schema(vec![schema_column(
            "state",
            LogicalType::String,
            false,
            None,
            Some(vec![
                SuggestedValue::String("A".to_string()),
                SuggestedValue::String("B".to_string()),
            ]),
        )]);

        assert!(validate_dataset(&input, &schema).is_valid());
    }

    #[test]
    fn one_disallowed_value_is_reported_once() {
        let input = DatasetInput::new(vec![input_column(
            "state",
            LogicalType::String,
            vec![
                ProfileValue::String("A".to_string()),
                ProfileValue::String("C".to_string()),
                ProfileValue::String("A".to_string()),
            ],
        )]);
        let schema = schema(vec![schema_column(
            "state",
            LogicalType::String,
            false,
            None,
            Some(vec![
                SuggestedValue::String("A".to_string()),
                SuggestedValue::String("B".to_string()),
            ]),
        )]);

        let result = validate_dataset(&input, &schema);

        assert_eq!(result.issues.len(), 1);
        assert_eq!(result.issues[0].code, ValidationCode::ValueNotAllowed);
        assert_eq!(
            result.issues[0].observed,
            Some(ValidationValue::String("C".to_string()))
        );
    }

    #[test]
    fn repeated_disallowed_values_are_reported_once_each() {
        let input = DatasetInput::new(vec![input_column(
            "state",
            LogicalType::String,
            vec![
                ProfileValue::String("C".to_string()),
                ProfileValue::String("C".to_string()),
                ProfileValue::String("D".to_string()),
                ProfileValue::String("C".to_string()),
            ],
        )]);
        let schema = schema(vec![schema_column(
            "state",
            LogicalType::String,
            false,
            None,
            Some(vec![
                SuggestedValue::String("A".to_string()),
                SuggestedValue::String("B".to_string()),
            ]),
        )]);

        let result = validate_dataset(&input, &schema);

        assert_eq!(
            result
                .issues
                .iter()
                .map(|issue| issue.observed.clone())
                .collect::<Vec<_>>(),
            vec![
                Some(ValidationValue::String("C".to_string())),
                Some(ValidationValue::String("D".to_string())),
            ]
        );
    }

    #[test]
    fn disallowed_values_are_deduplicated_in_first_appearance_order() {
        let input = DatasetInput::new(vec![input_column(
            "state",
            LogicalType::String,
            vec![
                ProfileValue::String("D".to_string()),
                ProfileValue::String("C".to_string()),
                ProfileValue::String("D".to_string()),
                ProfileValue::String("C".to_string()),
            ],
        )]);
        let schema = schema(vec![schema_column(
            "state",
            LogicalType::String,
            false,
            None,
            Some(vec![
                SuggestedValue::String("A".to_string()),
                SuggestedValue::String("B".to_string()),
            ]),
        )]);

        let result = validate_dataset(&input, &schema);

        assert_eq!(result.issues.len(), 2);
        assert_eq!(result.issues[0].code, ValidationCode::ValueNotAllowed);
        assert_eq!(
            result.issues[0].observed,
            Some(ValidationValue::String("D".to_string()))
        );
        assert_eq!(
            result.issues[1].observed,
            Some(ValidationValue::String("C".to_string()))
        );
    }

    #[test]
    fn nulls_are_not_checked_against_allowed_values() {
        let input = DatasetInput::new(vec![input_column(
            "state",
            LogicalType::String,
            vec![
                ProfileValue::String("A".to_string()),
                ProfileValue::Null,
                ProfileValue::String("B".to_string()),
            ],
        )]);
        let schema = schema(vec![schema_column(
            "state",
            LogicalType::String,
            true,
            None,
            Some(vec![
                SuggestedValue::String("A".to_string()),
                SuggestedValue::String("B".to_string()),
            ]),
        )]);

        assert!(validate_dataset(&input, &schema).is_valid());
    }

    #[test]
    fn allowed_boolean_values_report_false() {
        let input = DatasetInput::new(vec![input_column(
            "active",
            LogicalType::Boolean,
            vec![ProfileValue::Boolean(true), ProfileValue::Boolean(false)],
        )]);
        let schema = schema(vec![schema_column(
            "active",
            LogicalType::Boolean,
            false,
            None,
            Some(vec![SuggestedValue::Boolean(true)]),
        )]);

        let result = validate_dataset(&input, &schema);

        assert_eq!(result.issues.len(), 1);
        assert_eq!(result.issues[0].code, ValidationCode::ValueNotAllowed);
        assert_eq!(
            result.issues[0].observed,
            Some(ValidationValue::Boolean(false))
        );
    }

    #[test]
    fn integer_range_accepts_boundaries_and_reports_one_violation() {
        let schema = schema(vec![schema_column(
            "score",
            LogicalType::Integer,
            false,
            Some(range(Some(0.0), Some(10.0))),
            None,
        )]);
        let valid = DatasetInput::new(vec![input_column(
            "score",
            LogicalType::Integer,
            vec![
                ProfileValue::Integer(0),
                ProfileValue::Integer(5),
                ProfileValue::Integer(10),
            ],
        )]);
        let invalid = DatasetInput::new(vec![input_column(
            "score",
            LogicalType::Integer,
            vec![
                ProfileValue::Integer(-1),
                ProfileValue::Integer(5),
                ProfileValue::Integer(11),
            ],
        )]);

        assert!(validate_dataset(&valid, &schema).is_valid());
        let result = validate_dataset(&invalid, &schema);
        assert_eq!(result.issues.len(), 1);
        assert_eq!(result.issues[0].code, ValidationCode::RangeViolation);
        assert_eq!(result.issues[0].expected, None);
        assert_eq!(result.issues[0].observed, None);
    }

    #[test]
    fn float_ranges_and_single_limits_are_checked() {
        let float_schema = schema(vec![schema_column(
            "ratio",
            LogicalType::Float,
            false,
            Some(range(Some(0.0), Some(1.0))),
            None,
        )]);
        let valid = DatasetInput::new(vec![input_column(
            "ratio",
            LogicalType::Float,
            vec![
                ProfileValue::Float(0.0),
                ProfileValue::Float(0.5),
                ProfileValue::Float(1.0),
            ],
        )]);
        let invalid = DatasetInput::new(vec![input_column(
            "ratio",
            LogicalType::Float,
            vec![ProfileValue::Float(1.1)],
        )]);
        let min_schema = schema(vec![schema_column(
            "score",
            LogicalType::Integer,
            false,
            Some(range(Some(0.0), None)),
            None,
        )]);
        let max_schema = schema(vec![schema_column(
            "score",
            LogicalType::Integer,
            false,
            Some(range(None, Some(100.0))),
            None,
        )]);

        assert!(validate_dataset(&valid, &float_schema).is_valid());
        assert_eq!(
            validate_dataset(&invalid, &float_schema).issues[0].code,
            ValidationCode::RangeViolation
        );
        assert!(!validate_dataset(
            &DatasetInput::new(vec![input_column(
                "score",
                LogicalType::Integer,
                vec![ProfileValue::Integer(-1)],
            )]),
            &min_schema,
        )
        .is_valid());
        assert!(validate_dataset(
            &DatasetInput::new(vec![input_column(
                "score",
                LogicalType::Integer,
                vec![ProfileValue::Integer(100)],
            )]),
            &min_schema,
        )
        .is_valid());
        assert!(!validate_dataset(
            &DatasetInput::new(vec![input_column(
                "score",
                LogicalType::Integer,
                vec![ProfileValue::Integer(101)],
            )]),
            &max_schema,
        )
        .is_valid());
        assert!(validate_dataset(
            &DatasetInput::new(vec![input_column(
                "score",
                LogicalType::Integer,
                vec![ProfileValue::Integer(-100)],
            )]),
            &max_schema,
        )
        .is_valid());
    }

    #[test]
    fn nan_is_ignored_but_infinities_follow_range_limits() {
        let bounded = schema(vec![schema_column(
            "value",
            LogicalType::Float,
            true,
            Some(range(Some(0.0), Some(100.0))),
            None,
        )]);
        let nan_and_null = DatasetInput::new(vec![input_column(
            "value",
            LogicalType::Float,
            vec![ProfileValue::Float(f64::NAN), ProfileValue::Null],
        )]);
        let infinities = DatasetInput::new(vec![input_column(
            "value",
            LogicalType::Float,
            vec![
                ProfileValue::Float(f64::INFINITY),
                ProfileValue::Float(f64::NEG_INFINITY),
            ],
        )]);
        let min_only = schema(vec![schema_column(
            "value",
            LogicalType::Float,
            false,
            Some(range(Some(0.0), None)),
            None,
        )]);
        let max_only = schema(vec![schema_column(
            "value",
            LogicalType::Float,
            false,
            Some(range(None, Some(100.0))),
            None,
        )]);

        assert!(validate_dataset(&nan_and_null, &bounded).is_valid());
        assert_eq!(
            validate_dataset(&infinities, &bounded).issues[0].code,
            ValidationCode::RangeViolation
        );
        assert!(validate_dataset(
            &DatasetInput::new(vec![input_column(
                "value",
                LogicalType::Float,
                vec![ProfileValue::Float(f64::INFINITY)],
            )]),
            &min_only,
        )
        .is_valid());
        assert!(!validate_dataset(
            &DatasetInput::new(vec![input_column(
                "value",
                LogicalType::Float,
                vec![ProfileValue::Float(f64::NEG_INFINITY)],
            )]),
            &min_only,
        )
        .is_valid());
        assert!(validate_dataset(
            &DatasetInput::new(vec![input_column(
                "value",
                LogicalType::Float,
                vec![ProfileValue::Float(f64::NEG_INFINITY)],
            )]),
            &max_only,
        )
        .is_valid());
        assert!(!validate_dataset(
            &DatasetInput::new(vec![input_column(
                "value",
                LogicalType::Float,
                vec![ProfileValue::Float(f64::INFINITY)],
            )]),
            &max_only,
        )
        .is_valid());
    }

    #[test]
    fn numeric_range_on_non_numeric_schema_is_ignored() {
        let input = DatasetInput::new(vec![input_column(
            "name",
            LogicalType::String,
            vec![ProfileValue::String("outside".to_string())],
        )]);
        let schema = schema(vec![schema_column(
            "name",
            LogicalType::String,
            false,
            Some(range(Some(0.0), Some(1.0))),
            None,
        )]);

        assert!(validate_dataset(&input, &schema).is_valid());
    }

    #[test]
    fn mixed_issues_follow_the_documented_deterministic_order() {
        let input = DatasetInput::new(vec![
            input_column("id", LogicalType::String, vec![ProfileValue::Null]),
            input_column("name", LogicalType::String, vec![ProfileValue::Null]),
            input_column(
                "region",
                LogicalType::String,
                vec![ProfileValue::String("West".to_string())],
            ),
            input_column("legacy", LogicalType::Boolean, vec![]),
        ]);
        let schema = schema(vec![
            schema_column("missing", LogicalType::Integer, false, None, None),
            schema_column("id", LogicalType::Integer, false, None, None),
            schema_column("name", LogicalType::String, false, None, None),
            schema_column(
                "region",
                LogicalType::String,
                false,
                None,
                Some(vec![SuggestedValue::String("North".to_string())]),
            ),
        ]);

        let result = validate_dataset(&input, &schema);

        assert_eq!(result.issues.len(), 5);
        assert_eq!(
            result
                .issues
                .iter()
                .map(|issue| issue.code)
                .collect::<Vec<_>>(),
            vec![
                ValidationCode::MissingColumn,
                ValidationCode::TypeMismatch,
                ValidationCode::NullNotAllowed,
                ValidationCode::ValueNotAllowed,
                ValidationCode::UnexpectedColumn,
            ]
        );
        assert!(!result.is_valid());
        assert_eq!(result.error_count(), 5);
        assert_eq!(result.warning_count(), 0);
    }

    #[test]
    fn engine_issues_are_all_errors() {
        let input = DatasetInput::new(vec![input_column("legacy", LogicalType::String, vec![])]);

        let result = validate_dataset(&input, &schema(Vec::new()));

        assert!(result
            .issues
            .iter()
            .all(|issue| issue.severity == ValidationSeverity::Error));
        assert_eq!(result.warning_count(), 0);
    }

    #[test]
    fn validation_does_not_mutate_input_or_schema() {
        let input = DatasetInput::new(vec![input_column(
            "state",
            LogicalType::String,
            vec![ProfileValue::String("C".to_string())],
        )]);
        let schema = schema(vec![schema_column(
            "state",
            LogicalType::String,
            false,
            None,
            Some(vec![SuggestedValue::String("A".to_string())]),
        )]);
        let original_input_name = input.columns[0].name.clone();
        let original_input_type = input.columns[0].logical_type.clone();
        let original_input_values = input.columns[0].values.clone();
        let original_schema = schema.clone();

        let _ = validate_dataset(&input, &schema);

        assert_eq!(input.columns[0].name, original_input_name);
        assert_eq!(input.columns[0].logical_type, original_input_type);
        assert_eq!(input.columns[0].values, original_input_values);
        assert_eq!(schema, original_schema);
    }
}

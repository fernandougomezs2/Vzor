use crate::profiling::LogicalType;

use super::{ObservedColumnSchema, ObservedValue, SuggestedConstraints, SuggestedValue};

/// Derives a suggested nullability rule directly from observed nullability.
///
/// The result is a proposal, not an approved data-contract rule.
pub fn infer_nullable(column: &ObservedColumnSchema) -> bool {
    column.observed_nullable
}

/// Generates conservative suggested constraints from one observed column.
///
/// The result is a proposal, not an approved data contract. Vzor v0.1 never
/// turns an observed numeric range into a constraint, never treats a
/// low-cardinality String as an enum, and only suggests allowed values for a
/// Categorical column with non-empty observed values.
pub fn infer_constraints(column: &ObservedColumnSchema) -> SuggestedConstraints {
    SuggestedConstraints::new(None, infer_allowed_values(column))
}

fn infer_allowed_values(column: &ObservedColumnSchema) -> Option<Vec<SuggestedValue>> {
    if column.logical_type != LogicalType::Categorical {
        return None;
    }

    let observed_values = column.observed_values.as_ref()?;
    if observed_values.is_empty() {
        return None;
    }

    Some(
        observed_values
            .iter()
            .map(suggested_value_from_observed)
            .collect(),
    )
}

fn suggested_value_from_observed(value: &ObservedValue) -> SuggestedValue {
    match value {
        ObservedValue::String(value) => SuggestedValue::String(value.clone()),
        ObservedValue::Boolean(value) => SuggestedValue::Boolean(*value),
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::schema::ObservedRange;

    fn observed_column(
        logical_type: LogicalType,
        observed_nullable: bool,
        observed_range: Option<ObservedRange>,
        observed_values: Option<Vec<ObservedValue>>,
    ) -> ObservedColumnSchema {
        ObservedColumnSchema::new(
            "column".to_string(),
            logical_type,
            observed_nullable,
            0,
            observed_range,
            observed_values,
        )
    }

    #[test]
    fn nullable_suggestion_matches_observed_nullability_for_every_logical_type() {
        let types = [
            LogicalType::Integer,
            LogicalType::Float,
            LogicalType::Boolean,
            LogicalType::String,
            LogicalType::Datetime,
            LogicalType::Categorical,
            LogicalType::Unknown,
        ];

        for logical_type in types {
            assert!(!infer_nullable(&observed_column(
                logical_type.clone(),
                false,
                None,
                None,
            )));
            assert!(infer_nullable(&observed_column(
                logical_type,
                true,
                None,
                None
            )));
        }
    }

    #[test]
    fn numeric_observations_never_become_numeric_constraints() {
        for logical_type in [LogicalType::Integer, LogicalType::Float] {
            let constraints = infer_constraints(&observed_column(
                logical_type,
                false,
                Some(ObservedRange::new(-5.0, 100.0)),
                None,
            ));

            assert_eq!(constraints.numeric_range, None);
            assert_eq!(constraints.allowed_values, None);
        }
    }

    #[test]
    fn string_observations_never_become_allowed_values() {
        let low_cardinality = infer_constraints(&observed_column(
            LogicalType::String,
            false,
            None,
            Some(vec![
                ObservedValue::String("North".to_string()),
                ObservedValue::String("South".to_string()),
            ]),
        ));
        let empty = infer_constraints(&observed_column(
            LogicalType::String,
            false,
            None,
            Some(Vec::new()),
        ));

        assert_eq!(low_cardinality.allowed_values, None);
        assert_eq!(empty.allowed_values, None);
    }

    #[test]
    fn categorical_values_become_allowed_values_in_observed_order() {
        let column = observed_column(
            LogicalType::Categorical,
            false,
            None,
            Some(vec![
                ObservedValue::String("South".to_string()),
                ObservedValue::String("North".to_string()),
                ObservedValue::String("West".to_string()),
            ]),
        );
        let original = column.clone();

        let constraints = infer_constraints(&column);

        assert_eq!(
            constraints.allowed_values,
            Some(vec![
                SuggestedValue::String("South".to_string()),
                SuggestedValue::String("North".to_string()),
                SuggestedValue::String("West".to_string()),
            ])
        );
        assert_eq!(constraints.numeric_range, None);
        assert_eq!(column, original);
    }

    #[test]
    fn categorical_empty_and_high_cardinality_observations_do_not_become_allowed_values() {
        let empty = infer_constraints(&observed_column(
            LogicalType::Categorical,
            true,
            None,
            Some(Vec::new()),
        ));
        let high_cardinality = infer_constraints(&observed_column(
            LogicalType::Categorical,
            false,
            None,
            None,
        ));

        assert_eq!(empty.allowed_values, None);
        assert_eq!(high_cardinality.allowed_values, None);
    }

    #[test]
    fn categorical_boolean_observations_are_converted_without_panicking() {
        let constraints = infer_constraints(&observed_column(
            LogicalType::Categorical,
            false,
            None,
            Some(vec![
                ObservedValue::Boolean(true),
                ObservedValue::Boolean(false),
            ]),
        ));

        assert_eq!(
            constraints.allowed_values,
            Some(vec![
                SuggestedValue::Boolean(true),
                SuggestedValue::Boolean(false),
            ])
        );
    }

    #[test]
    fn boolean_datetime_and_unknown_constraints_are_empty() {
        for logical_type in [
            LogicalType::Boolean,
            LogicalType::Datetime,
            LogicalType::Unknown,
        ] {
            let constraints = infer_constraints(&observed_column(
                logical_type,
                true,
                Some(ObservedRange::new(1.0, 2.0)),
                Some(vec![ObservedValue::Boolean(true)]),
            ));

            assert_eq!(constraints.numeric_range, None);
            assert_eq!(constraints.allowed_values, None);
        }
    }

    #[test]
    fn numeric_range_is_none_for_every_logical_type() {
        for logical_type in [
            LogicalType::Integer,
            LogicalType::Float,
            LogicalType::Boolean,
            LogicalType::String,
            LogicalType::Datetime,
            LogicalType::Categorical,
            LogicalType::Unknown,
        ] {
            let constraints = infer_constraints(&observed_column(
                logical_type,
                false,
                Some(ObservedRange::new(1.0, 2.0)),
                None,
            ));

            assert_eq!(constraints.numeric_range, None);
        }
    }
}

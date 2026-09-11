use std::collections::HashSet;

use crate::profiling::{ColumnProfile, DatasetInput, DatasetProfile, LogicalType, ProfileValue};

use super::{
    infer_constraints, infer_nullable, ObservedColumnSchema, ObservedDatasetSchema, ObservedRange,
    ObservedValue, SuggestedColumnSchema, SuggestedDatasetSchema,
};

/// Maximum non-null distinct String or Categorical values retained in a snapshot.
const MAX_OBSERVED_VALUES: usize = 50;

/// Structural mismatches between a profile and the input used to observe values.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum SchemaObservationError {
    ColumnCountMismatch {
        profile: usize,
        input: usize,
    },
    ColumnNameMismatch {
        index: usize,
        profile: String,
        input: String,
    },
    LogicalTypeMismatch {
        column: String,
        profile: LogicalType,
        input: LogicalType,
    },
    ObservedValueCountMismatch {
        column: String,
        expected: usize,
        actual: usize,
    },
}

/// Converts profiling results into observations without generating constraints.
///
/// This conversion does not recalculate profiling. It derives ranges from
/// numeric min/max values and intentionally leaves `observed_values` unset.
pub fn observed_schema_from_profile(profile: &DatasetProfile) -> ObservedDatasetSchema {
    let columns = profile
        .columns
        .iter()
        .map(|column| observed_column_from_profile(column, None))
        .collect();

    ObservedDatasetSchema::new(profile.row_count, columns)
}

/// Converts a profile and its normalized input into an observed schema.
///
/// Values are retained only for eligible logical types. They are observations,
/// not allowed values: nulls are excluded, first-appearance order is retained,
/// and high-cardinality String or Categorical columns produce `None`.
pub fn observed_schema_from_profile_and_input(
    profile: &DatasetProfile,
    input: &DatasetInput,
) -> Result<ObservedDatasetSchema, SchemaObservationError> {
    validate_profile_input(profile, input)?;

    let columns = profile
        .columns
        .iter()
        .zip(&input.columns)
        .map(|(profile_column, input_column)| {
            let observed_values = collect_observed_values(
                &profile_column.logical_type,
                &input_column.values,
                profile_column.unique_count,
            );

            if let Some(values) = &observed_values {
                if values.len() != profile_column.unique_count {
                    return Err(SchemaObservationError::ObservedValueCountMismatch {
                        column: profile_column.name.clone(),
                        expected: profile_column.unique_count,
                        actual: values.len(),
                    });
                }
            }

            Ok(observed_column_from_profile(
                profile_column,
                observed_values,
            ))
        })
        .collect::<Result<Vec<_>, _>>()?;

    Ok(ObservedDatasetSchema::new(profile.row_count, columns))
}

/// Converts an observed schema into a suggested schema using inference rules.
///
/// The result is a proposal, not an approved data contract. This conversion
/// does not reinterpret original data or recalculate profiling.
pub fn suggested_schema_from_observed(observed: &ObservedDatasetSchema) -> SuggestedDatasetSchema {
    let columns = observed
        .columns
        .iter()
        .map(suggested_column_from_observed)
        .collect();

    SuggestedDatasetSchema::new(columns)
}

fn suggested_column_from_observed(column: &ObservedColumnSchema) -> SuggestedColumnSchema {
    SuggestedColumnSchema::new(
        column.name.clone(),
        column.logical_type.clone(),
        infer_nullable(column),
        infer_constraints(column),
    )
}

fn observed_column_from_profile(
    column: &ColumnProfile,
    observed_values: Option<Vec<ObservedValue>>,
) -> ObservedColumnSchema {
    let observed_range = column
        .numeric_stats
        .as_ref()
        .map(|stats| ObservedRange::new(stats.min, stats.max));

    ObservedColumnSchema::new(
        column.name.clone(),
        column.logical_type.clone(),
        column.null_count > 0,
        column.unique_count,
        observed_range,
        observed_values,
    )
}

fn validate_profile_input(
    profile: &DatasetProfile,
    input: &DatasetInput,
) -> Result<(), SchemaObservationError> {
    if profile.columns.len() != input.columns.len() {
        return Err(SchemaObservationError::ColumnCountMismatch {
            profile: profile.columns.len(),
            input: input.columns.len(),
        });
    }

    for (index, (profile_column, input_column)) in
        profile.columns.iter().zip(&input.columns).enumerate()
    {
        if profile_column.name != input_column.name {
            return Err(SchemaObservationError::ColumnNameMismatch {
                index,
                profile: profile_column.name.clone(),
                input: input_column.name.clone(),
            });
        }
        if profile_column.logical_type != input_column.logical_type {
            return Err(SchemaObservationError::LogicalTypeMismatch {
                column: profile_column.name.clone(),
                profile: profile_column.logical_type.clone(),
                input: input_column.logical_type.clone(),
            });
        }
    }

    Ok(())
}

fn collect_observed_values(
    logical_type: &LogicalType,
    values: &[ProfileValue],
    unique_count: usize,
) -> Option<Vec<ObservedValue>> {
    match logical_type {
        LogicalType::Boolean => Some(collect_booleans(values)),
        LogicalType::String | LogicalType::Categorical if unique_count <= MAX_OBSERVED_VALUES => {
            Some(collect_strings(values))
        }
        _ => None,
    }
}

fn collect_booleans(values: &[ProfileValue]) -> Vec<ObservedValue> {
    let mut seen = HashSet::new();
    let mut observed = Vec::new();

    for value in values {
        if let ProfileValue::Boolean(value) = value {
            if seen.insert(*value) {
                observed.push(ObservedValue::Boolean(*value));
            }
        }
    }

    observed
}

fn collect_strings(values: &[ProfileValue]) -> Vec<ObservedValue> {
    let mut seen = HashSet::new();
    let mut observed = Vec::new();

    for value in values {
        if let ProfileValue::String(value) = value {
            if seen.insert(value.as_str()) {
                observed.push(ObservedValue::String(value.clone()));
            }
        }
    }

    observed
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::profiling::{profile_structure, ColumnInput, NumericStats};
    use crate::schema::SuggestedValue;

    fn profile_column(
        name: &str,
        logical_type: LogicalType,
        null_count: usize,
        unique_count: usize,
        numeric_stats: Option<NumericStats>,
    ) -> ColumnProfile {
        ColumnProfile::new(
            name.to_string(),
            logical_type,
            3,
            null_count,
            unique_count,
            numeric_stats,
        )
    }

    fn input_column(
        name: &str,
        logical_type: LogicalType,
        values: Vec<ProfileValue>,
    ) -> ColumnInput {
        ColumnInput::new(name.to_string(), logical_type, values)
    }

    fn string_values(count: usize) -> Vec<ProfileValue> {
        (0..count)
            .map(|index| ProfileValue::String(format!("value-{index}")))
            .collect()
    }

    #[test]
    fn profile_only_conversion_preserves_profile_observations() {
        let numeric_stats = NumericStats {
            min: 10.0,
            max: 500.0,
            mean: 100.0,
            median: 90.0,
            p25: 50.0,
            p50: 90.0,
            p75: 150.0,
        };
        let profile = DatasetProfile::new(
            3,
            vec![
                profile_column("sales", LogicalType::Float, 1, 2, Some(numeric_stats)),
                profile_column("region", LogicalType::String, 0, 2, None),
            ],
        );
        let original = profile.clone();

        let observed = observed_schema_from_profile(&profile);

        assert_eq!(profile, original);
        assert_eq!(observed.row_count, 3);
        assert_eq!(observed.column_count(), profile.column_count());
        assert_eq!(observed.columns[0].name, "sales");
        assert_eq!(observed.columns[0].logical_type, LogicalType::Float);
        assert!(observed.columns[0].observed_nullable);
        assert_eq!(observed.columns[0].observed_unique_count, 2);
        assert_eq!(
            observed.columns[0].observed_range,
            Some(ObservedRange::new(10.0, 500.0))
        );
        assert!(observed
            .columns
            .iter()
            .all(|column| column.observed_values.is_none()));
    }

    #[test]
    fn boolean_values_preserve_first_appearance_and_support_all_null_columns() {
        let profile = DatasetProfile::new(
            3,
            vec![profile_column("active", LogicalType::Boolean, 0, 2, None)],
        );
        let input = DatasetInput::new(vec![input_column(
            "active",
            LogicalType::Boolean,
            vec![
                ProfileValue::Boolean(false),
                ProfileValue::Boolean(true),
                ProfileValue::Boolean(false),
            ],
        )]);

        let observed = observed_schema_from_profile_and_input(&profile, &input).unwrap();

        assert_eq!(
            observed.columns[0].observed_values,
            Some(vec![
                ObservedValue::Boolean(false),
                ObservedValue::Boolean(true),
            ])
        );
        assert_eq!(
            observed.columns[0].observed_values.as_ref().unwrap().len(),
            2
        );

        let all_null_profile = DatasetProfile::new(
            2,
            vec![profile_column("active", LogicalType::Boolean, 2, 0, None)],
        );
        let all_null_input = DatasetInput::new(vec![input_column(
            "active",
            LogicalType::Boolean,
            vec![ProfileValue::Null, ProfileValue::Null],
        )]);
        let all_null =
            observed_schema_from_profile_and_input(&all_null_profile, &all_null_input).unwrap();

        assert!(all_null.columns[0].observed_nullable);
        assert_eq!(all_null.columns[0].observed_values, Some(Vec::new()));
    }

    #[test]
    fn string_values_exclude_nulls_keep_empty_strings_and_deduplicate_in_order() {
        let profile = DatasetProfile::new(
            5,
            vec![profile_column("label", LogicalType::String, 1, 3, None)],
        );
        let input = DatasetInput::new(vec![input_column(
            "label",
            LogicalType::String,
            vec![
                ProfileValue::String(String::new()),
                ProfileValue::String("A".to_string()),
                ProfileValue::Null,
                ProfileValue::String(String::new()),
                ProfileValue::String("B".to_string()),
            ],
        )]);

        let observed = observed_schema_from_profile_and_input(&profile, &input).unwrap();

        assert!(observed.columns[0].observed_nullable);
        assert_eq!(
            observed.columns[0].observed_values,
            Some(vec![
                ObservedValue::String(String::new()),
                ObservedValue::String("A".to_string()),
                ObservedValue::String("B".to_string()),
            ])
        );
    }

    #[test]
    fn string_threshold_is_inclusive_at_fifty_values() {
        for count in [49, 50, 51] {
            let profile = DatasetProfile::new(
                count,
                vec![profile_column("label", LogicalType::String, 0, count, None)],
            );
            let input = DatasetInput::new(vec![input_column(
                "label",
                LogicalType::String,
                string_values(count),
            )]);

            let observed = observed_schema_from_profile_and_input(&profile, &input).unwrap();
            let observed_values = &observed.columns[0].observed_values;

            if count <= MAX_OBSERVED_VALUES {
                assert_eq!(observed_values.as_ref().unwrap().len(), count);
            } else {
                assert_eq!(observed_values, &None);
            }
        }
    }

    #[test]
    fn categorical_values_follow_the_same_threshold_policy() {
        for count in [2, 50, 51] {
            let profile = DatasetProfile::new(
                count,
                vec![profile_column(
                    "region",
                    LogicalType::Categorical,
                    0,
                    count,
                    None,
                )],
            );
            let input = DatasetInput::new(vec![input_column(
                "region",
                LogicalType::Categorical,
                string_values(count),
            )]);

            let observed = observed_schema_from_profile_and_input(&profile, &input).unwrap();
            let observed_values = &observed.columns[0].observed_values;

            if count <= MAX_OBSERVED_VALUES {
                assert_eq!(observed_values.as_ref().unwrap().len(), count);
            } else {
                assert_eq!(observed_values, &None);
            }
        }
    }

    #[test]
    fn non_discrete_types_do_not_retain_observed_values() {
        let numeric_stats = NumericStats {
            min: 1.0,
            max: 3.0,
            mean: 2.0,
            median: 2.0,
            p25: 1.5,
            p50: 2.0,
            p75: 2.5,
        };
        let profile = DatasetProfile::new(
            3,
            vec![
                profile_column(
                    "integer",
                    LogicalType::Integer,
                    0,
                    3,
                    Some(numeric_stats.clone()),
                ),
                profile_column("float", LogicalType::Float, 0, 3, Some(numeric_stats)),
                profile_column("datetime", LogicalType::Datetime, 0, 3, None),
                profile_column("unknown", LogicalType::Unknown, 3, 0, None),
            ],
        );
        let input = DatasetInput::new(vec![
            input_column(
                "integer",
                LogicalType::Integer,
                vec![
                    ProfileValue::Integer(1),
                    ProfileValue::Integer(2),
                    ProfileValue::Integer(3),
                ],
            ),
            input_column(
                "float",
                LogicalType::Float,
                vec![
                    ProfileValue::Float(1.0),
                    ProfileValue::Float(2.0),
                    ProfileValue::Float(3.0),
                ],
            ),
            input_column(
                "datetime",
                LogicalType::Datetime,
                vec![
                    ProfileValue::String("2026-01-01".to_string()),
                    ProfileValue::String("2026-01-02".to_string()),
                    ProfileValue::String("2026-01-03".to_string()),
                ],
            ),
            input_column(
                "unknown",
                LogicalType::Unknown,
                vec![ProfileValue::Null, ProfileValue::Null, ProfileValue::Null],
            ),
        ]);

        let observed = observed_schema_from_profile_and_input(&profile, &input).unwrap();

        assert!(observed
            .columns
            .iter()
            .all(|column| column.observed_values.is_none()));
        assert_eq!(
            observed.columns[0].observed_range,
            Some(ObservedRange::new(1.0, 3.0))
        );
        assert_eq!(
            observed.columns[1].observed_range,
            Some(ObservedRange::new(1.0, 3.0))
        );
        assert!(observed.columns[2].observed_range.is_none());
        assert!(observed.columns[3].observed_nullable);
    }

    #[test]
    fn conversion_rejects_profile_and_input_structural_mismatches() {
        let profile = DatasetProfile::new(
            1,
            vec![profile_column("id", LogicalType::Integer, 0, 1, None)],
        );
        let empty_input = DatasetInput::new(Vec::new());
        let renamed_input = DatasetInput::new(vec![input_column(
            "other",
            LogicalType::Integer,
            vec![ProfileValue::Integer(1)],
        )]);
        let typed_input = DatasetInput::new(vec![input_column(
            "id",
            LogicalType::Float,
            vec![ProfileValue::Float(1.0)],
        )]);

        assert_eq!(
            observed_schema_from_profile_and_input(&profile, &empty_input),
            Err(SchemaObservationError::ColumnCountMismatch {
                profile: 1,
                input: 0,
            })
        );
        assert_eq!(
            observed_schema_from_profile_and_input(&profile, &renamed_input),
            Err(SchemaObservationError::ColumnNameMismatch {
                index: 0,
                profile: "id".to_string(),
                input: "other".to_string(),
            })
        );
        assert_eq!(
            observed_schema_from_profile_and_input(&profile, &typed_input),
            Err(SchemaObservationError::LogicalTypeMismatch {
                column: "id".to_string(),
                profile: LogicalType::Integer,
                input: LogicalType::Float,
            })
        );
    }

    #[test]
    fn conversion_rejects_inconsistent_observed_value_counts() {
        let profile = DatasetProfile::new(
            2,
            vec![profile_column("label", LogicalType::String, 0, 2, None)],
        );
        let input = DatasetInput::new(vec![input_column(
            "label",
            LogicalType::String,
            vec![
                ProfileValue::String("same".to_string()),
                ProfileValue::String("same".to_string()),
            ],
        )]);

        assert_eq!(
            observed_schema_from_profile_and_input(&profile, &input),
            Err(SchemaObservationError::ObservedValueCountMismatch {
                column: "label".to_string(),
                expected: 2,
                actual: 1,
            })
        );
    }

    #[test]
    fn profiling_and_schema_conversion_integrate_without_mutating_the_profile() {
        fn source_input() -> DatasetInput {
            DatasetInput::new(vec![
                input_column(
                    "id",
                    LogicalType::Integer,
                    vec![
                        ProfileValue::Integer(1),
                        ProfileValue::Integer(2),
                        ProfileValue::Integer(3),
                    ],
                ),
                input_column(
                    "sales",
                    LogicalType::Float,
                    vec![
                        ProfileValue::Float(10.0),
                        ProfileValue::Float(20.0),
                        ProfileValue::Null,
                    ],
                ),
                input_column(
                    "region",
                    LogicalType::String,
                    vec![
                        ProfileValue::String("South".to_string()),
                        ProfileValue::String("North".to_string()),
                        ProfileValue::String("South".to_string()),
                    ],
                ),
                input_column(
                    "active",
                    LogicalType::Boolean,
                    vec![
                        ProfileValue::Boolean(false),
                        ProfileValue::Boolean(true),
                        ProfileValue::Boolean(false),
                    ],
                ),
            ])
        }

        let profile = profile_structure(source_input()).unwrap();
        let original = profile.clone();
        let observed = observed_schema_from_profile_and_input(&profile, &source_input()).unwrap();

        assert_eq!(profile, original);
        assert_eq!(observed.row_count, 3);
        assert_eq!(observed.column_count(), 4);
        assert_eq!(
            observed.columns[0].observed_range,
            Some(ObservedRange::new(1.0, 3.0))
        );
        assert!(observed.columns[1].observed_nullable);
        assert_eq!(
            observed.columns[1].observed_range,
            Some(ObservedRange::new(10.0, 20.0))
        );
        assert_eq!(
            observed.columns[2].observed_values,
            Some(vec![
                ObservedValue::String("South".to_string()),
                ObservedValue::String("North".to_string()),
            ])
        );
        assert_eq!(
            observed.columns[3].observed_values,
            Some(vec![
                ObservedValue::Boolean(false),
                ObservedValue::Boolean(true),
            ])
        );
        for (profile_column, observed_column) in profile.columns.iter().zip(&observed.columns) {
            assert_eq!(observed_column.name, profile_column.name);
            assert_eq!(observed_column.logical_type, profile_column.logical_type);
            assert_eq!(
                observed_column.observed_unique_count,
                profile_column.unique_count
            );
        }
    }

    #[test]
    fn suggested_conversion_supports_empty_observed_datasets() {
        let observed = ObservedDatasetSchema::new(99, Vec::new());

        let suggested = suggested_schema_from_observed(&observed);

        assert_eq!(suggested.column_count(), 0);
        assert!(suggested.columns.is_empty());
        assert_eq!(suggested.column("missing"), None);
    }

    #[test]
    fn suggested_conversion_preserves_column_structure_and_delegates_inference() {
        let observed = ObservedDatasetSchema::new(
            4,
            vec![
                ObservedColumnSchema::new(
                    "z_integer".to_string(),
                    LogicalType::Integer,
                    false,
                    4,
                    Some(ObservedRange::new(18.0, 65.0)),
                    None,
                ),
                ObservedColumnSchema::new(
                    "a_float".to_string(),
                    LogicalType::Float,
                    true,
                    3,
                    Some(ObservedRange::new(10.5, 99.9)),
                    None,
                ),
                ObservedColumnSchema::new(
                    "m_string".to_string(),
                    LogicalType::String,
                    false,
                    2,
                    None,
                    Some(vec![
                        ObservedValue::String("North".to_string()),
                        ObservedValue::String("South".to_string()),
                    ]),
                ),
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
                ObservedColumnSchema::new(
                    "region".to_string(),
                    LogicalType::Categorical,
                    true,
                    3,
                    None,
                    Some(vec![
                        ObservedValue::String("South".to_string()),
                        ObservedValue::String("North".to_string()),
                        ObservedValue::String("West".to_string()),
                    ]),
                ),
                ObservedColumnSchema::new(
                    "created_at".to_string(),
                    LogicalType::Datetime,
                    false,
                    4,
                    None,
                    None,
                ),
                ObservedColumnSchema::new(
                    "unresolved".to_string(),
                    LogicalType::Unknown,
                    true,
                    0,
                    None,
                    None,
                ),
            ],
        );
        let original = observed.clone();

        let suggested = suggested_schema_from_observed(&observed);

        assert_eq!(observed, original);
        assert_eq!(suggested.column_count(), observed.column_count());
        assert_eq!(
            suggested
                .columns
                .iter()
                .map(|column| column.name.as_str())
                .collect::<Vec<_>>(),
            vec![
                "z_integer",
                "a_float",
                "m_string",
                "active",
                "region",
                "created_at",
                "unresolved",
            ]
        );
        assert_eq!(suggested.columns[0].logical_type, LogicalType::Integer);
        assert_eq!(suggested.columns[1].logical_type, LogicalType::Float);
        assert!(!suggested.columns[0].nullable);
        assert!(suggested.columns[1].nullable);
        assert_eq!(suggested.columns[0].constraints.numeric_range, None);
        assert_eq!(suggested.columns[1].constraints.numeric_range, None);
        assert_eq!(suggested.columns[2].constraints.allowed_values, None);
        assert_eq!(suggested.columns[3].constraints.allowed_values, None);
        assert_eq!(
            suggested.columns[4].constraints.allowed_values,
            Some(vec![
                SuggestedValue::String("South".to_string()),
                SuggestedValue::String("North".to_string()),
                SuggestedValue::String("West".to_string()),
            ])
        );
        assert_eq!(suggested.columns[5].constraints.numeric_range, None);
        assert_eq!(suggested.columns[5].constraints.allowed_values, None);
        assert_eq!(suggested.columns[6].logical_type, LogicalType::Unknown);
        assert!(suggested.columns[6].nullable);
        assert_eq!(suggested.columns[6].constraints.numeric_range, None);
        assert_eq!(suggested.columns[6].constraints.allowed_values, None);
        assert_eq!(
            suggested
                .column("region")
                .map(|column| &column.logical_type),
            Some(&LogicalType::Categorical)
        );
        assert_eq!(suggested.column("missing"), None);
    }

    #[test]
    fn suggested_conversion_leaves_empty_and_unretained_categories_unconstrained() {
        let observed = ObservedDatasetSchema::new(
            51,
            vec![
                ObservedColumnSchema::new(
                    "empty".to_string(),
                    LogicalType::Categorical,
                    true,
                    0,
                    None,
                    Some(Vec::new()),
                ),
                ObservedColumnSchema::new(
                    "high_cardinality".to_string(),
                    LogicalType::Categorical,
                    false,
                    51,
                    None,
                    None,
                ),
            ],
        );

        let suggested = suggested_schema_from_observed(&observed);

        assert_eq!(suggested.columns[0].constraints.allowed_values, None);
        assert_eq!(suggested.columns[1].constraints.allowed_values, None);
    }

    #[test]
    fn profiling_to_observed_to_suggested_integrates_without_reprofiling() {
        let input = DatasetInput::new(vec![
            input_column(
                "id",
                LogicalType::Integer,
                vec![
                    ProfileValue::Integer(1),
                    ProfileValue::Integer(2),
                    ProfileValue::Integer(3),
                ],
            ),
            input_column(
                "region",
                LogicalType::Categorical,
                vec![
                    ProfileValue::String("South".to_string()),
                    ProfileValue::String("North".to_string()),
                    ProfileValue::String("South".to_string()),
                ],
            ),
            input_column(
                "sales",
                LogicalType::Float,
                vec![
                    ProfileValue::Float(10.0),
                    ProfileValue::Float(20.0),
                    ProfileValue::Null,
                ],
            ),
        ]);
        let profile = profile_structure(input.clone()).unwrap();
        let observed = observed_schema_from_profile_and_input(&profile, &input).unwrap();
        let original_observed = observed.clone();

        let suggested = suggested_schema_from_observed(&observed);

        assert_eq!(observed, original_observed);
        assert_eq!(input.columns.len(), 3);
        assert_eq!(input.columns[0].name, "id");
        assert_eq!(input.columns[1].name, "region");
        assert_eq!(
            input.columns[1].values,
            vec![
                ProfileValue::String("South".to_string()),
                ProfileValue::String("North".to_string()),
                ProfileValue::String("South".to_string()),
            ]
        );
        assert_eq!(suggested.column_count(), 3);
        assert_eq!(suggested.columns[0].logical_type, LogicalType::Integer);
        assert!(!suggested.columns[0].nullable);
        assert_eq!(suggested.columns[0].constraints.numeric_range, None);
        assert_eq!(suggested.columns[0].constraints.allowed_values, None);
        assert_eq!(suggested.columns[1].logical_type, LogicalType::Categorical);
        assert_eq!(
            suggested.columns[1].constraints.allowed_values,
            Some(vec![
                SuggestedValue::String("South".to_string()),
                SuggestedValue::String("North".to_string()),
            ])
        );
        assert_eq!(suggested.columns[2].logical_type, LogicalType::Float);
        assert!(suggested.columns[2].nullable);
        assert_eq!(suggested.columns[2].constraints.numeric_range, None);
    }
}

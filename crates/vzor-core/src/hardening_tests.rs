//! Bounded property targets for the pure Rust core.
//!
//! These tests are deliberately independent of PyO3, Python, files, and the
//! network.  They provide deterministic, replayable fuzz-equivalent coverage
//! on every supported CI platform.

use proptest::prelude::*;
use proptest::test_runner::RngSeed;

use crate::{
    comparison::compare_observed_schemas,
    persistence::deserialize_suggested_schema,
    profiling::{profile_structure, ColumnInput, DatasetInput, LogicalType, ProfileValue},
    schema::{observed_schema_from_profile_and_input, suggested_schema_from_observed},
    schema_drift::detect_schema_drift_from_observed_schemas,
    validation::{validate_dataset, ValidationCode, ValidationValue},
};

fn integer_input(name: String, values: Vec<i64>) -> DatasetInput {
    DatasetInput::new(vec![ColumnInput::new(
        name,
        LogicalType::Integer,
        values.into_iter().map(ProfileValue::Integer).collect(),
    )])
}

fn string_input(logical_type: LogicalType, values: Vec<String>) -> DatasetInput {
    DatasetInput::new(vec![ColumnInput::new(
        "value".to_string(),
        logical_type,
        values.into_iter().map(ProfileValue::String).collect(),
    )])
}

fn observed(input: &DatasetInput) -> crate::schema::ObservedDatasetSchema {
    let profile = profile_structure(input).expect("generated inputs are structurally valid");
    observed_schema_from_profile_and_input(&profile, input)
        .expect("profile and its source input remain compatible")
}

proptest! {
    #![proptest_config(ProptestConfig {
        cases: 96,
        failure_persistence: None,
        rng_seed: RngSeed::Fixed(0x56_5A_4F_52_04_07),
        .. ProptestConfig::default()
    })]

    #[test]
    fn numeric_profile_invariants_hold_for_arbitrary_integers(
        name in "[ -~]{0,32}",
        values in prop::collection::vec(any::<i64>(), 0..64),
    ) {
        let input = integer_input(name, values.clone());
        let first = profile_structure(&input).expect("integer input profiles");
        let second = profile_structure(&input).expect("integer input profiles deterministically");
        let column = &first.columns[0];

        prop_assert_eq!(&first, &second);
        prop_assert_eq!(column.count, values.len());
        prop_assert_eq!(column.null_count, 0);
        prop_assert!(column.unique_count <= column.count);

        if values.is_empty() {
            prop_assert!(column.numeric_stats.is_none());
        } else {
            let stats = column.numeric_stats.as_ref().expect("integers are finite");
            prop_assert!(stats.min <= stats.p25);
            prop_assert!(stats.p25 <= stats.p50);
            prop_assert!(stats.p50 <= stats.p75);
            prop_assert!(stats.p75 <= stats.max);
            prop_assert_eq!(stats.median, stats.p50);
            prop_assert!(stats.mean.is_finite());
        }
    }

    #[test]
    fn float_profile_target_never_panics_or_produces_non_finite_statistics(
        values in prop::collection::vec(any::<f64>(), 0..64),
    ) {
        let input = DatasetInput::new(vec![ColumnInput::new(
            "float".to_string(),
            LogicalType::Float,
            values.into_iter().map(ProfileValue::Float).collect(),
        )]);
        let first = profile_structure(&input).expect("float input profiles");
        let second = profile_structure(&input).expect("float input profiles deterministically");

        prop_assert_eq!(&first, &second);
        if let Some(stats) = first.columns[0].numeric_stats.as_ref() {
            prop_assert!(stats.min.is_finite());
            prop_assert!(stats.max.is_finite());
            prop_assert!(stats.mean.is_finite());
            prop_assert!(stats.p25.is_finite());
            prop_assert!(stats.p50.is_finite());
            prop_assert!(stats.p75.is_finite());
        }
    }

    #[test]
    fn string_profile_target_keeps_count_and_unique_bounds(
        values in prop::collection::vec(".{0,32}", 0..64),
    ) {
        let input = string_input(LogicalType::String, values.clone());
        let profile = profile_structure(&input).expect("string input profiles");
        let column = &profile.columns[0];

        prop_assert_eq!(column.count, values.len());
        prop_assert_eq!(column.null_count, 0);
        prop_assert!(column.unique_count <= column.count);
        prop_assert!(column.numeric_stats.is_none());
    }

    #[test]
    fn comparison_and_drift_are_identity_operations_for_same_observation(
        values in prop::collection::vec(any::<i64>(), 0..48),
    ) {
        let input = integer_input("id".to_string(), values);
        let schema = observed(&input);
        let comparison = compare_observed_schemas(&schema, &schema);
        let drift = detect_schema_drift_from_observed_schemas(&schema, &schema);

        prop_assert!(!comparison.has_changes());
        prop_assert!(comparison.columns.iter().all(|column| column.changes.is_empty()));
        prop_assert!(!drift.has_drift());
        prop_assert!(drift.issues.is_empty());
    }

    #[test]
    fn validation_accepts_a_schema_suggested_from_its_same_categorical_input(
        values in prop::collection::vec("[a-z]{0,8}", 0..32),
    ) {
        let input = string_input(LogicalType::Categorical, values);
        let schema = suggested_schema_from_observed(&observed(&input));
        let result = validate_dataset(&input, &schema);

        prop_assert!(result.is_valid());
        prop_assert!(result.issues.is_empty());
    }

    #[test]
    fn invalid_categorical_values_keep_first_appearance_order(
        values in prop::collection::vec(1_u8..5, 0..48),
    ) {
        let received = values
            .iter()
            .map(|value| ((b'A' + *value) as char).to_string())
            .collect::<Vec<_>>();
        let input = string_input(LogicalType::Categorical, received.clone());
        let schema = crate::schema::SuggestedDatasetSchema::new(vec![
            crate::schema::SuggestedColumnSchema::new(
                "value".to_string(),
                LogicalType::Categorical,
                false,
                crate::schema::SuggestedConstraints::new(
                    None,
                    Some(vec![crate::schema::SuggestedValue::String("A".to_string())]),
                ),
            ),
        ]);
        let result = validate_dataset(&input, &schema);
        let observed = result.issues.iter().map(|issue| issue.observed.clone()).collect::<Vec<_>>();
        let mut expected = Vec::new();
        for value in received {
            let value = Some(ValidationValue::String(value));
            if !expected.contains(&value) {
                expected.push(value);
            }
        }

        prop_assert!(result.issues.iter().all(|issue| issue.code == ValidationCode::ValueNotAllowed));
        prop_assert_eq!(observed, expected);
    }

    #[test]
    fn malformed_column_lengths_return_the_existing_error_without_panicking(
        first_len in 0_usize..48,
        extra in 1_usize..48,
    ) {
        let input = DatasetInput::new(vec![
            ColumnInput::new(
                "first".to_string(),
                LogicalType::Integer,
                (0..first_len as i64).map(ProfileValue::Integer).collect(),
            ),
            ColumnInput::new(
                "second".to_string(),
                LogicalType::Integer,
                (0..(first_len + extra) as i64).map(ProfileValue::Integer).collect(),
            ),
        ]);

        let result = profile_structure(&input);
        prop_assert_eq!(
            result,
            Err(crate::profiling::ProfilingError::ColumnLengthMismatch {
                column: "second".to_string(),
                expected: first_len,
                actual: first_len + extra,
            }),
        );
    }

    #[test]
    fn persistence_parser_target_is_total_and_deterministic(content in ".{0,256}") {
        let first = deserialize_suggested_schema(&content);
        let second = deserialize_suggested_schema(&content);

        prop_assert_eq!(first.is_ok(), second.is_ok());
    }
}

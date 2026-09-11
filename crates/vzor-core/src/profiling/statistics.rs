use super::{LogicalType, NumericStats, ProfileValue, ProfilingError};

/// Calculates basic statistics for columns declared as Integer or Float.
///
/// Null and non-finite float values remain part of structural profiling but
/// are excluded from these calculations. Integer values are promoted to f64
/// when the declared type is Float.
pub(crate) fn calculate_numeric_stats(
    column_name: &str,
    logical_type: &LogicalType,
    values: &[ProfileValue],
) -> Result<Option<NumericStats>, ProfilingError> {
    let is_integer = matches!(logical_type, LogicalType::Integer);
    let is_float = matches!(logical_type, LogicalType::Float);

    if !is_integer && !is_float {
        return Ok(None);
    }

    let mut numeric_values = Vec::new();
    for value in values {
        match (logical_type, value) {
            (_, ProfileValue::Null) => {}
            (LogicalType::Integer, ProfileValue::Integer(value)) => {
                numeric_values.push(*value as f64);
            }
            (LogicalType::Float, ProfileValue::Integer(value)) => {
                numeric_values.push(*value as f64);
            }
            (LogicalType::Float, ProfileValue::Float(value)) if value.is_finite() => {
                numeric_values.push(*value);
            }
            (LogicalType::Float, ProfileValue::Float(_)) => {}
            (_, value) => {
                return Err(ProfilingError::ValueTypeMismatch {
                    column: column_name.to_string(),
                    expected: logical_type.clone(),
                    actual: value_type_name(value).to_string(),
                });
            }
        }
    }

    if numeric_values.is_empty() {
        return Ok(None);
    }

    numeric_values.sort_by(f64::total_cmp);

    let min = numeric_values[0];
    let max = numeric_values[numeric_values.len() - 1];
    let mean = finite_mean(&numeric_values, min, max);
    let median = percentile(&numeric_values, 0.50).expect("non-empty values were checked");
    let p25 = percentile(&numeric_values, 0.25).expect("non-empty values were checked");
    let p50 = percentile(&numeric_values, 0.50).expect("non-empty values were checked");
    let p75 = percentile(&numeric_values, 0.75).expect("non-empty values were checked");

    Ok(Some(NumericStats {
        min,
        max,
        mean,
        median,
        p25,
        p50,
        p75,
    }))
}

fn finite_mean(values: &[f64], min: f64, max: f64) -> f64 {
    let scale = min.abs().max(max.abs());
    if scale == 0.0 {
        return 0.0;
    }

    let normalized_sum = values.iter().map(|value| value / scale).sum::<f64>();
    normalized_sum / values.len() as f64 * scale
}

fn percentile(sorted: &[f64], q: f64) -> Option<f64> {
    if sorted.is_empty() {
        return None;
    }

    let position = q * (sorted.len() - 1) as f64;
    let lower = position.floor() as usize;
    let upper = position.ceil() as usize;
    let weight = position - lower as f64;

    Some(sorted[lower] * (1.0 - weight) + sorted[upper] * weight)
}

fn value_type_name(value: &ProfileValue) -> &'static str {
    match value {
        ProfileValue::Null => "Null",
        ProfileValue::Integer(_) => "Integer",
        ProfileValue::Float(_) => "Float",
        ProfileValue::Boolean(_) => "Boolean",
        ProfileValue::String(_) => "String",
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn column(
        name: &str,
        logical_type: LogicalType,
        values: Vec<ProfileValue>,
    ) -> super::super::ColumnInput {
        super::super::ColumnInput::new(name.to_string(), logical_type, values)
    }

    fn approx_eq(actual: f64, expected: f64) {
        assert!((actual - expected).abs() < 1e-10, "{actual} != {expected}");
    }

    fn profile_for(
        logical_type: LogicalType,
        values: Vec<ProfileValue>,
    ) -> Result<super::super::ColumnProfile, ProfilingError> {
        super::super::profile_structure(super::super::DatasetInput::new(vec![column(
            "value",
            logical_type,
            values,
        )]))
        .map(|profile| profile.columns.into_iter().next().unwrap())
    }

    #[test]
    fn integer_statistics_are_calculated() {
        let stats = profile_for(
            LogicalType::Integer,
            vec![
                ProfileValue::Integer(1),
                ProfileValue::Integer(2),
                ProfileValue::Integer(3),
            ],
        )
        .unwrap()
        .numeric_stats
        .unwrap();

        approx_eq(stats.min, 1.0);
        approx_eq(stats.max, 3.0);
        approx_eq(stats.mean, 2.0);
        approx_eq(stats.median, 2.0);
        approx_eq(stats.p25, 1.5);
        approx_eq(stats.p50, 2.0);
        approx_eq(stats.p75, 2.5);
    }

    #[test]
    fn even_integer_count_uses_interpolated_median() {
        let stats = profile_for(
            LogicalType::Integer,
            (1..=4).map(ProfileValue::Integer).collect(),
        )
        .unwrap()
        .numeric_stats
        .unwrap();

        approx_eq(stats.median, 2.5);
        approx_eq(stats.p50, stats.median);
        approx_eq(stats.p25, 1.75);
        approx_eq(stats.p75, 3.25);
    }

    #[test]
    fn float_statistics_and_integer_promotion_work() {
        let stats = profile_for(
            LogicalType::Float,
            vec![
                ProfileValue::Integer(1),
                ProfileValue::Float(2.5),
                ProfileValue::Integer(4),
            ],
        )
        .unwrap()
        .numeric_stats
        .unwrap();

        approx_eq(stats.min, 1.0);
        approx_eq(stats.max, 4.0);
        approx_eq(stats.mean, 2.5);
        approx_eq(stats.median, 2.5);
    }

    #[test]
    fn nulls_are_ignored_by_numeric_statistics_but_counted_structurally() {
        let profile = profile_for(
            LogicalType::Integer,
            vec![
                ProfileValue::Integer(10),
                ProfileValue::Null,
                ProfileValue::Integer(30),
            ],
        )
        .unwrap();
        let stats = profile.numeric_stats.unwrap();

        assert_eq!(profile.count, 3);
        assert_eq!(profile.null_count, 1);
        assert_eq!(profile.unique_count, 2);
        approx_eq(stats.mean, 20.0);
        approx_eq(stats.median, 20.0);
    }

    #[test]
    fn non_numeric_columns_have_no_numeric_statistics() {
        for logical_type in [
            LogicalType::String,
            LogicalType::Boolean,
            LogicalType::Categorical,
            LogicalType::Datetime,
            LogicalType::Unknown,
        ] {
            let profile = profile_for(
                logical_type,
                vec![ProfileValue::Integer(1), ProfileValue::Integer(2)],
            )
            .unwrap();

            assert_eq!(profile.numeric_stats, None);
        }
    }

    #[test]
    fn no_finite_numeric_values_produce_no_statistics() {
        let profile = profile_for(
            LogicalType::Float,
            vec![
                ProfileValue::Null,
                ProfileValue::Float(f64::NAN),
                ProfileValue::Float(f64::INFINITY),
                ProfileValue::Float(f64::NEG_INFINITY),
            ],
        )
        .unwrap();

        assert_eq!(profile.count, 4);
        assert_eq!(profile.null_count, 1);
        assert_eq!(profile.unique_count, 3);
        assert_eq!(profile.numeric_stats, None);
    }

    #[test]
    fn non_finite_floats_are_excluded_from_statistics() {
        let stats = profile_for(
            LogicalType::Float,
            vec![
                ProfileValue::Float(10.0),
                ProfileValue::Float(f64::NAN),
                ProfileValue::Float(20.0),
                ProfileValue::Float(f64::INFINITY),
                ProfileValue::Float(f64::NEG_INFINITY),
            ],
        )
        .unwrap()
        .numeric_stats
        .unwrap();

        approx_eq(stats.min, 10.0);
        approx_eq(stats.max, 20.0);
        approx_eq(stats.mean, 15.0);
    }

    #[test]
    fn integer_column_rejects_float_and_string_values() {
        let float_result = profile_for(LogicalType::Integer, vec![ProfileValue::Float(1.0)]);
        let string_result = profile_for(
            LogicalType::Integer,
            vec![ProfileValue::String("1".to_string())],
        );

        assert_eq!(
            float_result,
            Err(ProfilingError::ValueTypeMismatch {
                column: "value".to_string(),
                expected: LogicalType::Integer,
                actual: "Float".to_string(),
            })
        );
        assert_eq!(
            string_result,
            Err(ProfilingError::ValueTypeMismatch {
                column: "value".to_string(),
                expected: LogicalType::Integer,
                actual: "String".to_string(),
            })
        );
    }

    #[test]
    fn float_column_accepts_integer_but_rejects_non_numeric_values() {
        let valid = profile_for(LogicalType::Float, vec![ProfileValue::Integer(1)]);
        let boolean_result = profile_for(LogicalType::Float, vec![ProfileValue::Boolean(true)]);
        let string_result = profile_for(
            LogicalType::Float,
            vec![ProfileValue::String("1".to_string())],
        );

        assert!(valid.is_ok());
        assert_eq!(
            boolean_result,
            Err(ProfilingError::ValueTypeMismatch {
                column: "value".to_string(),
                expected: LogicalType::Float,
                actual: "Boolean".to_string(),
            })
        );
        assert_eq!(
            string_result,
            Err(ProfilingError::ValueTypeMismatch {
                column: "value".to_string(),
                expected: LogicalType::Float,
                actual: "String".to_string(),
            })
        );
    }

    #[test]
    fn negative_and_repeated_values_are_supported() {
        let stats = profile_for(
            LogicalType::Float,
            vec![
                ProfileValue::Float(-10.0),
                ProfileValue::Float(5.0),
                ProfileValue::Float(5.0),
                ProfileValue::Float(-2.0),
            ],
        )
        .unwrap()
        .numeric_stats
        .unwrap();

        approx_eq(stats.min, -10.0);
        approx_eq(stats.max, 5.0);
        approx_eq(stats.mean, -0.5);
        approx_eq(stats.median, 1.5);
    }

    #[test]
    fn single_value_populates_all_statistics() {
        let stats = profile_for(LogicalType::Integer, vec![ProfileValue::Integer(7)])
            .unwrap()
            .numeric_stats
            .unwrap();

        for value in [
            stats.min,
            stats.max,
            stats.mean,
            stats.median,
            stats.p25,
            stats.p50,
            stats.p75,
        ] {
            approx_eq(value, 7.0);
        }
    }

    #[test]
    fn finite_values_do_not_overflow_the_mean_during_summation() {
        let stats = profile_for(
            LogicalType::Float,
            vec![ProfileValue::Float(f64::MAX), ProfileValue::Float(f64::MAX)],
        )
        .unwrap()
        .numeric_stats
        .unwrap();

        assert!(stats.mean.is_finite());
        assert_eq!(stats.mean, f64::MAX);
    }

    #[test]
    fn opposite_extreme_values_keep_interpolated_statistics_finite() {
        let stats = profile_for(
            LogicalType::Float,
            vec![
                ProfileValue::Float(-f64::MAX),
                ProfileValue::Float(f64::MAX),
            ],
        )
        .unwrap()
        .numeric_stats
        .unwrap();

        assert_eq!(stats.mean, 0.0);
        assert_eq!(stats.median, 0.0);
        assert!(((stats.p25 - (-f64::MAX / 2.0)) / stats.p25).abs() < 1e-15);
        assert_eq!(stats.p50, stats.median);
        assert!(((stats.p75 - (f64::MAX / 2.0)) / stats.p75).abs() < 1e-15);
    }

    #[test]
    fn original_values_keep_their_order() {
        let values = vec![
            ProfileValue::Integer(3),
            ProfileValue::Integer(1),
            ProfileValue::Integer(2),
        ];
        let original = values.clone();

        let _ = calculate_numeric_stats("value", &LogicalType::Integer, &values).unwrap();

        assert_eq!(values, original);
    }

    #[test]
    fn mismatched_lengths_still_return_the_existing_error() {
        let result = super::super::profile_structure(super::super::DatasetInput::new(vec![
            column(
                "first",
                LogicalType::Integer,
                vec![ProfileValue::Integer(1)],
            ),
            column("second", LogicalType::Integer, vec![]),
        ]));

        assert_eq!(
            result,
            Err(ProfilingError::ColumnLengthMismatch {
                column: "second".to_string(),
                expected: 1,
                actual: 0,
            })
        );
    }
}

use std::collections::HashSet;

use super::{
    statistics::calculate_numeric_stats, ColumnProfile, DatasetProfile, LogicalType, ProfileValue,
};

/// Input metadata and values for one column during the temporary profiling step.
pub struct ColumnInput {
    pub name: String,
    pub logical_type: LogicalType,
    pub values: Vec<ProfileValue>,
}

impl ColumnInput {
    pub fn new(name: String, logical_type: LogicalType, values: Vec<ProfileValue>) -> Self {
        Self {
            name,
            logical_type,
            values,
        }
    }
}

/// Minimal dataset input for profiling. Row count is derived from column lengths.
pub struct DatasetInput {
    pub columns: Vec<ColumnInput>,
}

impl DatasetInput {
    pub fn new(columns: Vec<ColumnInput>) -> Self {
        Self { columns }
    }
}

/// Structural profiling errors that can be detected before processing values.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum ProfilingError {
    ColumnLengthMismatch {
        column: String,
        expected: usize,
        actual: usize,
    },
    ValueTypeMismatch {
        column: String,
        expected: LogicalType,
        actual: String,
    },
}

/// Profiles rows, columns, nulls and non-null unique values.
///
/// `ProfileValue::Null` is the only null representation. Empty strings and
/// values such as zero, false or NaN are not treated as null. Null values are
/// excluded from `unique_count`, while `count` includes every position.
pub fn profile_structure(input: &DatasetInput) -> Result<DatasetProfile, ProfilingError> {
    let row_count = input
        .columns
        .first()
        .map_or(0, |column| column.values.len());

    for column in &input.columns {
        if column.values.len() != row_count {
            return Err(ProfilingError::ColumnLengthMismatch {
                column: column.name.clone(),
                expected: row_count,
                actual: column.values.len(),
            });
        }
    }

    let columns = input
        .columns
        .iter()
        .map(|column| {
            let null_count = count_nulls(&column.values);
            let unique_count = count_unique(&column.values);
            let numeric_stats =
                calculate_numeric_stats(&column.name, &column.logical_type, &column.values)?;

            Ok(ColumnProfile::new(
                column.name.clone(),
                column.logical_type.clone(),
                row_count,
                null_count,
                unique_count,
                numeric_stats,
            ))
        })
        .collect::<Result<Vec<_>, ProfilingError>>()?;

    Ok(DatasetProfile::new(row_count, columns))
}

fn count_nulls(values: &[ProfileValue]) -> usize {
    values
        .iter()
        .filter(|value| matches!(value, ProfileValue::Null))
        .count()
}

fn count_unique(values: &[ProfileValue]) -> usize {
    values
        .iter()
        .filter_map(UniqueValue::from_profile_value)
        .collect::<HashSet<_>>()
        .len()
}

#[derive(Debug, PartialEq, Eq, Hash)]
enum UniqueValue<'a> {
    Integer(i64),
    Float(u64),
    Boolean(bool),
    String(&'a str),
}

impl<'a> UniqueValue<'a> {
    fn from_profile_value(value: &'a ProfileValue) -> Option<Self> {
        match value {
            ProfileValue::Null => None,
            ProfileValue::Integer(value) => Some(Self::Integer(*value)),
            ProfileValue::Float(value) => Some(Self::Float(normalize_float(*value))),
            ProfileValue::Boolean(value) => Some(Self::Boolean(*value)),
            ProfileValue::String(value) => Some(Self::String(value.as_str())),
        }
    }
}

fn normalize_float(value: f64) -> u64 {
    if value.is_nan() {
        f64::NAN.to_bits()
    } else if value == 0.0 {
        0.0f64.to_bits()
    } else {
        value.to_bits()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn column(name: &str, logical_type: LogicalType, values: Vec<ProfileValue>) -> ColumnInput {
        ColumnInput::new(name.to_string(), logical_type, values)
    }

    fn profile_for(values: Vec<ProfileValue>) -> ColumnProfile {
        profile_structure(&DatasetInput::new(vec![column(
            "value",
            LogicalType::Unknown,
            values,
        )]))
        .unwrap()
        .columns
        .remove(0)
    }

    #[test]
    fn counts_nulls_and_excludes_them_from_unique_values() {
        let profile = profile_for(vec![
            ProfileValue::Integer(1),
            ProfileValue::Null,
            ProfileValue::Integer(1),
            ProfileValue::Integer(2),
            ProfileValue::Null,
        ]);

        assert_eq!(profile.count, 5);
        assert_eq!(profile.null_count, 2);
        assert_eq!(profile.unique_count, 2);
    }

    #[test]
    fn only_explicit_null_counts_as_null() {
        let profile = profile_for(vec![
            ProfileValue::String(String::new()),
            ProfileValue::String("NULL".to_string()),
            ProfileValue::Float(f64::NAN),
            ProfileValue::Integer(0),
            ProfileValue::Boolean(false),
            ProfileValue::Null,
        ]);

        assert_eq!(profile.null_count, 1);
        assert_eq!(profile.unique_count, 5);
    }

    #[test]
    fn counts_unique_integers_strings_and_booleans() {
        let profile = profile_structure(&DatasetInput::new(vec![
            column(
                "integer",
                LogicalType::Integer,
                vec![
                    ProfileValue::Integer(1),
                    ProfileValue::Integer(1),
                    ProfileValue::Integer(2),
                ],
            ),
            column(
                "string",
                LogicalType::String,
                vec![
                    ProfileValue::String("A".to_string()),
                    ProfileValue::String("A".to_string()),
                    ProfileValue::String("B".to_string()),
                ],
            ),
            column(
                "boolean",
                LogicalType::Boolean,
                vec![
                    ProfileValue::Boolean(true),
                    ProfileValue::Boolean(false),
                    ProfileValue::Boolean(true),
                ],
            ),
        ]))
        .unwrap();

        assert_eq!(profile.column_count(), 3);
        assert_eq!(profile.columns[0].unique_count, 2);
        assert_eq!(profile.columns[1].unique_count, 2);
        assert_eq!(profile.columns[2].unique_count, 2);
    }

    #[test]
    fn counts_repeated_floats_and_normalizes_zero() {
        let profile = profile_for(vec![
            ProfileValue::Float(1.0),
            ProfileValue::Float(1.0),
            ProfileValue::Float(2.0),
            ProfileValue::Float(0.0),
            ProfileValue::Float(-0.0),
        ]);

        assert_eq!(profile.unique_count, 3);
    }

    #[test]
    fn special_float_cardinality_is_stable() {
        let profile = profile_for(vec![
            ProfileValue::Float(f64::NAN),
            ProfileValue::Float(f64::from_bits(0x7ff8_0000_0000_0001)),
            ProfileValue::Float(f64::INFINITY),
            ProfileValue::Float(f64::NEG_INFINITY),
            ProfileValue::Float(0.0),
            ProfileValue::Float(-0.0),
            ProfileValue::Float(1.0),
            ProfileValue::Null,
        ]);

        assert_eq!(profile.count, 8);
        assert_eq!(profile.null_count, 1);
        assert_eq!(profile.unique_count, 5);
    }

    #[test]
    fn all_null_values_have_zero_unique_count() {
        let profile = profile_for(vec![ProfileValue::Null, ProfileValue::Null]);

        assert_eq!(profile.count, 2);
        assert_eq!(profile.null_count, 2);
        assert_eq!(profile.unique_count, 0);
    }

    #[test]
    fn one_repeated_value_has_one_unique_value() {
        let profile = profile_for(vec![
            ProfileValue::String("same".to_string()),
            ProfileValue::String("same".to_string()),
        ]);

        assert_eq!(profile.unique_count, 1);
    }

    #[test]
    fn preserves_multiple_columns_and_their_counts() {
        let profile = profile_structure(&DatasetInput::new(vec![
            column(
                "id",
                LogicalType::Integer,
                vec![
                    ProfileValue::Integer(1),
                    ProfileValue::Null,
                    ProfileValue::Integer(1),
                ],
            ),
            column(
                "name",
                LogicalType::String,
                vec![
                    ProfileValue::String("A".to_string()),
                    ProfileValue::String("B".to_string()),
                    ProfileValue::String("A".to_string()),
                ],
            ),
        ]))
        .unwrap();

        assert_eq!(profile.row_count, 3);
        assert_eq!(profile.column_count(), 2);
        assert_eq!(profile.columns[0].name, "id");
        assert_eq!(profile.columns[0].count, 3);
        assert_eq!(profile.columns[0].null_count, 1);
        assert_eq!(profile.columns[0].unique_count, 1);
        assert_eq!(profile.columns[1].name, "name");
        assert_eq!(profile.columns[1].unique_count, 2);
    }

    #[test]
    fn rejects_columns_with_different_lengths() {
        let result = profile_structure(&DatasetInput::new(vec![
            column(
                "first",
                LogicalType::Integer,
                vec![ProfileValue::Integer(1)],
            ),
            column(
                "second",
                LogicalType::String,
                vec![
                    ProfileValue::String("a".to_string()),
                    ProfileValue::String("b".to_string()),
                ],
            ),
        ]));

        assert_eq!(
            result,
            Err(ProfilingError::ColumnLengthMismatch {
                column: "second".to_string(),
                expected: 1,
                actual: 2,
            })
        );
    }

    #[test]
    fn empty_dataset_is_supported() {
        let profile = profile_structure(&DatasetInput::new(Vec::new())).unwrap();

        assert_eq!(profile.row_count, 0);
        assert_eq!(profile.column_count(), 0);
    }

    #[test]
    fn zero_rows_with_columns_is_supported() {
        let profile = profile_structure(&DatasetInput::new(vec![
            column("empty", LogicalType::Categorical, Vec::new()),
            column("date", LogicalType::Datetime, Vec::new()),
        ]))
        .unwrap();

        assert_eq!(profile.row_count, 0);
        assert_eq!(profile.column_count(), 2);
        assert!(profile.columns.iter().all(|column| {
            column.count == 0 && column.null_count == 0 && column.unique_count == 0
        }));
    }

    #[test]
    fn profiling_borrows_input_without_consuming_or_mutating_values() {
        let input = DatasetInput::new(vec![column(
            "label",
            LogicalType::String,
            vec![
                ProfileValue::String("área".to_string()),
                ProfileValue::Null,
                ProfileValue::String("東京".to_string()),
            ],
        )]);

        let profile = profile_structure(&input).unwrap();

        assert_eq!(profile.columns[0].unique_count, 2);
        assert_eq!(input.columns[0].name, "label");
        assert_eq!(
            input.columns[0].values,
            vec![
                ProfileValue::String("área".to_string()),
                ProfileValue::Null,
                ProfileValue::String("東京".to_string()),
            ]
        );
    }
}

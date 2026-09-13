use std::collections::{HashMap, HashSet};

use crate::schema::{ObservedColumnSchema, ObservedDatasetSchema};

use super::{ColumnComparison, ComparisonChangeCode, ComparisonResult, ComparisonStatus};

/// Compares two observed dataset schemas by exact column name.
///
/// The result retains the before column order, followed by columns that exist
/// only in the after schema in their after order. Inputs are expected to have
/// unique column names.
pub fn compare_observed_schemas(
    before: &ObservedDatasetSchema,
    after: &ObservedDatasetSchema,
) -> ComparisonResult {
    let mut columns = Vec::with_capacity(before.columns.len() + after.columns.len());
    visit_comparison_columns(before, after, |column| {
        columns.push(ColumnComparison {
            name: column.name.to_string(),
            status: column.status,
            before: column.before.cloned(),
            after: column.after.cloned(),
            changes: column.changes,
        });
    });

    ComparisonResult {
        before_row_count: before.row_count,
        after_row_count: after.row_count,
        columns,
    }
}

/// One ephemeral factual column comparison used by internal consumers.
///
/// The references are valid only for the comparison traversal. Public
/// `ComparisonResult` snapshots them into owned values; consumers that need
/// only facts, such as schema drift, can avoid that allocation.
pub(crate) struct ComparisonColumnFacts<'a> {
    pub name: &'a str,
    pub status: ComparisonStatus,
    pub before: Option<&'a ObservedColumnSchema>,
    pub after: Option<&'a ObservedColumnSchema>,
    pub changes: Vec<ComparisonChangeCode>,
}

/// Visit factual column comparisons in the public deterministic order.
pub(crate) fn visit_comparison_columns<'a>(
    before: &'a ObservedDatasetSchema,
    after: &'a ObservedDatasetSchema,
    mut visit: impl FnMut(ComparisonColumnFacts<'a>),
) {
    let after_by_name = after
        .columns
        .iter()
        .map(|column| (column.name.as_str(), column))
        .collect::<HashMap<_, _>>();
    let before_names = before
        .columns
        .iter()
        .map(|column| column.name.as_str())
        .collect::<HashSet<_>>();

    for before_column in &before.columns {
        match after_by_name.get(before_column.name.as_str()) {
            Some(after_column) => {
                let changes = detect_changes(before_column, after_column);
                let status = if changes.is_empty() {
                    ComparisonStatus::Unchanged
                } else {
                    ComparisonStatus::Changed
                };

                visit(ComparisonColumnFacts {
                    name: before_column.name.as_str(),
                    status,
                    before: Some(before_column),
                    after: Some(*after_column),
                    changes,
                });
            }
            None => visit(ComparisonColumnFacts {
                name: before_column.name.as_str(),
                status: ComparisonStatus::Removed,
                before: Some(before_column),
                after: None,
                changes: Vec::new(),
            }),
        }
    }

    for after_column in &after.columns {
        if !before_names.contains(after_column.name.as_str()) {
            visit(ComparisonColumnFacts {
                name: after_column.name.as_str(),
                status: ComparisonStatus::Added,
                before: None,
                after: Some(after_column),
                changes: Vec::new(),
            });
        }
    }
}

fn detect_changes(
    before: &ObservedColumnSchema,
    after: &ObservedColumnSchema,
) -> Vec<ComparisonChangeCode> {
    let mut changes = Vec::with_capacity(5);

    if before.logical_type != after.logical_type {
        changes.push(ComparisonChangeCode::LogicalTypeChanged);
    }
    if before.observed_nullable != after.observed_nullable {
        changes.push(ComparisonChangeCode::NullabilityChanged);
    }
    if before.observed_unique_count != after.observed_unique_count {
        changes.push(ComparisonChangeCode::UniqueCountChanged);
    }
    if before.observed_range != after.observed_range {
        changes.push(ComparisonChangeCode::RangeChanged);
    }
    if before.observed_values != after.observed_values {
        changes.push(ComparisonChangeCode::ObservedValuesChanged);
    }

    changes
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::{
        profiling::LogicalType,
        schema::{ObservedRange, ObservedValue},
    };

    fn column(
        name: &str,
        logical_type: LogicalType,
        nullable: bool,
        unique_count: usize,
        range: Option<ObservedRange>,
        values: Option<Vec<ObservedValue>>,
    ) -> ObservedColumnSchema {
        ObservedColumnSchema::new(
            name.to_string(),
            logical_type,
            nullable,
            unique_count,
            range,
            values,
        )
    }

    fn schema(row_count: usize, columns: Vec<ObservedColumnSchema>) -> ObservedDatasetSchema {
        ObservedDatasetSchema::new(row_count, columns)
    }

    fn basic_column(name: &str) -> ObservedColumnSchema {
        column(name, LogicalType::Integer, false, 3, None, None)
    }

    #[test]
    fn empty_schemas_have_no_changes() {
        let result = compare_observed_schemas(&schema(0, vec![]), &schema(0, vec![]));

        assert!(result.columns.is_empty());
        assert!(!result.has_changes());
        assert!(!result.row_count_changed());
        assert_eq!(result.column_count_before(), 0);
        assert_eq!(result.column_count_after(), 0);
    }

    #[test]
    fn row_count_only_change_keeps_columns_unchanged() {
        let before = schema(100, vec![basic_column("id")]);
        let after = schema(120, vec![basic_column("id")]);
        let result = compare_observed_schemas(&before, &after);

        assert!(result.row_count_changed());
        assert!(result.has_changes());
        assert_eq!(result.changed_count(), 0);
        assert_eq!(result.columns[0].status, ComparisonStatus::Unchanged);
    }

    #[test]
    fn reordered_columns_are_unchanged_and_keep_before_order() {
        let before = schema(
            3,
            vec![
                basic_column("id"),
                basic_column("sales"),
                basic_column("region"),
            ],
        );
        let after = schema(
            3,
            vec![
                basic_column("region"),
                basic_column("id"),
                basic_column("sales"),
            ],
        );
        let result = compare_observed_schemas(&before, &after);

        assert_eq!(
            result
                .columns
                .iter()
                .map(|column| &column.name)
                .collect::<Vec<_>>(),
            vec!["id", "sales", "region"]
        );
        assert!(result
            .columns
            .iter()
            .all(|column| column.status == ComparisonStatus::Unchanged));
    }

    #[test]
    fn added_and_removed_columns_have_one_snapshot_and_no_change_codes() {
        let before = schema(1, vec![basic_column("id"), basic_column("legacy")]);
        let after = schema(1, vec![basic_column("id"), basic_column("region")]);
        let result = compare_observed_schemas(&before, &after);

        assert_eq!(
            result
                .columns
                .iter()
                .map(|column| &column.name)
                .collect::<Vec<_>>(),
            vec!["id", "legacy", "region"]
        );
        assert_eq!(result.columns[1].status, ComparisonStatus::Removed);
        assert!(result.columns[1].before.is_some());
        assert!(result.columns[1].after.is_none());
        assert!(result.columns[1].changes.is_empty());
        assert_eq!(result.columns[2].status, ComparisonStatus::Added);
        assert!(result.columns[2].before.is_none());
        assert!(result.columns[2].after.is_some());
        assert!(result.columns[2].changes.is_empty());
    }

    #[test]
    fn added_columns_follow_before_columns_in_after_order() {
        let before = schema(1, vec![basic_column("id"), basic_column("sales")]);
        let after = schema(
            1,
            vec![
                basic_column("region"),
                basic_column("sales"),
                basic_column("id"),
                basic_column("channel"),
            ],
        );
        let result = compare_observed_schemas(&before, &after);

        assert_eq!(
            result
                .columns
                .iter()
                .map(|column| &column.name)
                .collect::<Vec<_>>(),
            vec!["id", "sales", "region", "channel"]
        );
    }

    #[test]
    fn every_observed_property_is_reported_in_canonical_order() {
        let before = schema(
            1,
            vec![column(
                "value",
                LogicalType::Integer,
                false,
                1,
                Some(ObservedRange::new(1.0, 10.0)),
                Some(vec![ObservedValue::String("A".to_string())]),
            )],
        );
        let after = schema(
            1,
            vec![column(
                "value",
                LogicalType::Float,
                true,
                2,
                Some(ObservedRange::new(1.0, 20.0)),
                Some(vec![ObservedValue::String("B".to_string())]),
            )],
        );
        let result = compare_observed_schemas(&before, &after);

        assert_eq!(result.columns[0].status, ComparisonStatus::Changed);
        assert_eq!(
            result.columns[0].changes,
            vec![
                ComparisonChangeCode::LogicalTypeChanged,
                ComparisonChangeCode::NullabilityChanged,
                ComparisonChangeCode::UniqueCountChanged,
                ComparisonChangeCode::RangeChanged,
                ComparisonChangeCode::ObservedValuesChanged,
            ]
        );
    }

    #[test]
    fn range_presence_and_observed_value_structure_are_compared_exactly() {
        let before = schema(
            1,
            vec![
                column(
                    "range",
                    LogicalType::Integer,
                    false,
                    1,
                    Some(ObservedRange::new(1.0, 10.0)),
                    None,
                ),
                column(
                    "values",
                    LogicalType::Categorical,
                    false,
                    2,
                    None,
                    Some(vec![
                        ObservedValue::String("A".to_string()),
                        ObservedValue::String("B".to_string()),
                    ]),
                ),
                column("none_empty", LogicalType::String, false, 0, None, None),
                column("range_appears", LogicalType::Integer, false, 1, None, None),
                column(
                    "boolean",
                    LogicalType::Boolean,
                    false,
                    1,
                    None,
                    Some(vec![ObservedValue::Boolean(true)]),
                ),
            ],
        );
        let after = schema(
            1,
            vec![
                column("range", LogicalType::Integer, false, 1, None, None),
                column(
                    "values",
                    LogicalType::Categorical,
                    false,
                    2,
                    None,
                    Some(vec![
                        ObservedValue::String("B".to_string()),
                        ObservedValue::String("A".to_string()),
                    ]),
                ),
                column(
                    "none_empty",
                    LogicalType::String,
                    false,
                    0,
                    None,
                    Some(vec![]),
                ),
                column(
                    "range_appears",
                    LogicalType::Integer,
                    false,
                    1,
                    Some(ObservedRange::new(1.0, 10.0)),
                    None,
                ),
                column(
                    "boolean",
                    LogicalType::Boolean,
                    false,
                    2,
                    None,
                    Some(vec![
                        ObservedValue::Boolean(true),
                        ObservedValue::Boolean(false),
                    ]),
                ),
            ],
        );
        let result = compare_observed_schemas(&before, &after);

        assert_eq!(
            result.columns[0].changes,
            vec![ComparisonChangeCode::RangeChanged]
        );
        assert_eq!(
            result.columns[1].changes,
            vec![ComparisonChangeCode::ObservedValuesChanged]
        );
        assert_eq!(
            result.columns[2].changes,
            vec![ComparisonChangeCode::ObservedValuesChanged]
        );
        assert_eq!(
            result.columns[3].changes,
            vec![ComparisonChangeCode::RangeChanged]
        );
        assert_eq!(
            result.columns[4].changes,
            vec![
                ComparisonChangeCode::UniqueCountChanged,
                ComparisonChangeCode::ObservedValuesChanged,
            ]
        );
    }

    #[test]
    fn snapshots_are_owned_inputs_are_unchanged_and_results_are_deterministic() {
        let before = schema(
            2,
            vec![column(
                "sales",
                LogicalType::Integer,
                false,
                2,
                Some(ObservedRange::new(1.0, 10.0)),
                None,
            )],
        );
        let after = schema(
            2,
            vec![column(
                "sales",
                LogicalType::Float,
                true,
                3,
                Some(ObservedRange::new(1.0, 20.0)),
                Some(vec![ObservedValue::String("new".to_string())]),
            )],
        );
        let before_clone = before.clone();
        let after_clone = after.clone();

        let first = compare_observed_schemas(&before, &after);
        let second = compare_observed_schemas(&before, &after);

        assert_eq!(before, before_clone);
        assert_eq!(after, after_clone);
        assert_eq!(first, second);
        assert_eq!(first.columns[0].before, Some(before.columns[0].clone()));
        assert_eq!(first.columns[0].after, Some(after.columns[0].clone()));
    }
}

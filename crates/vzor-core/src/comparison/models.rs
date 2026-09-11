use crate::schema::ObservedColumnSchema;

/// Factual presence or change state of one column between two observations.
///
/// This status does not express severity, compatibility, or schema drift.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ComparisonStatus {
    Added,
    Removed,
    Changed,
    Unchanged,
}

/// Factual kind of difference observed between two versions of one column.
///
/// When multiple codes are present, their canonical order is:
/// `LogicalTypeChanged`, `NullabilityChanged`, `UniqueCountChanged`,
/// `RangeChanged`, then `ObservedValuesChanged`. These codes do not express
/// severity, compatibility, or schema drift.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub enum ComparisonChangeCode {
    LogicalTypeChanged,
    NullabilityChanged,
    UniqueCountChanged,
    RangeChanged,
    ObservedValuesChanged,
}

/// Before/after snapshots and factual differences for one column.
///
/// `before` and `after` are owned snapshots so the comparison result outlives
/// its inputs. Added columns have only `after`, removed columns have only
/// `before`, and columns that changed or remained unchanged have both.
/// This model does not express severity, compatibility, or schema drift.
#[derive(Debug, Clone, PartialEq)]
pub struct ColumnComparison {
    pub name: String,
    pub status: ComparisonStatus,
    pub before: Option<ObservedColumnSchema>,
    pub after: Option<ObservedColumnSchema>,
    pub changes: Vec<ComparisonChangeCode>,
}

/// Structured result of comparing two observed dataset schemas.
///
/// It records factual row and column differences only. It does not express
/// severity, compatibility, or schema drift. A future comparison engine will
/// order columns by retaining the BEFORE order first, followed by Added
/// columns in their AFTER order.
#[derive(Debug, Clone, PartialEq)]
pub struct ComparisonResult {
    pub before_row_count: usize,
    pub after_row_count: usize,
    pub columns: Vec<ColumnComparison>,
}

impl ComparisonResult {
    /// Returns whether row count or any column status differs from unchanged.
    pub fn has_changes(&self) -> bool {
        self.row_count_changed()
            || self
                .columns
                .iter()
                .any(|column| column.status != ComparisonStatus::Unchanged)
    }

    /// Returns whether the observed dataset row count changed.
    pub fn row_count_changed(&self) -> bool {
        self.before_row_count != self.after_row_count
    }

    /// Returns the number of columns that exist only in the after snapshot.
    pub fn added_count(&self) -> usize {
        self.count_status(ComparisonStatus::Added)
    }

    /// Returns the number of columns that exist only in the before snapshot.
    pub fn removed_count(&self) -> usize {
        self.count_status(ComparisonStatus::Removed)
    }

    /// Returns the number of columns with factual observed-property changes.
    pub fn changed_count(&self) -> usize {
        self.count_status(ComparisonStatus::Changed)
    }

    /// Returns the number of columns with no compared-property changes.
    pub fn unchanged_count(&self) -> usize {
        self.count_status(ComparisonStatus::Unchanged)
    }

    /// Returns the column count represented by the before snapshot.
    pub fn column_count_before(&self) -> usize {
        self.columns
            .iter()
            .filter(|column| {
                matches!(
                    column.status,
                    ComparisonStatus::Removed
                        | ComparisonStatus::Changed
                        | ComparisonStatus::Unchanged
                )
            })
            .count()
    }

    /// Returns the column count represented by the after snapshot.
    pub fn column_count_after(&self) -> usize {
        self.columns
            .iter()
            .filter(|column| {
                matches!(
                    column.status,
                    ComparisonStatus::Added
                        | ComparisonStatus::Changed
                        | ComparisonStatus::Unchanged
                )
            })
            .count()
    }

    fn count_status(&self, status: ComparisonStatus) -> usize {
        self.columns
            .iter()
            .filter(|column| column.status == status)
            .count()
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::{
        profiling::LogicalType,
        schema::{ObservedRange, ObservedValue},
    };

    fn observed_column(
        name: &str,
        logical_type: LogicalType,
        observed_nullable: bool,
        observed_unique_count: usize,
        observed_range: Option<ObservedRange>,
        observed_values: Option<Vec<ObservedValue>>,
    ) -> ObservedColumnSchema {
        ObservedColumnSchema::new(
            name.to_string(),
            logical_type,
            observed_nullable,
            observed_unique_count,
            observed_range,
            observed_values,
        )
    }

    fn unchanged(name: &str) -> ColumnComparison {
        let snapshot = observed_column(name, LogicalType::Integer, false, 2, None, None);

        ColumnComparison {
            name: name.to_string(),
            status: ComparisonStatus::Unchanged,
            before: Some(snapshot.clone()),
            after: Some(snapshot),
            changes: Vec::new(),
        }
    }

    #[test]
    fn comparison_status_variants_are_copyable_and_distinct() {
        let statuses = [
            ComparisonStatus::Added,
            ComparisonStatus::Removed,
            ComparisonStatus::Changed,
            ComparisonStatus::Unchanged,
        ];
        let copied = statuses[0];

        assert_eq!(copied, ComparisonStatus::Added);
        assert!(statuses.windows(2).all(|pair| pair[0] != pair[1]));
    }

    #[test]
    fn comparison_change_codes_are_distinct() {
        let codes = [
            ComparisonChangeCode::LogicalTypeChanged,
            ComparisonChangeCode::NullabilityChanged,
            ComparisonChangeCode::UniqueCountChanged,
            ComparisonChangeCode::RangeChanged,
            ComparisonChangeCode::ObservedValuesChanged,
        ];

        assert_eq!(codes.len(), 5);
        assert!(codes.windows(2).all(|pair| pair[0] != pair[1]));
    }

    #[test]
    fn unchanged_result_has_no_derived_changes() {
        let result = ComparisonResult {
            before_row_count: 100,
            after_row_count: 100,
            columns: vec![unchanged("id"), unchanged("sales")],
        };

        assert!(!result.has_changes());
        assert!(!result.row_count_changed());
        assert_eq!(result.added_count(), 0);
        assert_eq!(result.removed_count(), 0);
        assert_eq!(result.changed_count(), 0);
        assert_eq!(result.unchanged_count(), 2);
        assert_eq!(result.column_count_before(), 2);
        assert_eq!(result.column_count_after(), 2);
    }

    #[test]
    fn row_count_change_does_not_change_column_statuses() {
        let result = ComparisonResult {
            before_row_count: 100,
            after_row_count: 120,
            columns: vec![unchanged("id"), unchanged("sales")],
        };

        assert!(result.has_changes());
        assert!(result.row_count_changed());
        assert_eq!(result.changed_count(), 0);
        assert_eq!(result.unchanged_count(), 2);
    }

    #[test]
    fn added_column_keeps_only_after_snapshot() {
        let after = observed_column("region", LogicalType::Categorical, true, 3, None, None);
        let result = ComparisonResult {
            before_row_count: 2,
            after_row_count: 2,
            columns: vec![ColumnComparison {
                name: "region".to_string(),
                status: ComparisonStatus::Added,
                before: None,
                after: Some(after.clone()),
                changes: Vec::new(),
            }],
        };

        assert_eq!(result.added_count(), 1);
        assert_eq!(result.column_count_before(), 0);
        assert_eq!(result.column_count_after(), 1);
        assert_eq!(result.columns[0].after, Some(after));
        assert!(result.columns[0].changes.is_empty());
    }

    #[test]
    fn removed_column_keeps_only_before_snapshot() {
        let before = observed_column("legacy", LogicalType::String, false, 2, None, None);
        let result = ComparisonResult {
            before_row_count: 2,
            after_row_count: 2,
            columns: vec![ColumnComparison {
                name: "legacy".to_string(),
                status: ComparisonStatus::Removed,
                before: Some(before.clone()),
                after: None,
                changes: Vec::new(),
            }],
        };

        assert_eq!(result.removed_count(), 1);
        assert_eq!(result.column_count_before(), 1);
        assert_eq!(result.column_count_after(), 0);
        assert_eq!(result.columns[0].before, Some(before));
        assert!(result.columns[0].changes.is_empty());
    }

    #[test]
    fn changed_column_preserves_change_codes_and_snapshots() {
        let before = observed_column("sales", LogicalType::Integer, false, 2, None, None);
        let after = observed_column("sales", LogicalType::Float, true, 2, None, None);
        let result = ComparisonResult {
            before_row_count: 2,
            after_row_count: 2,
            columns: vec![ColumnComparison {
                name: "sales".to_string(),
                status: ComparisonStatus::Changed,
                before: Some(before.clone()),
                after: Some(after.clone()),
                changes: vec![
                    ComparisonChangeCode::LogicalTypeChanged,
                    ComparisonChangeCode::NullabilityChanged,
                ],
            }],
        };

        assert!(result.has_changes());
        assert_eq!(result.changed_count(), 1);
        assert_eq!(result.columns[0].before, Some(before));
        assert_eq!(result.columns[0].after, Some(after));
        assert_eq!(
            result.columns[0].changes,
            vec![
                ComparisonChangeCode::LogicalTypeChanged,
                ComparisonChangeCode::NullabilityChanged,
            ]
        );
    }

    #[test]
    fn unchanged_column_keeps_both_snapshots_without_changes() {
        let column = unchanged("id");

        assert_eq!(column.status, ComparisonStatus::Unchanged);
        assert!(column.before.is_some());
        assert!(column.after.is_some());
        assert!(column.changes.is_empty());
    }

    #[test]
    fn mixed_statuses_derive_counts_and_column_counts() {
        let changed = ColumnComparison {
            name: "sales".to_string(),
            status: ComparisonStatus::Changed,
            before: Some(observed_column(
                "sales",
                LogicalType::Integer,
                false,
                2,
                None,
                None,
            )),
            after: Some(observed_column(
                "sales",
                LogicalType::Float,
                false,
                2,
                None,
                None,
            )),
            changes: vec![ComparisonChangeCode::LogicalTypeChanged],
        };
        let removed = ColumnComparison {
            name: "legacy".to_string(),
            status: ComparisonStatus::Removed,
            before: Some(observed_column(
                "legacy",
                LogicalType::String,
                false,
                2,
                None,
                None,
            )),
            after: None,
            changes: Vec::new(),
        };
        let added = ColumnComparison {
            name: "region".to_string(),
            status: ComparisonStatus::Added,
            before: None,
            after: Some(observed_column(
                "region",
                LogicalType::Categorical,
                false,
                2,
                None,
                None,
            )),
            changes: Vec::new(),
        };
        let result = ComparisonResult {
            before_row_count: 2,
            after_row_count: 2,
            columns: vec![unchanged("id"), changed, removed, added],
        };

        assert_eq!(result.added_count(), 1);
        assert_eq!(result.removed_count(), 1);
        assert_eq!(result.changed_count(), 1);
        assert_eq!(result.unchanged_count(), 1);
        assert_eq!(result.column_count_before(), 3);
        assert_eq!(result.column_count_after(), 3);
        assert!(result.has_changes());
    }

    #[test]
    fn asymmetric_column_counts_are_derived_from_statuses() {
        let result = ComparisonResult {
            before_row_count: 2,
            after_row_count: 2,
            columns: vec![
                unchanged("id"),
                unchanged("sales"),
                ColumnComparison {
                    name: "legacy".to_string(),
                    status: ComparisonStatus::Removed,
                    before: Some(observed_column(
                        "legacy",
                        LogicalType::String,
                        false,
                        2,
                        None,
                        None,
                    )),
                    after: None,
                    changes: Vec::new(),
                },
                ColumnComparison {
                    name: "region".to_string(),
                    status: ComparisonStatus::Added,
                    before: None,
                    after: Some(observed_column(
                        "region",
                        LogicalType::Categorical,
                        false,
                        2,
                        None,
                        None,
                    )),
                    changes: Vec::new(),
                },
                ColumnComparison {
                    name: "channel".to_string(),
                    status: ComparisonStatus::Added,
                    before: None,
                    after: Some(observed_column(
                        "channel",
                        LogicalType::Categorical,
                        false,
                        2,
                        None,
                        None,
                    )),
                    changes: Vec::new(),
                },
            ],
        };

        assert_eq!(result.column_count_before(), 3);
        assert_eq!(result.column_count_after(), 4);
    }

    #[test]
    fn snapshots_preserve_logical_type_and_nullability() {
        let before = observed_column("sales", LogicalType::Integer, false, 2, None, None);
        let after = observed_column("sales", LogicalType::Float, true, 2, None, None);
        let comparison = ColumnComparison {
            name: "sales".to_string(),
            status: ComparisonStatus::Changed,
            before: Some(before),
            after: Some(after),
            changes: vec![
                ComparisonChangeCode::LogicalTypeChanged,
                ComparisonChangeCode::NullabilityChanged,
            ],
        };

        assert_eq!(
            comparison
                .before
                .as_ref()
                .map(|column| &column.logical_type),
            Some(&LogicalType::Integer)
        );
        assert!(
            !comparison
                .before
                .as_ref()
                .expect("test snapshot is present")
                .observed_nullable
        );
        assert_eq!(
            comparison.after.as_ref().map(|column| &column.logical_type),
            Some(&LogicalType::Float)
        );
        assert!(
            comparison
                .after
                .as_ref()
                .expect("test snapshot is present")
                .observed_nullable
        );
    }

    #[test]
    fn snapshots_preserve_observed_ranges() {
        let before_range = ObservedRange::new(1.0, 10.0);
        let after_range = ObservedRange::new(1.0, 20.0);
        let comparison = ColumnComparison {
            name: "sales".to_string(),
            status: ComparisonStatus::Changed,
            before: Some(observed_column(
                "sales",
                LogicalType::Float,
                false,
                2,
                Some(before_range.clone()),
                None,
            )),
            after: Some(observed_column(
                "sales",
                LogicalType::Float,
                false,
                2,
                Some(after_range.clone()),
                None,
            )),
            changes: vec![ComparisonChangeCode::RangeChanged],
        };

        assert_eq!(
            comparison
                .before
                .as_ref()
                .and_then(|column| column.observed_range.clone()),
            Some(before_range)
        );
        assert_eq!(
            comparison
                .after
                .as_ref()
                .and_then(|column| column.observed_range.clone()),
            Some(after_range)
        );
    }

    #[test]
    fn snapshots_preserve_observed_string_and_boolean_values() {
        let before_values = vec![ObservedValue::String("North".to_string())];
        let after_values = vec![ObservedValue::Boolean(true)];
        let comparison = ColumnComparison {
            name: "region".to_string(),
            status: ComparisonStatus::Changed,
            before: Some(observed_column(
                "region",
                LogicalType::Categorical,
                false,
                1,
                None,
                Some(before_values.clone()),
            )),
            after: Some(observed_column(
                "region",
                LogicalType::Categorical,
                false,
                1,
                None,
                Some(after_values.clone()),
            )),
            changes: vec![ComparisonChangeCode::ObservedValuesChanged],
        };

        assert_eq!(
            comparison
                .before
                .as_ref()
                .and_then(|column| column.observed_values.clone()),
            Some(before_values)
        );
        assert_eq!(
            comparison
                .after
                .as_ref()
                .and_then(|column| column.observed_values.clone()),
            Some(after_values)
        );
    }
}

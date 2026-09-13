use std::collections::{HashMap, HashSet};

use crate::{
    comparison::{
        visit_comparison_columns, ComparisonChangeCode, ComparisonResult, ComparisonStatus,
    },
    profiling::{numeric_value_for_profile, DatasetInput, ProfileValue, ProfilingError},
    schema::{ObservedColumnSchema, ObservedDatasetSchema},
};

use super::{SchemaDriftCode, SchemaDriftIssue, SchemaDriftResult, SchemaDriftSeverity};

/// Interprets a comparison result for structural schema drift without
/// re-comparing schemas.
///
/// Row count, unique count, numeric range, and observed-value changes are not
/// schema drift in v0.2. The comparison result remains unchanged.
pub fn detect_schema_drift(comparison: &ComparisonResult) -> SchemaDriftResult {
    let mut issues = Vec::new();

    for column in &comparison.columns {
        append_drift_issues(
            &mut issues,
            column.status,
            &column.name,
            &column.changes,
            column.before.as_ref(),
            column.after.as_ref(),
        );
    }

    SchemaDriftResult { issues }
}

/// Detects drift from the same factual comparison traversal without creating
/// owned comparison snapshots that schema-drift output does not expose.
pub fn detect_schema_drift_from_observed_schemas(
    before: &ObservedDatasetSchema,
    after: &ObservedDatasetSchema,
) -> SchemaDriftResult {
    let mut issues = Vec::new();

    visit_comparison_columns(before, after, |column| {
        append_drift_issues(
            &mut issues,
            column.status,
            column.name,
            &column.changes,
            column.before,
            column.after,
        );
    });

    SchemaDriftResult { issues }
}

/// Detects drift from normalized inputs without profiling properties that the
/// drift contract intentionally ignores, such as unique count and ranges.
pub fn detect_schema_drift_from_input(
    before: &DatasetInput,
    after: &DatasetInput,
) -> Result<SchemaDriftResult, ProfilingError> {
    let before_nullability = structural_nullability(before)?;
    let after_nullability = structural_nullability(after)?;
    let after_by_name = after
        .columns
        .iter()
        .zip(after_nullability)
        .map(|(column, nullable)| (column.name.as_str(), (column, nullable)))
        .collect::<HashMap<_, _>>();
    let before_names = before
        .columns
        .iter()
        .map(|column| column.name.as_str())
        .collect::<HashSet<_>>();
    let mut issues = Vec::new();

    for (before_column, before_nullable) in before.columns.iter().zip(before_nullability) {
        match after_by_name.get(before_column.name.as_str()).copied() {
            Some((after_column, after_nullable)) => {
                if before_column.logical_type != after_column.logical_type {
                    issues.push(issue(
                        SchemaDriftCode::LogicalTypeChanged,
                        SchemaDriftSeverity::Error,
                        &before_column.name,
                    ));
                }
                if before_nullable != after_nullable {
                    issues.push(issue(
                        SchemaDriftCode::NullabilityChanged,
                        nullability_severity_from_values(before_nullable, after_nullable),
                        &before_column.name,
                    ));
                }
            }
            None => issues.push(issue(
                SchemaDriftCode::ColumnRemoved,
                SchemaDriftSeverity::Error,
                &before_column.name,
            )),
        }
    }

    for after_column in &after.columns {
        if !before_names.contains(after_column.name.as_str()) {
            issues.push(issue(
                SchemaDriftCode::ColumnAdded,
                SchemaDriftSeverity::Warning,
                &after_column.name,
            ));
        }
    }

    Ok(SchemaDriftResult { issues })
}

fn structural_nullability(input: &DatasetInput) -> Result<Vec<bool>, ProfilingError> {
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

    input
        .columns
        .iter()
        .map(|column| {
            let mut nullable = false;
            for value in &column.values {
                nullable |= matches!(value, ProfileValue::Null);
                numeric_value_for_profile(&column.name, &column.logical_type, value)?;
            }
            Ok(nullable)
        })
        .collect()
}

fn append_drift_issues(
    issues: &mut Vec<SchemaDriftIssue>,
    status: ComparisonStatus,
    name: &str,
    changes: &[ComparisonChangeCode],
    before: Option<&ObservedColumnSchema>,
    after: Option<&ObservedColumnSchema>,
) {
    match status {
        ComparisonStatus::Added => issues.push(issue(
            SchemaDriftCode::ColumnAdded,
            SchemaDriftSeverity::Warning,
            name,
        )),
        ComparisonStatus::Removed => issues.push(issue(
            SchemaDriftCode::ColumnRemoved,
            SchemaDriftSeverity::Error,
            name,
        )),
        ComparisonStatus::Changed => {
            if changes.contains(&ComparisonChangeCode::LogicalTypeChanged) {
                issues.push(issue(
                    SchemaDriftCode::LogicalTypeChanged,
                    SchemaDriftSeverity::Error,
                    name,
                ));
            }

            if changes.contains(&ComparisonChangeCode::NullabilityChanged) {
                if let Some(severity) = nullability_severity(before, after) {
                    issues.push(issue(SchemaDriftCode::NullabilityChanged, severity, name));
                }
            }
        }
        ComparisonStatus::Unchanged => {}
    }
}

fn issue(code: SchemaDriftCode, severity: SchemaDriftSeverity, column: &str) -> SchemaDriftIssue {
    SchemaDriftIssue {
        code,
        severity,
        column: column.to_string(),
    }
}

fn nullability_severity(
    before: Option<&ObservedColumnSchema>,
    after: Option<&ObservedColumnSchema>,
) -> Option<SchemaDriftSeverity> {
    let (Some(before), Some(after)) = (before, after) else {
        return None;
    };

    match (before.observed_nullable, after.observed_nullable) {
        (false, true) => Some(SchemaDriftSeverity::Error),
        (true, false) => Some(SchemaDriftSeverity::Warning),
        (false, false) | (true, true) => None,
    }
}

fn nullability_severity_from_values(
    before_nullable: bool,
    after_nullable: bool,
) -> SchemaDriftSeverity {
    match (before_nullable, after_nullable) {
        (false, true) => SchemaDriftSeverity::Error,
        (true, false) => SchemaDriftSeverity::Warning,
        (false, false) | (true, true) => {
            unreachable!("a drift issue is emitted only for changed nullability")
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::{
        comparison::{
            compare_observed_schemas, ColumnComparison, ComparisonChangeCode, ComparisonResult,
            ComparisonStatus,
        },
        profiling::LogicalType,
        schema::{ObservedColumnSchema, ObservedDatasetSchema},
    };

    fn snapshot(name: &str, nullable: bool) -> ObservedColumnSchema {
        ObservedColumnSchema::new(
            name.to_string(),
            LogicalType::Integer,
            nullable,
            1,
            None,
            None,
        )
    }

    fn column(
        name: &str,
        status: ComparisonStatus,
        before: Option<ObservedColumnSchema>,
        after: Option<ObservedColumnSchema>,
        changes: Vec<ComparisonChangeCode>,
    ) -> ColumnComparison {
        ColumnComparison {
            name: name.to_string(),
            status,
            before,
            after,
            changes,
        }
    }

    fn comparison(columns: Vec<ColumnComparison>) -> ComparisonResult {
        ComparisonResult {
            before_row_count: 100,
            after_row_count: 100,
            columns,
        }
    }

    #[test]
    fn empty_and_row_count_only_results_have_no_schema_drift() {
        let empty = comparison(vec![]);
        let row_count_only = ComparisonResult {
            before_row_count: 100,
            after_row_count: 120,
            columns: vec![column(
                "id",
                ComparisonStatus::Unchanged,
                Some(snapshot("id", false)),
                Some(snapshot("id", false)),
                vec![],
            )],
        };

        for result in [&empty, &row_count_only] {
            let drift = detect_schema_drift(result);
            assert!(drift.issues.is_empty());
            assert!(!drift.has_drift());
            assert_eq!(drift.warning_count(), 0);
            assert_eq!(drift.error_count(), 0);
        }
    }

    #[test]
    fn added_and_removed_columns_have_their_fixed_severities() {
        let result = comparison(vec![
            column(
                "region",
                ComparisonStatus::Added,
                None,
                Some(snapshot("region", false)),
                vec![ComparisonChangeCode::LogicalTypeChanged],
            ),
            column(
                "legacy",
                ComparisonStatus::Removed,
                Some(snapshot("legacy", false)),
                None,
                vec![ComparisonChangeCode::NullabilityChanged],
            ),
        ]);

        assert_eq!(
            detect_schema_drift(&result).issues,
            vec![
                issue(
                    SchemaDriftCode::ColumnAdded,
                    SchemaDriftSeverity::Warning,
                    "region",
                ),
                issue(
                    SchemaDriftCode::ColumnRemoved,
                    SchemaDriftSeverity::Error,
                    "legacy",
                ),
            ]
        );
    }

    #[test]
    fn structural_changes_have_canonical_order_and_do_not_duplicate() {
        let result = comparison(vec![column(
            "sales",
            ComparisonStatus::Changed,
            Some(snapshot("sales", false)),
            Some(snapshot("sales", true)),
            vec![
                ComparisonChangeCode::NullabilityChanged,
                ComparisonChangeCode::LogicalTypeChanged,
                ComparisonChangeCode::LogicalTypeChanged,
                ComparisonChangeCode::NullabilityChanged,
            ],
        )]);

        assert_eq!(
            detect_schema_drift(&result).issues,
            vec![
                issue(
                    SchemaDriftCode::LogicalTypeChanged,
                    SchemaDriftSeverity::Error,
                    "sales",
                ),
                issue(
                    SchemaDriftCode::NullabilityChanged,
                    SchemaDriftSeverity::Error,
                    "sales",
                ),
            ]
        );
    }

    #[test]
    fn nullable_true_to_false_is_a_warning() {
        let result = comparison(vec![column(
            "status",
            ComparisonStatus::Changed,
            Some(snapshot("status", true)),
            Some(snapshot("status", false)),
            vec![ComparisonChangeCode::NullabilityChanged],
        )]);

        assert_eq!(
            detect_schema_drift(&result).issues,
            vec![issue(
                SchemaDriftCode::NullabilityChanged,
                SchemaDriftSeverity::Warning,
                "status",
            )]
        );
    }

    #[test]
    fn profile_only_changes_are_not_schema_drift() {
        let profile_codes = vec![
            ComparisonChangeCode::UniqueCountChanged,
            ComparisonChangeCode::RangeChanged,
            ComparisonChangeCode::ObservedValuesChanged,
        ];
        let result = comparison(vec![
            column(
                "unique",
                ComparisonStatus::Changed,
                Some(snapshot("unique", false)),
                Some(snapshot("unique", false)),
                vec![ComparisonChangeCode::UniqueCountChanged],
            ),
            column(
                "range",
                ComparisonStatus::Changed,
                Some(snapshot("range", false)),
                Some(snapshot("range", false)),
                vec![ComparisonChangeCode::RangeChanged],
            ),
            column(
                "values",
                ComparisonStatus::Changed,
                Some(snapshot("values", false)),
                Some(snapshot("values", false)),
                vec![ComparisonChangeCode::ObservedValuesChanged],
            ),
            column(
                "mixed",
                ComparisonStatus::Changed,
                Some(snapshot("mixed", false)),
                Some(snapshot("mixed", false)),
                profile_codes,
            ),
        ]);

        let drift = detect_schema_drift(&result);
        assert!(drift.issues.is_empty());
        assert!(!drift.has_drift());
    }

    #[test]
    fn structural_codes_are_reported_while_profile_codes_are_ignored() {
        let result = comparison(vec![column(
            "sales",
            ComparisonStatus::Changed,
            Some(snapshot("sales", false)),
            Some(snapshot("sales", false)),
            vec![
                ComparisonChangeCode::RangeChanged,
                ComparisonChangeCode::LogicalTypeChanged,
                ComparisonChangeCode::UniqueCountChanged,
            ],
        )]);

        assert_eq!(
            detect_schema_drift(&result).issues,
            vec![issue(
                SchemaDriftCode::LogicalTypeChanged,
                SchemaDriftSeverity::Error,
                "sales",
            )]
        );
    }

    #[test]
    fn unchanged_and_missing_nullability_snapshots_produce_no_issues() {
        let result = comparison(vec![
            column(
                "unchanged",
                ComparisonStatus::Unchanged,
                Some(snapshot("unchanged", false)),
                Some(snapshot("unchanged", true)),
                vec![ComparisonChangeCode::LogicalTypeChanged],
            ),
            column(
                "missing",
                ComparisonStatus::Changed,
                None,
                None,
                vec![ComparisonChangeCode::NullabilityChanged],
            ),
        ]);

        assert!(detect_schema_drift(&result).issues.is_empty());
    }

    #[test]
    fn mixed_dataset_preserves_comparison_order_and_counts() {
        let result = comparison(vec![
            column(
                "id",
                ComparisonStatus::Unchanged,
                Some(snapshot("id", false)),
                Some(snapshot("id", false)),
                vec![],
            ),
            column(
                "sales",
                ComparisonStatus::Changed,
                Some(snapshot("sales", false)),
                Some(snapshot("sales", false)),
                vec![ComparisonChangeCode::LogicalTypeChanged],
            ),
            column(
                "legacy",
                ComparisonStatus::Removed,
                Some(snapshot("legacy", false)),
                None,
                vec![],
            ),
            column(
                "region",
                ComparisonStatus::Added,
                None,
                Some(snapshot("region", false)),
                vec![],
            ),
            column(
                "status",
                ComparisonStatus::Changed,
                Some(snapshot("status", false)),
                Some(snapshot("status", true)),
                vec![ComparisonChangeCode::NullabilityChanged],
            ),
            column(
                "score",
                ComparisonStatus::Changed,
                Some(snapshot("score", false)),
                Some(snapshot("score", false)),
                vec![ComparisonChangeCode::RangeChanged],
            ),
        ]);
        let drift = detect_schema_drift(&result);

        assert_eq!(
            drift.issues,
            vec![
                issue(
                    SchemaDriftCode::LogicalTypeChanged,
                    SchemaDriftSeverity::Error,
                    "sales",
                ),
                issue(
                    SchemaDriftCode::ColumnRemoved,
                    SchemaDriftSeverity::Error,
                    "legacy",
                ),
                issue(
                    SchemaDriftCode::ColumnAdded,
                    SchemaDriftSeverity::Warning,
                    "region",
                ),
                issue(
                    SchemaDriftCode::NullabilityChanged,
                    SchemaDriftSeverity::Error,
                    "status",
                ),
            ]
        );
        assert!(drift.has_drift());
        assert_eq!(drift.error_count(), 3);
        assert_eq!(drift.warning_count(), 1);
    }

    #[test]
    fn renamed_columns_remain_removed_and_added() {
        let result = comparison(vec![
            column(
                "old_name",
                ComparisonStatus::Removed,
                Some(snapshot("old_name", false)),
                None,
                vec![],
            ),
            column(
                "new_name",
                ComparisonStatus::Added,
                None,
                Some(snapshot("new_name", false)),
                vec![],
            ),
        ]);

        assert_eq!(
            detect_schema_drift(&result).issues,
            vec![
                issue(
                    SchemaDriftCode::ColumnRemoved,
                    SchemaDriftSeverity::Error,
                    "old_name",
                ),
                issue(
                    SchemaDriftCode::ColumnAdded,
                    SchemaDriftSeverity::Warning,
                    "new_name",
                ),
            ]
        );
    }

    #[test]
    fn detection_is_deterministic_and_does_not_mutate_comparison() {
        let result = comparison(vec![column(
            "status",
            ComparisonStatus::Changed,
            Some(snapshot("status", false)),
            Some(snapshot("status", true)),
            vec![ComparisonChangeCode::NullabilityChanged],
        )]);
        let original = result.clone();

        let first = detect_schema_drift(&result);
        let second = detect_schema_drift(&result);

        assert_eq!(result, original);
        assert_eq!(first, second);
    }

    #[test]
    fn direct_schema_drift_matches_the_owned_comparison_pipeline() {
        let before = ObservedDatasetSchema::new(
            2,
            vec![
                snapshot("id", false),
                snapshot("removed", false),
                snapshot("nullable", false),
            ],
        );
        let after = ObservedDatasetSchema::new(
            3,
            vec![
                snapshot("nullable", true),
                ObservedColumnSchema::new(
                    "id".to_string(),
                    LogicalType::Float,
                    false,
                    2,
                    None,
                    None,
                ),
                snapshot("added", false),
            ],
        );

        let owned = detect_schema_drift(&compare_observed_schemas(&before, &after));
        let direct = detect_schema_drift_from_observed_schemas(&before, &after);

        assert_eq!(direct, owned);
    }
}

/// Operational relevance or risk level of a structural schema drift issue.
///
/// This severity is independent from validation severity and does not express
/// contract compliance or formal compatibility.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum SchemaDriftSeverity {
    Warning,
    Error,
}

/// Structural kind of schema drift detected from a comparison result.
///
/// Profile changes such as row count, unique count, numeric range, and
/// observed values are intentionally not schema drift codes in v0.2.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub enum SchemaDriftCode {
    ColumnAdded,
    ColumnRemoved,
    LogicalTypeChanged,
    NullabilityChanged,
}

/// Structured schema drift issue associated with one column.
///
/// Before and after detail remains available on the source `ComparisonResult`.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct SchemaDriftIssue {
    pub code: SchemaDriftCode,
    pub severity: SchemaDriftSeverity,
    pub column: String,
}

/// Result of structurally interpreting a `ComparisonResult`.
///
/// Row count, unique count, numeric range, and observed-value changes are not
/// schema drift in v0.2 and therefore do not appear in `issues`.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct SchemaDriftResult {
    pub issues: Vec<SchemaDriftIssue>,
}

impl SchemaDriftResult {
    /// Returns whether any structural schema drift issue was detected.
    pub fn has_drift(&self) -> bool {
        !self.issues.is_empty()
    }

    /// Returns the number of warning-severity schema drift issues.
    pub fn warning_count(&self) -> usize {
        self.count_severity(SchemaDriftSeverity::Warning)
    }

    /// Returns the number of error-severity schema drift issues.
    pub fn error_count(&self) -> usize {
        self.count_severity(SchemaDriftSeverity::Error)
    }

    fn count_severity(&self, severity: SchemaDriftSeverity) -> usize {
        self.issues
            .iter()
            .filter(|issue| issue.severity == severity)
            .count()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn severity_variants_are_distinct_and_copyable() {
        let severities = [SchemaDriftSeverity::Warning, SchemaDriftSeverity::Error];
        let copied = severities[0];

        assert_eq!(copied, SchemaDriftSeverity::Warning);
        assert_ne!(severities[0], severities[1]);
    }

    #[test]
    fn code_variants_are_distinct() {
        let codes = [
            SchemaDriftCode::ColumnAdded,
            SchemaDriftCode::ColumnRemoved,
            SchemaDriftCode::LogicalTypeChanged,
            SchemaDriftCode::NullabilityChanged,
        ];

        assert!(codes.windows(2).all(|pair| pair[0] != pair[1]));
    }

    #[test]
    fn derived_counts_are_calculated_from_issues() {
        let result = SchemaDriftResult {
            issues: vec![
                SchemaDriftIssue {
                    code: SchemaDriftCode::ColumnAdded,
                    severity: SchemaDriftSeverity::Warning,
                    column: "region".to_string(),
                },
                SchemaDriftIssue {
                    code: SchemaDriftCode::NullabilityChanged,
                    severity: SchemaDriftSeverity::Warning,
                    column: "status".to_string(),
                },
                SchemaDriftIssue {
                    code: SchemaDriftCode::ColumnRemoved,
                    severity: SchemaDriftSeverity::Error,
                    column: "legacy".to_string(),
                },
                SchemaDriftIssue {
                    code: SchemaDriftCode::LogicalTypeChanged,
                    severity: SchemaDriftSeverity::Error,
                    column: "sales".to_string(),
                },
                SchemaDriftIssue {
                    code: SchemaDriftCode::NullabilityChanged,
                    severity: SchemaDriftSeverity::Error,
                    column: "id".to_string(),
                },
            ],
        };

        assert!(result.has_drift());
        assert_eq!(result.warning_count(), 2);
        assert_eq!(result.error_count(), 3);
    }
}

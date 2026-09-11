use crate::profiling::LogicalType;

/// Importance assigned to a validation issue.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ValidationSeverity {
    Warning,
    Error,
}

/// Stable identifier for the kind of validation problem detected.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ValidationCode {
    MissingColumn,
    UnexpectedColumn,
    TypeMismatch,
    NullNotAllowed,
    ValueNotAllowed,
    RangeViolation,
}

/// Structured value recorded as the expected or observed side of an issue.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum ValidationValue {
    String(String),
    Boolean(bool),
    LogicalType(LogicalType),
}

/// An individual validation failure or warning.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ValidationIssue {
    pub code: ValidationCode,
    pub severity: ValidationSeverity,
    pub column: Option<String>,
    pub expected: Option<ValidationValue>,
    pub observed: Option<ValidationValue>,
}

impl ValidationIssue {
    pub fn new(
        code: ValidationCode,
        severity: ValidationSeverity,
        column: Option<String>,
        expected: Option<ValidationValue>,
        observed: Option<ValidationValue>,
    ) -> Self {
        Self {
            code,
            severity,
            column,
            expected,
            observed,
        }
    }
}

/// Complete result produced by validating a dataset.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ValidationResult {
    pub issues: Vec<ValidationIssue>,
}

impl ValidationResult {
    pub fn new(issues: Vec<ValidationIssue>) -> Self {
        Self { issues }
    }

    /// Returns whether the result contains no error-severity issues.
    pub fn is_valid(&self) -> bool {
        !self
            .issues
            .iter()
            .any(|issue| issue.severity == ValidationSeverity::Error)
    }

    /// Returns the number of error-severity issues derived from `issues`.
    pub fn error_count(&self) -> usize {
        self.issues
            .iter()
            .filter(|issue| issue.severity == ValidationSeverity::Error)
            .count()
    }

    /// Returns the number of warning-severity issues derived from `issues`.
    pub fn warning_count(&self) -> usize {
        self.issues
            .iter()
            .filter(|issue| issue.severity == ValidationSeverity::Warning)
            .count()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn issue(code: ValidationCode, severity: ValidationSeverity) -> ValidationIssue {
        ValidationIssue::new(code, severity, None, None, None)
    }

    #[test]
    fn severity_variants_are_distinct_and_comparable() {
        assert_eq!(ValidationSeverity::Warning, ValidationSeverity::Warning);
        assert_eq!(ValidationSeverity::Error, ValidationSeverity::Error);
        assert_ne!(ValidationSeverity::Warning, ValidationSeverity::Error);
    }

    #[test]
    fn validation_codes_are_stable_distinct_variants() {
        let codes = [
            ValidationCode::MissingColumn,
            ValidationCode::UnexpectedColumn,
            ValidationCode::TypeMismatch,
            ValidationCode::NullNotAllowed,
            ValidationCode::ValueNotAllowed,
            ValidationCode::RangeViolation,
        ];

        assert_eq!(codes.len(), 6);
        assert!(codes.windows(2).all(|pair| pair[0] != pair[1]));
    }

    #[test]
    fn validation_values_preserve_logical_types_strings_and_booleans() {
        assert_eq!(
            ValidationValue::LogicalType(LogicalType::Integer),
            ValidationValue::LogicalType(LogicalType::Integer)
        );
        assert_eq!(
            ValidationValue::String("Mars".to_string()),
            ValidationValue::String("Mars".to_string())
        );
        assert_eq!(
            ValidationValue::Boolean(true),
            ValidationValue::Boolean(true)
        );
    }

    #[test]
    fn issue_preserves_column_and_expected_and_observed_values() {
        let issue = ValidationIssue::new(
            ValidationCode::TypeMismatch,
            ValidationSeverity::Error,
            Some("age".to_string()),
            Some(ValidationValue::LogicalType(LogicalType::Integer)),
            Some(ValidationValue::LogicalType(LogicalType::String)),
        );

        assert_eq!(issue.column.as_deref(), Some("age"));
        assert_eq!(
            issue.expected,
            Some(ValidationValue::LogicalType(LogicalType::Integer))
        );
        assert_eq!(
            issue.observed,
            Some(ValidationValue::LogicalType(LogicalType::String))
        );
    }

    #[test]
    fn dataset_level_issue_allows_absent_column_expected_and_observed_values() {
        let issue = issue(ValidationCode::MissingColumn, ValidationSeverity::Error);

        assert_eq!(issue.column, None);
        assert_eq!(issue.expected, None);
        assert_eq!(issue.observed, None);
    }

    #[test]
    fn empty_and_warning_only_results_are_valid() {
        let empty = ValidationResult::new(Vec::new());
        let warnings = ValidationResult::new(vec![issue(
            ValidationCode::UnexpectedColumn,
            ValidationSeverity::Warning,
        )]);

        assert!(empty.is_valid());
        assert_eq!(empty.error_count(), 0);
        assert_eq!(empty.warning_count(), 0);
        assert!(warnings.is_valid());
        assert_eq!(warnings.error_count(), 0);
        assert_eq!(warnings.warning_count(), 1);
    }

    #[test]
    fn error_only_result_is_invalid() {
        let result = ValidationResult::new(vec![issue(
            ValidationCode::TypeMismatch,
            ValidationSeverity::Error,
        )]);

        assert!(!result.is_valid());
        assert_eq!(result.error_count(), 1);
        assert_eq!(result.warning_count(), 0);
    }

    #[test]
    fn validity_and_counts_are_derived_exclusively_from_issues() {
        let result = ValidationResult::new(vec![
            issue(
                ValidationCode::UnexpectedColumn,
                ValidationSeverity::Warning,
            ),
            issue(ValidationCode::TypeMismatch, ValidationSeverity::Error),
            issue(ValidationCode::NullNotAllowed, ValidationSeverity::Warning),
        ]);

        assert!(!result.is_valid());
        assert_eq!(result.error_count(), 1);
        assert_eq!(result.warning_count(), 2);
    }
}

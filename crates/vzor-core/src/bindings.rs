use pyo3::{
    exceptions::{PyOSError, PyTypeError, PyValueError},
    prelude::*,
    types::{PyBool, PyDict, PyFloat, PyInt, PyIterator, PyList, PyString},
};

use crate::comparison::{
    compare_observed_schemas, ColumnComparison, ComparisonChangeCode, ComparisonResult,
    ComparisonStatus,
};
use crate::persistence::{load_suggested_schema, save_suggested_schema, PersistenceError};
use crate::profiling::{
    profile_structure, ColumnInput, ColumnProfile, DatasetInput, DatasetProfile, LogicalType,
    NumericStats, ProfileValue, ProfilingError,
};
use crate::schema::{
    observed_schema_from_profile_and_input, suggested_schema_from_observed, ObservedColumnSchema,
    ObservedDatasetSchema, ObservedRange, ObservedValue, SchemaObservationError,
    SuggestedColumnSchema, SuggestedConstraints, SuggestedDatasetSchema, SuggestedNumericRange,
    SuggestedValue,
};
use crate::schema_drift::{
    detect_schema_drift_from_input, SchemaDriftCode, SchemaDriftIssue, SchemaDriftResult,
    SchemaDriftSeverity,
};
use crate::validation::{
    validate_dataset, ValidationCode, ValidationIssue, ValidationResult, ValidationSeverity,
    ValidationValue,
};

type NormalizedColumn = (String, String, Py<PyAny>, bool);
type PythonColumn = Py<PyAny>;
type SuggestedSchemaColumn = (
    String,
    String,
    bool,
    Option<(Option<f64>, Option<f64>)>,
    Option<Vec<Py<PyAny>>>,
);

pub(crate) fn register(module: &Bound<'_, PyModule>) -> PyResult<()> {
    module.add_function(wrap_pyfunction!(profile_dataset, module)?)?;
    module.add_function(wrap_pyfunction!(observed_schema_dataset, module)?)?;
    module.add_function(wrap_pyfunction!(suggest_schema_dataset, module)?)?;
    module.add_function(wrap_pyfunction!(inspect_dataset, module)?)?;
    module.add_function(wrap_pyfunction!(save_suggested_schema_dataset, module)?)?;
    module.add_function(wrap_pyfunction!(validate_dataset_file, module)?)?;
    module.add_function(wrap_pyfunction!(validate_dataset_schema, module)?)?;
    module.add_function(wrap_pyfunction!(compare_datasets, module)?)?;
    module.add_function(wrap_pyfunction!(schema_drift_datasets, module)?)?;
    Ok(())
}

#[pyfunction]
fn profile_dataset(py: Python<'_>, columns: Vec<PythonColumn>) -> PyResult<Py<PyAny>> {
    let input = dataset_input_from_python(py, columns)?;
    let profile = profile_structure(&input).map_err(profiling_error)?;
    dataset_profile_to_python(py, profile)
}

#[pyfunction]
fn observed_schema_dataset(py: Python<'_>, columns: Vec<PythonColumn>) -> PyResult<Py<PyAny>> {
    let input = dataset_input_from_python(py, columns)?;
    let profile = profile_structure(&input).map_err(profiling_error)?;
    let schema = observed_schema_from_profile_and_input(&profile, &input)
        .map_err(schema_observation_error)?;

    observed_dataset_schema_to_python(py, schema)
}

#[pyfunction]
fn suggest_schema_dataset(py: Python<'_>, columns: Vec<PythonColumn>) -> PyResult<Py<PyAny>> {
    let input = dataset_input_from_python(py, columns)?;
    let profile = profile_structure(&input).map_err(profiling_error)?;
    let observed = observed_schema_from_profile_and_input(&profile, &input)
        .map_err(schema_observation_error)?;
    let suggested = suggested_schema_from_observed(&observed);

    suggested_dataset_schema_to_python(py, suggested)
}

#[pyfunction]
fn inspect_dataset(py: Python<'_>, columns: Vec<PythonColumn>) -> PyResult<Py<PyAny>> {
    let input = dataset_input_from_python(py, columns)?;
    let profile = profile_structure(&input).map_err(profiling_error)?;
    let observed = observed_schema_from_profile_and_input(&profile, &input)
        .map_err(schema_observation_error)?;
    let suggested = suggested_schema_from_observed(&observed);
    let result = PyDict::new(py);

    result.set_item("profile", dataset_profile_to_python(py, profile)?)?;
    result.set_item(
        "observed_schema",
        observed_dataset_schema_to_python(py, observed)?,
    )?;
    result.set_item(
        "suggested_schema",
        suggested_dataset_schema_to_python(py, suggested)?,
    )?;

    Ok(result.into_any().unbind())
}

#[pyfunction]
fn save_suggested_schema_dataset(
    py: Python<'_>,
    columns: Vec<PythonColumn>,
    path: String,
) -> PyResult<()> {
    let input = dataset_input_from_python(py, columns)?;
    let observed = observed_schema_from_input(&input)?;
    let suggested = suggested_schema_from_observed(&observed);

    save_suggested_schema(&suggested, path).map_err(persistence_error)
}

#[pyfunction]
fn validate_dataset_file(
    py: Python<'_>,
    columns: Vec<PythonColumn>,
    schema_path: String,
) -> PyResult<Py<PyAny>> {
    let input = dataset_input_from_python(py, columns)?;
    let schema = load_suggested_schema(schema_path).map_err(persistence_error)?;
    let result = validate_dataset(&input, &schema);

    validation_result_to_python(py, result)
}

#[pyfunction(name = "_validate_dataset_schema")]
fn validate_dataset_schema(
    py: Python<'_>,
    columns: Vec<PythonColumn>,
    schema_columns: Vec<SuggestedSchemaColumn>,
) -> PyResult<Py<PyAny>> {
    let input = dataset_input_from_python(py, columns)?;
    let schema = suggested_schema_from_python(py, schema_columns)?;
    let result = validate_dataset(&input, &schema);

    validation_result_to_python(py, result)
}

#[pyfunction]
fn compare_datasets(
    py: Python<'_>,
    before_columns: Vec<PythonColumn>,
    after_columns: Vec<PythonColumn>,
) -> PyResult<Py<PyAny>> {
    let before_input = dataset_input_from_python(py, before_columns)?;
    let after_input = dataset_input_from_python(py, after_columns)?;
    let before = observed_schema_from_input(&before_input)?;
    let after = observed_schema_from_input(&after_input)?;
    let result = compare_observed_schemas(&before, &after);

    comparison_result_to_python(py, result)
}

#[pyfunction]
fn schema_drift_datasets(
    py: Python<'_>,
    before_columns: Vec<PythonColumn>,
    after_columns: Vec<PythonColumn>,
) -> PyResult<Py<PyAny>> {
    let before_input = dataset_input_from_python(py, before_columns)?;
    let after_input = dataset_input_from_python(py, after_columns)?;
    let result =
        detect_schema_drift_from_input(&before_input, &after_input).map_err(profiling_error)?;

    schema_drift_result_to_python(py, result)
}

fn observed_schema_from_input(input: &DatasetInput) -> PyResult<ObservedDatasetSchema> {
    let profile = profile_structure(input).map_err(profiling_error)?;
    observed_schema_from_profile_and_input(&profile, input).map_err(schema_observation_error)
}

fn suggested_schema_from_python(
    py: Python<'_>,
    columns: Vec<SuggestedSchemaColumn>,
) -> PyResult<SuggestedDatasetSchema> {
    let columns = columns
        .into_iter()
        .map(
            |(name, logical_type, nullable, numeric_range, allowed_values)| {
                let logical_type = parse_logical_type(&logical_type)?;
                let numeric_range =
                    numeric_range.map(|(min, max)| SuggestedNumericRange::new(min, max));
                let allowed_values = allowed_values
                    .map(|values| {
                        values
                            .iter()
                            .map(|value| suggested_value_from_python(py, value))
                            .collect::<PyResult<Vec<_>>>()
                    })
                    .transpose()?;

                Ok(SuggestedColumnSchema::new(
                    name,
                    logical_type,
                    nullable,
                    SuggestedConstraints::new(numeric_range, allowed_values),
                ))
            },
        )
        .collect::<PyResult<Vec<_>>>()?;

    Ok(SuggestedDatasetSchema::new(columns))
}

fn dataset_input_from_python(py: Python<'_>, columns: Vec<PythonColumn>) -> PyResult<DatasetInput> {
    let columns = columns
        .into_iter()
        .map(|column| {
            let (name, logical_type, values, raw_scalars) =
                normalized_column_from_python(py, column)?;
            let logical_type = parse_logical_type(&logical_type)?;
            let values = PyIterator::from_object(values.bind(py))?
                .map(|value| {
                    value.and_then(|value| {
                        if raw_scalars {
                            profile_value_from_raw_scalar(&value, &logical_type, &name)
                        } else {
                            profile_value_from_bound(&value)
                        }
                    })
                })
                .collect::<PyResult<Vec<_>>>()?;

            Ok(ColumnInput::new(name, logical_type, values))
        })
        .collect::<PyResult<Vec<_>>>()?;

    Ok(DatasetInput::new(columns))
}

fn normalized_column_from_python(
    py: Python<'_>,
    column: PythonColumn,
) -> PyResult<NormalizedColumn> {
    let column = column.bind(py);
    if let Ok(normalized) = column.extract::<NormalizedColumn>() {
        return Ok(normalized);
    }

    let (name, logical_type, values) = column.extract()?;
    Ok((name, logical_type, values, false))
}

fn parse_logical_type(value: &str) -> PyResult<LogicalType> {
    match value {
        "integer" => Ok(LogicalType::Integer),
        "float" => Ok(LogicalType::Float),
        "boolean" => Ok(LogicalType::Boolean),
        "string" => Ok(LogicalType::String),
        "datetime" => Ok(LogicalType::Datetime),
        "categorical" => Ok(LogicalType::Categorical),
        "unknown" => Ok(LogicalType::Unknown),
        _ => Err(PyValueError::new_err(format!(
            "Unsupported logical type '{value}'"
        ))),
    }
}

fn profile_value_from_bound(value: &Bound<'_, PyAny>) -> PyResult<ProfileValue> {
    if value.is_none() {
        Ok(ProfileValue::Null)
    } else if value.is_instance_of::<PyBool>() {
        Ok(ProfileValue::Boolean(value.extract()?))
    } else if value.is_instance_of::<PyInt>() {
        Ok(ProfileValue::Integer(value.extract()?))
    } else if value.is_instance_of::<PyFloat>() {
        Ok(ProfileValue::Float(value.extract()?))
    } else if value.is_instance_of::<PyString>() {
        Ok(ProfileValue::String(value.extract()?))
    } else {
        Err(PyTypeError::new_err(format!(
            "Unsupported normalized value type '{}'",
            value.get_type().name()?
        )))
    }
}

fn profile_value_from_raw_scalar(
    value: &Bound<'_, PyAny>,
    logical_type: &LogicalType,
    column_name: &str,
) -> PyResult<ProfileValue> {
    match logical_type {
        LogicalType::Integer => value
            .extract::<i64>()
            .map(ProfileValue::Integer)
            .map_err(|_| {
                PyTypeError::new_err(format!(
                    "Column '{column_name}' contains an unsupported value"
                ))
            }),
        LogicalType::Float => {
            let value = value.extract::<f64>()?;
            Ok(if value.is_nan() {
                ProfileValue::Null
            } else {
                ProfileValue::Float(value)
            })
        }
        LogicalType::Boolean => value
            .extract::<bool>()
            .map(ProfileValue::Boolean)
            .map_err(|_| {
                PyTypeError::new_err(format!(
                    "Column '{column_name}' contains an unsupported value"
                ))
            }),
        _ => profile_value_from_bound(value),
    }
}

fn suggested_value_from_python(py: Python<'_>, value: &Py<PyAny>) -> PyResult<SuggestedValue> {
    let value = value.bind(py);

    if value.is_instance_of::<PyBool>() {
        Ok(SuggestedValue::Boolean(value.extract()?))
    } else if value.is_instance_of::<PyString>() {
        Ok(SuggestedValue::String(value.extract()?))
    } else {
        Err(PyTypeError::new_err(format!(
            "Unsupported suggested allowed value type '{}'",
            value.get_type().name()?
        )))
    }
}

fn dataset_profile_to_python(py: Python<'_>, profile: DatasetProfile) -> PyResult<Py<PyAny>> {
    let result = PyDict::new(py);
    let columns = PyList::empty(py);

    result.set_item("row_count", profile.row_count)?;
    for column in profile.columns {
        columns.append(column_profile_to_python(py, column)?)?;
    }
    result.set_item("columns", columns)?;

    Ok(result.into_any().unbind())
}

fn column_profile_to_python(py: Python<'_>, profile: ColumnProfile) -> PyResult<Py<PyAny>> {
    let result = PyDict::new(py);

    result.set_item("name", profile.name)?;
    result.set_item("logical_type", logical_type_name(&profile.logical_type))?;
    result.set_item("count", profile.count)?;
    result.set_item("null_count", profile.null_count)?;
    result.set_item("unique_count", profile.unique_count)?;
    match profile.numeric_stats {
        Some(stats) => result.set_item("numeric_stats", numeric_stats_to_python(py, stats)?)?,
        None => result.set_item("numeric_stats", py.None())?,
    }

    Ok(result.into_any().unbind())
}

fn numeric_stats_to_python(py: Python<'_>, stats: NumericStats) -> PyResult<Py<PyAny>> {
    let result = PyDict::new(py);

    result.set_item("min", stats.min)?;
    result.set_item("max", stats.max)?;
    result.set_item("mean", stats.mean)?;
    result.set_item("median", stats.median)?;
    result.set_item("p25", stats.p25)?;
    result.set_item("p50", stats.p50)?;
    result.set_item("p75", stats.p75)?;

    Ok(result.into_any().unbind())
}

fn observed_dataset_schema_to_python(
    py: Python<'_>,
    schema: ObservedDatasetSchema,
) -> PyResult<Py<PyAny>> {
    let result = PyDict::new(py);
    let columns = PyList::empty(py);

    result.set_item("row_count", schema.row_count)?;
    for column in schema.columns {
        columns.append(observed_column_schema_to_python(py, column)?)?;
    }
    result.set_item("columns", columns)?;

    Ok(result.into_any().unbind())
}

fn observed_column_schema_to_python(
    py: Python<'_>,
    schema: ObservedColumnSchema,
) -> PyResult<Py<PyAny>> {
    let result = PyDict::new(py);

    result.set_item("name", schema.name)?;
    result.set_item("logical_type", logical_type_name(&schema.logical_type))?;
    result.set_item("observed_nullable", schema.observed_nullable)?;
    result.set_item("observed_unique_count", schema.observed_unique_count)?;
    match schema.observed_range {
        Some(range) => result.set_item("observed_range", observed_range_to_python(py, range)?)?,
        None => result.set_item("observed_range", py.None())?,
    }
    match schema.observed_values {
        Some(values) => {
            let observed = PyList::empty(py);
            for value in values {
                match value {
                    ObservedValue::String(value) => observed.append(value)?,
                    ObservedValue::Boolean(value) => observed.append(value)?,
                }
            }
            result.set_item("observed_values", observed)?;
        }
        None => result.set_item("observed_values", py.None())?,
    }

    Ok(result.into_any().unbind())
}

fn observed_range_to_python(py: Python<'_>, range: ObservedRange) -> PyResult<Py<PyAny>> {
    let result = PyDict::new(py);
    result.set_item("min", range.min)?;
    result.set_item("max", range.max)?;
    Ok(result.into_any().unbind())
}

fn suggested_dataset_schema_to_python(
    py: Python<'_>,
    schema: SuggestedDatasetSchema,
) -> PyResult<Py<PyAny>> {
    let result = PyDict::new(py);
    let columns = PyList::empty(py);

    for column in schema.columns {
        columns.append(suggested_column_schema_to_python(py, column)?)?;
    }
    result.set_item("columns", columns)?;

    Ok(result.into_any().unbind())
}

fn suggested_column_schema_to_python(
    py: Python<'_>,
    schema: SuggestedColumnSchema,
) -> PyResult<Py<PyAny>> {
    let result = PyDict::new(py);

    result.set_item("name", schema.name)?;
    result.set_item("logical_type", logical_type_name(&schema.logical_type))?;
    result.set_item("nullable", schema.nullable)?;
    result.set_item(
        "constraints",
        suggested_constraints_to_python(py, schema.constraints)?,
    )?;

    Ok(result.into_any().unbind())
}

fn suggested_constraints_to_python(
    py: Python<'_>,
    constraints: SuggestedConstraints,
) -> PyResult<Py<PyAny>> {
    let result = PyDict::new(py);

    match constraints.numeric_range {
        Some(range) => result.set_item(
            "numeric_range",
            suggested_numeric_range_to_python(py, range)?,
        )?,
        None => result.set_item("numeric_range", py.None())?,
    }
    match constraints.allowed_values {
        Some(values) => {
            let allowed = PyList::empty(py);
            for value in values {
                match value {
                    SuggestedValue::String(value) => allowed.append(value)?,
                    SuggestedValue::Boolean(value) => allowed.append(value)?,
                }
            }
            result.set_item("allowed_values", allowed)?;
        }
        None => result.set_item("allowed_values", py.None())?,
    }

    Ok(result.into_any().unbind())
}

fn suggested_numeric_range_to_python(
    py: Python<'_>,
    range: SuggestedNumericRange,
) -> PyResult<Py<PyAny>> {
    let result = PyDict::new(py);

    match range.min {
        Some(min) => result.set_item("min", min)?,
        None => result.set_item("min", py.None())?,
    }
    match range.max {
        Some(max) => result.set_item("max", max)?,
        None => result.set_item("max", py.None())?,
    }

    Ok(result.into_any().unbind())
}

fn validation_result_to_python(py: Python<'_>, result: ValidationResult) -> PyResult<Py<PyAny>> {
    let output = PyDict::new(py);
    let issues = PyList::empty(py);

    output.set_item("is_valid", result.is_valid())?;
    output.set_item("error_count", result.error_count())?;
    output.set_item("warning_count", result.warning_count())?;
    for issue in result.issues {
        issues.append(validation_issue_to_python(py, issue)?)?;
    }
    output.set_item("issues", issues)?;

    Ok(output.into_any().unbind())
}

fn validation_issue_to_python(py: Python<'_>, issue: ValidationIssue) -> PyResult<Py<PyAny>> {
    let output = PyDict::new(py);

    output.set_item("code", validation_code_name(issue.code))?;
    output.set_item("severity", validation_severity_name(issue.severity))?;
    output.set_item("column", issue.column)?;
    output.set_item("expected", validation_value_to_python(py, issue.expected)?)?;
    output.set_item("observed", validation_value_to_python(py, issue.observed)?)?;

    Ok(output.into_any().unbind())
}

fn validation_value_to_python(
    py: Python<'_>,
    value: Option<ValidationValue>,
) -> PyResult<Py<PyAny>> {
    match value {
        Some(ValidationValue::String(value)) => Ok(value.into_pyobject(py)?.into_any().unbind()),
        Some(ValidationValue::Boolean(value)) => {
            Ok(value.into_pyobject(py)?.to_owned().into_any().unbind())
        }
        Some(ValidationValue::LogicalType(value)) => Ok(logical_type_name(&value)
            .into_pyobject(py)?
            .into_any()
            .unbind()),
        None => Ok(py.None()),
    }
}

fn comparison_result_to_python(py: Python<'_>, result: ComparisonResult) -> PyResult<Py<PyAny>> {
    let output = PyDict::new(py);
    let columns = PyList::empty(py);

    output.set_item("before_row_count", result.before_row_count)?;
    output.set_item("after_row_count", result.after_row_count)?;
    output.set_item("has_changes", result.has_changes())?;
    output.set_item("row_count_changed", result.row_count_changed())?;
    output.set_item("added_count", result.added_count())?;
    output.set_item("removed_count", result.removed_count())?;
    output.set_item("changed_count", result.changed_count())?;
    output.set_item("unchanged_count", result.unchanged_count())?;
    output.set_item("column_count_before", result.column_count_before())?;
    output.set_item("column_count_after", result.column_count_after())?;
    for column in result.columns {
        columns.append(column_comparison_to_python(py, column)?)?;
    }
    output.set_item("columns", columns)?;

    Ok(output.into_any().unbind())
}

fn column_comparison_to_python(py: Python<'_>, column: ColumnComparison) -> PyResult<Py<PyAny>> {
    let output = PyDict::new(py);
    let changes = PyList::empty(py);

    output.set_item("name", column.name)?;
    output.set_item("status", comparison_status_name(column.status))?;
    match column.before {
        Some(before) => output.set_item("before", observed_column_schema_to_python(py, before)?)?,
        None => output.set_item("before", py.None())?,
    }
    match column.after {
        Some(after) => output.set_item("after", observed_column_schema_to_python(py, after)?)?,
        None => output.set_item("after", py.None())?,
    }
    for change in column.changes {
        changes.append(comparison_change_code_name(change))?;
    }
    output.set_item("changes", changes)?;

    Ok(output.into_any().unbind())
}

fn schema_drift_result_to_python(py: Python<'_>, result: SchemaDriftResult) -> PyResult<Py<PyAny>> {
    let output = PyDict::new(py);
    let issues = PyList::empty(py);

    output.set_item("has_drift", result.has_drift())?;
    output.set_item("warning_count", result.warning_count())?;
    output.set_item("error_count", result.error_count())?;
    for issue in result.issues {
        issues.append(schema_drift_issue_to_python(py, issue)?)?;
    }
    output.set_item("issues", issues)?;

    Ok(output.into_any().unbind())
}

fn schema_drift_issue_to_python(py: Python<'_>, issue: SchemaDriftIssue) -> PyResult<Py<PyAny>> {
    let output = PyDict::new(py);

    output.set_item("code", schema_drift_code_name(issue.code))?;
    output.set_item("severity", schema_drift_severity_name(issue.severity))?;
    output.set_item("column", issue.column)?;

    Ok(output.into_any().unbind())
}

fn validation_code_name(code: ValidationCode) -> &'static str {
    match code {
        ValidationCode::MissingColumn => "missing_column",
        ValidationCode::UnexpectedColumn => "unexpected_column",
        ValidationCode::TypeMismatch => "type_mismatch",
        ValidationCode::NullNotAllowed => "null_not_allowed",
        ValidationCode::ValueNotAllowed => "value_not_allowed",
        ValidationCode::RangeViolation => "range_violation",
    }
}

fn validation_severity_name(severity: ValidationSeverity) -> &'static str {
    match severity {
        ValidationSeverity::Warning => "warning",
        ValidationSeverity::Error => "error",
    }
}

fn comparison_status_name(status: ComparisonStatus) -> &'static str {
    match status {
        ComparisonStatus::Added => "added",
        ComparisonStatus::Removed => "removed",
        ComparisonStatus::Changed => "changed",
        ComparisonStatus::Unchanged => "unchanged",
    }
}

fn comparison_change_code_name(code: ComparisonChangeCode) -> &'static str {
    match code {
        ComparisonChangeCode::LogicalTypeChanged => "logical_type_changed",
        ComparisonChangeCode::NullabilityChanged => "nullability_changed",
        ComparisonChangeCode::UniqueCountChanged => "unique_count_changed",
        ComparisonChangeCode::RangeChanged => "range_changed",
        ComparisonChangeCode::ObservedValuesChanged => "observed_values_changed",
    }
}

fn schema_drift_code_name(code: SchemaDriftCode) -> &'static str {
    match code {
        SchemaDriftCode::ColumnAdded => "column_added",
        SchemaDriftCode::ColumnRemoved => "column_removed",
        SchemaDriftCode::LogicalTypeChanged => "logical_type_changed",
        SchemaDriftCode::NullabilityChanged => "nullability_changed",
    }
}

fn schema_drift_severity_name(severity: SchemaDriftSeverity) -> &'static str {
    match severity {
        SchemaDriftSeverity::Warning => "warning",
        SchemaDriftSeverity::Error => "error",
    }
}

fn logical_type_name(logical_type: &LogicalType) -> &'static str {
    match logical_type {
        LogicalType::Integer => "integer",
        LogicalType::Float => "float",
        LogicalType::Boolean => "boolean",
        LogicalType::String => "string",
        LogicalType::Datetime => "datetime",
        LogicalType::Categorical => "categorical",
        LogicalType::Unknown => "unknown",
    }
}

fn profiling_error(error: ProfilingError) -> PyErr {
    match error {
        ProfilingError::ColumnLengthMismatch {
            column,
            expected,
            actual,
        } => PyValueError::new_err(format!(
            "Column '{column}' has {actual} values; expected {expected}"
        )),
        ProfilingError::ValueTypeMismatch {
            column,
            expected,
            actual,
        } => PyTypeError::new_err(format!(
            "Column '{column}' expected {} values but received {}",
            logical_type_name(&expected),
            actual.to_lowercase()
        )),
    }
}

fn schema_observation_error(error: SchemaObservationError) -> PyErr {
    match error {
        SchemaObservationError::ColumnCountMismatch { profile, input } => PyValueError::new_err(
            format!("Observed schema input has {input} columns; profile has {profile}"),
        ),
        SchemaObservationError::ColumnNameMismatch {
            index,
            profile,
            input,
        } => PyValueError::new_err(format!(
            "Column {index} is named '{input}' in the input but '{profile}' in the profile"
        )),
        SchemaObservationError::LogicalTypeMismatch {
            column,
            profile,
            input,
        } => PyTypeError::new_err(format!(
            "Column '{column}' has logical type {} in the input; expected {}",
            logical_type_name(&input),
            logical_type_name(&profile)
        )),
        SchemaObservationError::ObservedValueCountMismatch {
            column,
            expected,
            actual,
        } => PyValueError::new_err(format!(
            "Column '{column}' produced {actual} observed values; expected {expected}"
        )),
    }
}

fn persistence_error(error: PersistenceError) -> PyErr {
    match error {
        PersistenceError::Io(message) => PyOSError::new_err(message),
        PersistenceError::Serialization(message) => PyValueError::new_err(message),
        PersistenceError::Deserialization(message) => PyValueError::new_err(message),
        PersistenceError::UnsupportedFormatVersion(version) => PyValueError::new_err(format!(
            "Unsupported suggested schema format version: {version}"
        )),
    }
}

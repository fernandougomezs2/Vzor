use std::fmt;

use serde::{Deserialize, Serialize};

use crate::schema::SuggestedDatasetSchema;

/// Stable version for the persisted suggested-schema JSON envelope.
pub const SUGGESTED_SCHEMA_FORMAT_VERSION: u32 = 1;

/// Versioned envelope used to persist a suggested schema independently from
/// the Vzor package version.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct PersistedSuggestedSchema {
    pub format_version: u32,
    pub schema: SuggestedDatasetSchema,
}

/// Errors produced while reading, writing, or converting suggested-schema
/// persistence JSON.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum PersistenceError {
    Io(String),
    Serialization(String),
    Deserialization(String),
    UnsupportedFormatVersion(u32),
}

impl fmt::Display for PersistenceError {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::Io(message) => write!(formatter, "I/O error: {message}"),
            Self::Serialization(message) => write!(formatter, "serialization error: {message}"),
            Self::Deserialization(message) => {
                write!(formatter, "deserialization error: {message}")
            }
            Self::UnsupportedFormatVersion(version) => {
                write!(
                    formatter,
                    "unsupported suggested schema format version: {version}"
                )
            }
        }
    }
}

impl std::error::Error for PersistenceError {}

"""Deterministic agent-ready representation for Vzor CLI results.

``output_version`` versions this CLI contract independently from both the
package version and persistence's ``format_version``.  ``machine_payload`` is
the source of truth; ``human_summary`` is only a compact derived view.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, is_dataclass
from typing import Any, Mapping

from ._human_summary import format_inspection_summary, format_validation_summary

OUTPUT_VERSION = 1

OUTPUT_KINDS = (
    "profile",
    "inspection",
    "suggested_schema",
    "validation",
    "comparison",
    "schema_drift",
)

VALIDATION_STABLE_CODES = {
    "missing_column": "VZOR_VALIDATION_MISSING_COLUMN",
    "unexpected_column": "VZOR_VALIDATION_UNEXPECTED_COLUMN",
    "type_mismatch": "VZOR_VALIDATION_TYPE_MISMATCH",
    "null_not_allowed": "VZOR_VALIDATION_NULL_NOT_ALLOWED",
    "value_not_allowed": "VZOR_VALIDATION_VALUE_NOT_ALLOWED",
    "range_violation": "VZOR_VALIDATION_RANGE_VIOLATION",
}

COMPARISON_STABLE_CODES = {
    "logical_type_changed": "VZOR_COMPARISON_LOGICAL_TYPE_CHANGED",
    "nullability_changed": "VZOR_COMPARISON_NULLABILITY_CHANGED",
    "unique_count_changed": "VZOR_COMPARISON_UNIQUE_COUNT_CHANGED",
    "range_changed": "VZOR_COMPARISON_RANGE_CHANGED",
    "observed_values_changed": "VZOR_COMPARISON_OBSERVED_VALUES_CHANGED",
}

SCHEMA_DRIFT_STABLE_CODES = {
    "column_added": "VZOR_DRIFT_COLUMN_ADDED",
    "column_removed": "VZOR_DRIFT_COLUMN_REMOVED",
    "logical_type_changed": "VZOR_DRIFT_LOGICAL_TYPE_CHANGED",
    "nullability_changed": "VZOR_DRIFT_NULLABILITY_CHANGED",
}


def build_agent_output(kind: str, value: Any) -> dict[str, Any]:
    """Build an output v1 envelope without mutating the core result."""
    if kind not in OUTPUT_KINDS:
        raise ValueError(f"Unknown agent output kind: {kind}")

    payload = _as_payload(value)
    machine_payload = _normalize_payload(kind, payload)
    human_summary = _build_human_summary(kind, machine_payload)

    return {
        "output_version": OUTPUT_VERSION,
        "kind": kind,
        "human_summary": human_summary,
        "machine_payload": machine_payload,
    }


def _as_payload(value: Any) -> dict[str, Any]:
    if is_dataclass(value) and not isinstance(value, type):
        payload = asdict(value)
    elif isinstance(value, Mapping):
        payload = deepcopy(dict(value))
    else:
        raise TypeError("Agent output machine payload must be a dataclass or mapping")

    return payload


def _normalize_payload(kind: str, payload: dict[str, Any]) -> dict[str, Any]:
    if kind == "validation":
        payload["issues"] = [
            _issue_with_stable_code(issue, VALIDATION_STABLE_CODES, "validation")
            for issue in payload["issues"]
        ]
    elif kind == "comparison":
        for column in payload["columns"]:
            column["changes"] = [
                {
                    "code": code,
                    "stable_code": _stable_code(
                        code,
                        COMPARISON_STABLE_CODES,
                        "comparison",
                    ),
                }
                for code in column["changes"]
            ]
    elif kind == "schema_drift":
        payload["issues"] = [
            _issue_with_stable_code(issue, SCHEMA_DRIFT_STABLE_CODES, "schema drift")
            for issue in payload["issues"]
        ]

    return payload


def _issue_with_stable_code(
    issue: Mapping[str, Any],
    mapping: Mapping[str, str],
    namespace: str,
) -> dict[str, Any]:
    code = issue["code"]
    return {
        "code": code,
        "stable_code": _stable_code(code, mapping, namespace),
        **{key: deepcopy(value) for key, value in issue.items() if key != "code"},
    }


def _stable_code(
    code: str,
    mapping: Mapping[str, str],
    namespace: str,
) -> str:
    try:
        return mapping[code]
    except KeyError as error:
        raise ValueError(f"Unknown {namespace} code: {code}") from error


def _build_human_summary(kind: str, payload: Mapping[str, Any]) -> str:
    if kind == "profile":
        return (
            "Profile completed: "
            f"{_counted(payload['row_count'], 'row')}, "
            f"{_counted(len(payload['columns']), 'column')}."
        )
    if kind == "inspection":
        summary = payload["summary"]
        return format_inspection_summary(
            summary["row_count"],
            summary["column_count"],
            summary["nullable_columns"],
        )
    if kind == "suggested_schema":
        return (
            "Suggested schema generated: "
            f"{_counted(len(payload['columns']), 'column')}."
        )
    if kind == "validation":
        return format_validation_summary(
            payload["is_valid"],
            payload["error_count"],
            payload["warning_count"],
        )
    if kind == "comparison":
        if not payload["has_changes"]:
            return "Comparison completed: no changes detected."
        summary = (
            "Comparison detected changes: "
            f"{payload['added_count']} added, "
            f"{payload['removed_count']} removed, "
            f"{_counted(payload['changed_count'], 'changed column')}"
        )
        if payload["row_count_changed"]:
            return f"{summary}; row count changed."
        return f"{summary}."
    if kind == "schema_drift":
        if not payload["has_drift"]:
            return "Schema drift not detected."
        return (
            "Schema drift detected: "
            f"{_counted(payload['error_count'], 'error')}, "
            f"{_counted(payload['warning_count'], 'warning')}."
        )

    raise ValueError(f"Unknown agent output kind: {kind}")


def _counted(count: int, noun: str) -> str:
    suffix = "" if count == 1 else "s"
    return f"{count} {noun}{suffix}"

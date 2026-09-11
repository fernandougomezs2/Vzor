import copy
import json

import pytest

from vzor.agent_output import (
    COMPARISON_STABLE_CODES,
    OUTPUT_KINDS,
    OUTPUT_VERSION,
    SCHEMA_DRIFT_STABLE_CODES,
    VALIDATION_STABLE_CODES,
    build_agent_output,
)


def minimal_payload(kind: str) -> dict:
    if kind == "profile":
        return {"row_count": 0, "columns": []}
    if kind == "inspection":
        return {
            "profile": {},
            "observed_schema": {},
            "suggested_schema": {},
            "summary": {"row_count": 0, "column_count": 0, "nullable_columns": 0},
        }
    if kind == "suggested_schema":
        return {"columns": []}
    if kind == "validation":
        return {
            "is_valid": True,
            "error_count": 0,
            "warning_count": 0,
            "issues": [],
        }
    if kind == "comparison":
        return {
            "before_row_count": 0,
            "after_row_count": 0,
            "has_changes": False,
            "row_count_changed": False,
            "added_count": 0,
            "removed_count": 0,
            "changed_count": 0,
            "unchanged_count": 0,
            "column_count_before": 0,
            "column_count_after": 0,
            "columns": [],
        }
    if kind == "schema_drift":
        return {
            "has_drift": False,
            "warning_count": 0,
            "error_count": 0,
            "issues": [],
        }
    raise AssertionError(f"Missing test payload for {kind}")


@pytest.mark.parametrize("kind", OUTPUT_KINDS)
def test_all_six_kinds_use_the_exact_v1_envelope(kind: str) -> None:
    output = build_agent_output(kind, minimal_payload(kind))

    assert OUTPUT_VERSION == 1
    assert OUTPUT_KINDS == (
        "profile",
        "inspection",
        "suggested_schema",
        "validation",
        "comparison",
        "schema_drift",
    )
    assert list(output) == [
        "output_version",
        "kind",
        "human_summary",
        "machine_payload",
    ]
    assert output["output_version"] == 1
    assert output["kind"] == kind
    assert isinstance(output["human_summary"], str)
    assert isinstance(output["machine_payload"], dict)


def test_profile_inspection_and_suggested_schema_summaries() -> None:
    profile = build_agent_output("profile", {"row_count": 100, "columns": [{}] * 5})
    inspection_payload = minimal_payload("inspection")
    inspection_payload["summary"] = {
        "row_count": 100,
        "column_count": 5,
        "nullable_columns": 2,
    }
    inspection = build_agent_output("inspection", inspection_payload)
    suggested = build_agent_output("suggested_schema", {"columns": [{}] * 5})

    assert profile["human_summary"] == "Profile completed: 100 rows, 5 columns."
    assert (
        inspection["human_summary"]
        == "Inspection completed: 100 rows, 5 columns, 2 nullable columns."
    )
    assert (
        suggested["human_summary"] == "Suggested schema generated: 5 columns."
    )


def test_validation_adds_every_stable_code_and_preserves_typed_values() -> None:
    issues = [
        {
            "code": code,
            "severity": "error",
            "column": "Región",
            "expected": {"min": 0, "max": 100},
            "observed": None if index == 0 else index,
        }
        for index, code in enumerate(VALIDATION_STABLE_CODES)
    ]
    output = build_agent_output(
        "validation",
        {
            "is_valid": False,
            "error_count": 6,
            "warning_count": 0,
            "issues": issues,
        },
    )
    payload = output["machine_payload"]

    assert output["human_summary"] == "Validation failed: 6 errors, 0 warnings."
    assert {
        issue["code"]: issue["stable_code"] for issue in payload["issues"]
    } == VALIDATION_STABLE_CODES
    assert payload["issues"][0]["observed"] is None
    assert payload["issues"][1]["expected"] == {"min": 0, "max": 100}


def test_validation_pass_and_fail_summaries_are_exact() -> None:
    passed = build_agent_output("validation", minimal_payload("validation"))
    failed_payload = minimal_payload("validation")
    failed_payload.update(is_valid=False, error_count=2)
    failed = build_agent_output("validation", failed_payload)

    assert passed["human_summary"] == "Validation passed: 0 errors, 0 warnings."
    assert failed["human_summary"] == "Validation failed: 2 errors, 0 warnings."
    assert failed["machine_payload"]["is_valid"] is False
    assert failed["machine_payload"]["error_count"] == 2


def test_comparison_adds_every_stable_code_and_preserves_statuses() -> None:
    payload = minimal_payload("comparison")
    payload.update(
        has_changes=True,
        row_count_changed=True,
        added_count=1,
        removed_count=1,
        changed_count=2,
        columns=[
            {
                "name": "added",
                "status": "added",
                "before": None,
                "after": {},
                "changes": [],
            },
            {
                "name": "removed",
                "status": "removed",
                "before": {},
                "after": None,
                "changes": [],
            },
            {
                "name": "changed",
                "status": "changed",
                "before": {"numeric_range": {"min": 0, "max": 10}},
                "after": {"numeric_range": {"min": 1, "max": 11}},
                "changes": list(COMPARISON_STABLE_CODES),
            },
            {
                "name": "same",
                "status": "unchanged",
                "before": {},
                "after": {},
                "changes": [],
            },
        ],
    )
    output = build_agent_output("comparison", payload)
    machine_payload = output["machine_payload"]

    assert (
        output["human_summary"]
        == "Comparison detected changes: 1 added, 1 removed, 2 changed columns; row count changed."
    )
    assert [column["status"] for column in machine_payload["columns"]] == [
        "added",
        "removed",
        "changed",
        "unchanged",
    ]
    assert {
        change["code"]: change["stable_code"]
        for change in machine_payload["columns"][2]["changes"]
    } == COMPARISON_STABLE_CODES
    assert machine_payload["columns"][2]["before"] == {
        "numeric_range": {"min": 0, "max": 10}
    }


def test_comparison_summaries_with_no_changes_and_unchanged_row_count() -> None:
    unchanged = build_agent_output("comparison", minimal_payload("comparison"))
    changed_payload = minimal_payload("comparison")
    changed_payload.update(has_changes=True, changed_count=1)
    changed = build_agent_output("comparison", changed_payload)

    assert unchanged["human_summary"] == "Comparison completed: no changes detected."
    assert (
        changed["human_summary"]
        == "Comparison detected changes: 0 added, 0 removed, 1 changed column."
    )


def test_schema_drift_adds_every_stable_code_and_builds_summaries() -> None:
    issues = [
        {"code": code, "severity": "error", "column": code}
        for code in SCHEMA_DRIFT_STABLE_CODES
    ]
    drift = build_agent_output(
        "schema_drift",
        {"has_drift": True, "error_count": 2, "warning_count": 1, "issues": issues},
    )
    no_drift = build_agent_output("schema_drift", minimal_payload("schema_drift"))

    assert drift["human_summary"] == "Schema drift detected: 2 errors, 1 warning."
    assert {
        issue["code"]: issue["stable_code"]
        for issue in drift["machine_payload"]["issues"]
    } == SCHEMA_DRIFT_STABLE_CODES
    assert no_drift["human_summary"] == "Schema drift not detected."


def test_comparison_and_drift_namespaces_are_distinct() -> None:
    assert (
        COMPARISON_STABLE_CODES["logical_type_changed"]
        == "VZOR_COMPARISON_LOGICAL_TYPE_CHANGED"
    )
    assert (
        SCHEMA_DRIFT_STABLE_CODES["logical_type_changed"]
        == "VZOR_DRIFT_LOGICAL_TYPE_CHANGED"
    )
    assert (
        COMPARISON_STABLE_CODES["logical_type_changed"]
        != SCHEMA_DRIFT_STABLE_CODES["logical_type_changed"]
    )


@pytest.mark.parametrize(
    ("kind", "payload", "message"),
    [
        (
            "validation",
            {
                "is_valid": False,
                "error_count": 1,
                "warning_count": 0,
                "issues": [{"code": "new_validation_code"}],
            },
            "Unknown validation code: new_validation_code",
        ),
        (
            "comparison",
            {
                **minimal_payload("comparison"),
                "columns": [{"changes": ["new_comparison_code"]}],
            },
            "Unknown comparison code: new_comparison_code",
        ),
        (
            "schema_drift",
            {
                "has_drift": True,
                "error_count": 1,
                "warning_count": 0,
                "issues": [{"code": "new_drift_code"}],
            },
            "Unknown schema drift code: new_drift_code",
        ),
    ],
)
def test_unknown_internal_codes_fail_fast(kind: str, payload: dict, message: str) -> None:
    with pytest.raises(ValueError, match=f"^{message}$"):
        build_agent_output(kind, payload)


def test_unknown_kind_and_non_mapping_payload_fail_fast() -> None:
    with pytest.raises(ValueError, match="^Unknown agent output kind: future_kind$"):
        build_agent_output("future_kind", {})
    with pytest.raises(TypeError, match="must be a dataclass or mapping"):
        build_agent_output("profile", [])


def test_builder_does_not_mutate_core_payload_and_adds_no_volatile_metadata() -> None:
    payload = minimal_payload("comparison")
    payload["columns"] = [
        {
            "name": "amount",
            "status": "changed",
            "before": {},
            "after": {},
            "changes": ["range_changed"],
        }
    ]
    original = copy.deepcopy(payload)

    output = build_agent_output("comparison", payload)
    serialized = json.dumps(output, ensure_ascii=False)

    assert payload == original
    for forbidden in (
        "timestamp",
        "created_at",
        "generated_at",
        "execution_id",
        "trace_id",
        "confidence",
        "quality_score",
        "recommendation",
    ):
        assert f'"{forbidden}"' not in serialized

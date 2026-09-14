"""Pure large-data benchmark guardrail and classification helpers."""

from __future__ import annotations

GUARDRAIL_FRACTION = 0.70


def estimated_peak(previous_peak_bytes: int, previous_rows: int, target_rows: int) -> int:
    """Linearly extrapolate a prior isolated peak for benchmark safety only."""
    if previous_peak_bytes < 0 or previous_rows <= 0 or target_rows < 0:
        raise ValueError("peak and target rows must be non-negative; previous rows must be positive")
    return (previous_peak_bytes * target_rows + previous_rows - 1) // previous_rows


def is_safe_to_start(estimate_bytes: int, total_bytes: int | None, available_bytes: int | None) -> bool:
    """Require the estimate below 70% of total and, when known, free memory."""
    if total_bytes is None or total_bytes <= 0:
        return False
    if estimate_bytes > total_bytes * GUARDRAIL_FRACTION:
        return False
    return available_bytes is None or estimate_bytes <= available_bytes * GUARDRAIL_FRACTION


def classify_run(peak_bytes: int | None, total_bytes: int | None, completed: bool) -> str:
    """Classify benchmark evidence without exposing a Vzor runtime status."""
    if not completed:
        return "Not executed"
    if peak_bytes is None or total_bytes is None or total_bytes <= 0:
        return "Acceptable"
    ratio = peak_bytes / total_bytes
    if ratio <= 0.50:
        return "Comfortable"
    if ratio <= GUARDRAIL_FRACTION:
        return "Acceptable"
    if ratio <= 0.85:
        return "Memory pressure"
    return "Unsafe on current hardware"

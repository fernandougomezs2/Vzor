from benchmarks.large_data import classify_run, estimated_peak, is_safe_to_start
from benchmarks.scenarios import generate_dataframe


def test_linear_peak_estimate_is_conservative_integer_math() -> None:
    assert estimated_peak(101, 10, 20) == 202
    assert estimated_peak(101, 10, 21) == 213


def test_guardrail_requires_total_and_respects_available_memory() -> None:
    total = 1000
    assert is_safe_to_start(700, total, None)
    assert not is_safe_to_start(701, total, None)
    assert not is_safe_to_start(400, total, 500)
    assert not is_safe_to_start(400, None, None)


def test_large_data_classification_is_not_runtime_api() -> None:
    assert classify_run(None, None, False) == "Not executed"
    assert classify_run(400, 1000, True) == "Comfortable"
    assert classify_run(700, 1000, True) == "Acceptable"
    assert classify_run(800, 1000, True) == "Memory pressure"
    assert classify_run(900, 1000, True) == "Unsafe on current hardware"


def test_wide_generator_configuration_is_reproducible_without_large_fixtures() -> None:
    first = generate_dataframe(3, 250, 42, "wide")
    second = generate_dataframe(3, 250, 42, "wide")
    assert first.shape == (3, 250)
    assert first.equals(second)

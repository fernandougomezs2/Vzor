"""Deterministic pandas datasets used by the manual Vzor benchmarks.

The generators deliberately create pandas DataFrames; they do not use Vzor's
runtime or private APIs.  A seed, profile, row count, and column count define
one logical dataset.
"""

from __future__ import annotations

from collections.abc import Callable

import numpy as np
import pandas as pd


PROFILES = (
    "baseline",
    "numeric",
    "many_nulls",
    "high_cardinality",
    "heavy_strings",
    "categorical",
    "wide",
)


def profile_names() -> tuple[str, ...]:
    """Return valid profile names in stable CLI/documentation order."""

    return PROFILES


def _nullable_mask(rng: np.random.Generator, rows: int, fraction: float) -> np.ndarray:
    return rng.random(rows) < fraction


def _nullable_strings(
    values: np.ndarray, rng: np.random.Generator, fraction: float
) -> np.ndarray:
    result = values.astype(object)
    result[_nullable_mask(rng, len(result), fraction)] = None
    return result


def _dates(rows: int) -> pd.Series:
    return pd.Series(
        pd.Timestamp("2020-01-01") + pd.to_timedelta(np.arange(rows) % 1_461, unit="D")
    )


def _baseline_columns(rows: int, rng: np.random.Generator) -> list[tuple[str, object]]:
    regions = np.array(["north", "south", "east", "west", "central"], dtype=object)
    products = np.array([f"product-{number:03d}" for number in range(100)], dtype=object)
    quantities = rng.integers(1, 25, rows, dtype=np.int64)
    prices = rng.uniform(5, 500, rows)
    discounts = rng.choice(np.array([0.0, 0.05, 0.10, 0.15]), rows)
    return [
        ("transaction_id", np.arange(rows, dtype=np.int64)),
        ("order_date", _dates(rows)),
        ("region", pd.Categorical(rng.choice(regions, rows), categories=regions)),
        ("product", pd.Categorical(rng.choice(products, rows), categories=products)),
        ("quantity", quantities),
        ("unit_price", prices),
        ("discount", discounts),
        ("total", quantities * prices * (1.0 - discounts)),
        ("is_priority", pd.array(rng.random(rows) < 0.2, dtype="boolean")),
        (
            "customer_id",
            _nullable_strings(
                np.array([f"customer-{value:06d}" for value in rng.integers(0, 10_000, rows)]),
                rng,
                0.1,
            ),
        ),
        (
            "seller",
            _nullable_strings(
                np.array([f"seller-{value:04d}" for value in rng.integers(0, 250, rows)]),
                rng,
                0.05,
            ),
        ),
    ]


def _numeric_columns(rows: int, rng: np.random.Generator) -> list[tuple[str, object]]:
    return [
        ("integer_id", np.arange(rows, dtype=np.int64)),
        ("integer_measure", rng.integers(-1_000_000, 1_000_000, rows, dtype=np.int64)),
        ("float_measure", rng.normal(100.0, 15.0, rows)),
        ("ratio", rng.random(rows)),
        ("flag", pd.array(rng.random(rows) < 0.5, dtype="boolean")),
    ]


def _many_null_columns(rows: int, rng: np.random.Generator) -> list[tuple[str, object]]:
    fractions = (0.0, 0.1, 0.5, 0.9, 1.0)
    columns: list[tuple[str, object]] = []
    for percent in fractions:
        label = f"null_{int(percent * 100):03d}"
        numeric = pd.Series(rng.normal(size=rows))
        strings = pd.Series(rng.choice(np.array(["alpha", "beta", "gamma"], dtype=object), rows))
        booleans = pd.Series(pd.array(rng.random(rows) < 0.5, dtype="boolean"))
        dates = _dates(rows)
        mask = _nullable_mask(rng, rows, percent)
        numeric[mask] = np.nan
        strings[mask] = None
        booleans[mask] = pd.NA
        dates[mask] = pd.NaT
        columns.extend(
            [
                (f"numeric_{label}", numeric),
                (f"string_{label}", strings),
                (f"boolean_{label}", booleans),
                (f"datetime_{label}", dates),
            ]
        )
    return columns


def _high_cardinality_columns(rows: int, rng: np.random.Generator) -> list[tuple[str, object]]:
    unique = np.arange(rows, dtype=np.int64)
    return [
        ("transaction_id", unique),
        ("event_id", np.array([f"event-{value:012d}" for value in unique], dtype=object)),
        ("customer_id", np.array([f"customer-{value:012d}" for value in unique], dtype=object)),
        ("session_id", np.array([f"session-{value:012d}" for value in unique], dtype=object)),
        ("amount", rng.uniform(1, 1_000, rows)),
    ]


def _string_value(index: int, width: int, unicode: bool) -> str:
    alphabet = "áβ漢🙂" if unicode else "abcdef0123456789"
    prefix = f"value-{index:08d}-"
    return (prefix + (alphabet * ((width // len(alphabet)) + 1)))[:width]


def _heavy_string_columns(rows: int, rng: np.random.Generator) -> list[tuple[str, object]]:
    columns: list[tuple[str, object]] = []
    for width in (16, 64, 256):
        repeated = np.array([_string_value(i, width, False) for i in range(20)], dtype=object)
        near_unique = np.array([_string_value(i, width, True) for i in range(rows)], dtype=object)
        columns.append(
            (f"ascii_{width}", _nullable_strings(rng.choice(repeated, rows), rng, 0.1))
        )
        values = _nullable_strings(near_unique, rng, 0.05)
        if rows:
            values[0] = ""
        columns.append((f"unicode_unique_{width}", values))
    return columns


def _categorical_columns(rows: int, rng: np.random.Generator) -> list[tuple[str, object]]:
    columns: list[tuple[str, object]] = []
    for cardinality in (5, 50, 1_000, 10_000):
        categories = [f"category-{value:05d}" for value in range(cardinality)]
        columns.append(
            (
                f"category_{cardinality}",
                pd.Categorical(rng.choice(categories, rows), categories=categories),
            )
        )
    return columns


def _wide_columns(rows: int, rng: np.random.Generator) -> list[tuple[str, object]]:
    return _baseline_columns(rows, rng) + _numeric_columns(rows, rng) + _categorical_columns(rows, rng)


_BUILDERS: dict[str, Callable[[int, np.random.Generator], list[tuple[str, object]]]] = {
    "baseline": _baseline_columns,
    "numeric": _numeric_columns,
    "many_nulls": _many_null_columns,
    "high_cardinality": _high_cardinality_columns,
    "heavy_strings": _heavy_string_columns,
    "categorical": _categorical_columns,
    "wide": _wide_columns,
}


def generate_dataframe(rows: int, columns: int, seed: int, profile: str) -> pd.DataFrame:
    """Build a reproducible DataFrame for a named benchmark profile.

    Columns are repeated deterministically when a requested width exceeds the
    profile template, and are truncated when it is smaller.  The ``wide``
    profile accepts any positive width, including 50, 100, and 250.
    """

    if rows < 0:
        raise ValueError("rows must be non-negative")
    if columns <= 0:
        raise ValueError("columns must be positive")
    if profile not in _BUILDERS:
        raise ValueError(f"unknown profile {profile!r}; choose one of: {', '.join(PROFILES)}")

    rng = np.random.default_rng(seed)
    template = _BUILDERS[profile](rows, rng)
    result: dict[str, object] = {}
    for index in range(columns):
        name, values = template[index % len(template)]
        result[name if index < len(template) else f"{name}_{index // len(template)}"] = values
    return pd.DataFrame(result)

"""Run a self-contained public-API Vzor workflow without network access."""

import pandas as pd

import vzor


def main() -> None:
    baseline = pd.DataFrame(
        {
            "customer_id": [1, 2, 3],
            "region": pd.Categorical(["North", "South", "North"]),
            "sales": [120.0, 95.5, 210.0],
        }
    )
    incoming = pd.DataFrame(
        {
            "customer_id": ["one", "two", "three", "four"],
            "region": pd.Categorical(["North", "West", "North", "West"]),
            "sales": [120.0, 95.5, 210.0, 88.0],
            "active": [True, True, False, True],
        }
    )

    inspection = vzor.inspect(baseline)
    print(inspection.human_summary)

    schema = vzor.suggest_schema(baseline)
    validation = vzor.validate(incoming, schema)
    print(validation.human_summary)
    for issue in validation.errors:
        print(f"validation: {issue.code} ({issue.column})")

    comparison = vzor.compare(baseline, incoming)
    print(comparison.human_summary)
    for column in comparison.added:
        print(f"comparison added: {column.name}")
    for column in comparison.changed:
        print(f"comparison changed: {column.name} ({', '.join(column.changes)})")

    drift = vzor.schema_drift(baseline, incoming)
    print(drift.human_summary)
    for issue in drift.errors:
        print(f"drift error: {issue.code} ({issue.column})")
    for issue in drift.warnings:
        print(f"drift warning: {issue.code} ({issue.column})")


if __name__ == "__main__":
    main()

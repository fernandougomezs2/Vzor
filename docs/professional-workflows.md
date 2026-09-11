# Professional Workflows

Vzor is a trust and structure checkpoint. It does not schedule pipelines,
perform transformations, or present dashboards.

## Monthly reporting

```text
SQL extract
    ↓
pandas cleaning
    ↓
Vzor validation
    ↓
KPI calculation
    ↓
Excel / Power BI
```

SQL supplies the extract. pandas cleans and transforms it. Vzor validates the
dataset against a saved suggested schema. KPI calculation and presentation stay
in pandas, SQL, Excel, or Power BI.

## A new file from another department

```text
new file
    ↓
Vzor inspect
    ↓
compare with previous dataset
    ↓
schema drift
    ↓
analyst review
```

Inspect the new file first. Compare it with a previous snapshot for factual
changes. Use schema drift to isolate structural changes. An analyst decides any
subsequent transformation or remediation.

## Pipeline validation gate

```text
extract
    ↓
transform
    ↓
Vzor validate
    ↓
valid: continue
invalid: stop or review
```

An external scheduler or application owns orchestration. Vzor returns a
deterministic validation result; the caller decides whether to continue, stop,
or request review.

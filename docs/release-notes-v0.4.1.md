# Vzor 0.4.1 Release Notes

Vzor 0.4.1 is a maintenance release created to adopt the Vzor Community and
SaaS License 1.0 after the existing `v0.4.0` tag. It makes no runtime behavior,
public API, CLI, report, dependency, or installation change.

## Licensing

Vzor now uses a permissive source-available license with a commercial SaaS
threshold. It remains free for personal, educational, research, analytics,
consulting, nonprofit, internal business, on-premise, desktop, and commercial
software use, including a commercial SaaS product through USD 5,000 in that
product's cumulative gross revenue.

Only a commercial hosted or network-accessible SaaS product that uses Vzor and
exceeds USD 5,000 in cumulative gross revenue requires a commercial license:
USD 149/year for that SaaS product, after a 30-calendar-day grace period.
There is no telemetry, activation, or automatic revenue tracking.

See the [plain-language licensing guide](licensing.md). The [LICENSE](../LICENSE)
is authoritative and governs if this summary differs from it.

## Compatibility and installation

The supported matrix remains CPython 3.12 and 3.13 on Windows and Linux x86-64.
The required `pandas>=2.2.3,<4` dependency and optional
`vzor[polars]` extra remain unchanged. Installation and all public APIs remain
unchanged.

`output_version = 1` and suggested-schema `format_version = 1` remain
unchanged.

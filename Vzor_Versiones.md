# Vzor — Versiones y etapas de desarrollo

## Propósito

Este documento mantiene el alcance real de cada versión. Vzor es una capa de
confianza para datos que complementa pandas y otros backends; no es un reemplazo
de pandas ni un motor general de ingesta.

## Estado actual

```text
v0.1 — Core                                      COMPLETE
v0.2 — Validación, drift y uso operativo         COMPLETE
v0.3 — Madurez, reporting y UX avanzada          COMPLETE
v0.4 — Hardening, performance y backends         PLANNED
v0.5 — Excel / Power BI exports                   PLANNED
```

# v0.1 — Core — COMPLETE

Objetivo cumplido: Vzor entiende y representa datasets mediante un core Rust y
una API Python para pandas.

Incluye:

- workspace Rust, PyO3 y maturin;
- profiling estructural y estadísticas numéricas;
- tipos lógicos;
- schema observado;
- schema sugerido conservador;
- API pública `version`, `profile`, `observed_schema`, `suggest_schema` e
  `inspect`;
- modelos Python inmutables.

Invariante principal: una observación no se convierte automáticamente en una
restricción de negocio. En particular, los rangos numéricos observados no se
promueven a constraints sugeridos.

# v0.2 — Functional — COMPLETE

Objetivo cumplido: Vzor puede validar contratos persistidos, comparar datasets,
interpretar schema drift y operar desde una CLI determinista.

## Subfases cerradas

```text
2.1 — Modelos de validación
2.2 — Motor de validación
2.3 — Modelos de comparación
2.4 — Motor de comparación
2.5 — Schema drift
2.6 — Persistencia JSON versionada
2.7 — CLI
2.8 — Outputs agent-ready
2.9 — UX vertical y cierre
```

## Capacidades reales

- validación de columnas requeridas e inesperadas, tipos, nullability, valores
  permitidos y rangos explícitos;
- comparación factual de row count, columnas, tipos lógicos, nullability,
  cardinalidad, rangos y valores observados;
- interpretación separada de schema drift únicamente para cambios
  estructurales;
- persistencia JSON de suggested schemas;
- CLI para `profile`, `inspect`, `suggest-schema`, `validate`, `compare` y
  `drift`;
- outputs JSON agent-ready con códigos externos estables;
- representación vertical de los modelos públicos en notebook y REPL.

La subfase v0.3.1 publica reportes Python sobre los mismos resultados
estructurados, sin modificar la versión del paquete (`0.2.0`) ni los formatos
externos. La API pública actual es:

```python
vzor.version()
vzor.profile(df)
vzor.observed_schema(df)
vzor.suggest_schema(df)
vzor.inspect(df)
vzor.validate(df, schema)
vzor.compare(before, after)
vzor.schema_drift(before, after)
```

Las nuevas funciones devuelven reportes inmutables con un resultado completo y
un resumen; las reglas de negocio se mantienen en Rust.

## Contratos de versión independientes

```text
Package version:             0.3.2
Persistence format_version:  1
Agent output_version:         1
```

El número de versión del paquete no modifica automáticamente ninguno de los dos
formatos externos.

# v0.3 — Madurez, reporting y UX avanzada — COMPLETE

Objetivo cumplido: mejorar la experiencia de uso recurrente y la presentación
sin debilitar los contratos estructurados.

## v0.3.1 — Reporting y resúmenes

**COMPLETE.** `validate`, `compare` y `schema_drift` exponen reportes Python
inmutables, deterministas y orientados a notebook/REPL. La CLI, los outputs
agent-ready y el formato de persistencia no cambian.

## v0.3.2 — Human-readable summaries

**COMPLETE.** `InspectionReport`, `ValidationReport`, `ComparisonReport` y
`SchemaDriftReport` exponen la propiedad derivada `human_summary`. Sus textos
son breves, deterministas y se generan exclusivamente desde sus summaries; no
se modifican el payload agent-ready, la CLI ni los formatos externos.

## v0.3.3 — UX Python avanzada

**COMPLETE.** Los reportes delegan estados y conteos frecuentes y ofrecen
tuplas filtradas (`errors`, `warnings`, `added`, `removed`, `changed` y
`unchanged`) sin duplicar estado. Los modelos de profile, observed schema y
suggested schema conservan su lookup exacto y case-sensitive `column(name)`.
El `repr`, la igualdad, la CLI y los formatos externos permanecen intactos.

## v0.3.4 — UX CLI

**COMPLETE.** La ayuda general y por comando explica propósito, archivos y
exit codes. Errores de rutas, formatos de entrada, carga y persistencia se
presentan limpiamente en stderr con exit code `2`; la JSON agent-ready, sus
exit codes condicionales y los formatos externos no cambian.

## v0.3.5 — AGENTS.md

**COMPLETE.** La raíz del repositorio incluye `AGENTS.md`, una guía opcional en
inglés para asistentes/agentes sobre API pública, arquitectura, semánticas y
contratos estables. No forma parte del runtime ni modifica CLI, persistencia o
formatos externos.

## v0.3.6 — Documentación y ejemplos profesionales

**COMPLETE.** Se añaden README en inglés, documentación de inicio/conceptos/
workflows y un ejemplo autocontenido que usa exclusivamente la API pública.
No se modifican runtime, CLI, persistencia ni formatos externos.

## v0.3.7 — Hardening final y cierre

**COMPLETE.** Se auditan API, contratos, documentación, determinismo,
dependencias, empaquetado y casos límite; se incorpora la licencia MIT formal,
se valida un wheel release desde un entorno limpio y se cierra el paquete como
`0.3.0`. `output_version = 1` y `format_version = 1` permanecen sin cambios.

## Package release v0.3.2 — Compact Report Repr

**COMPLETE.** Los cuatro reportes públicos muestran en `repr` su summary
completo y previews estructurales de hasta cinco elementos. Inspection evita
expandir perfiles, schemas y estadísticas; validation y drift muestran issues
compactos; comparison no incluye snapshots before/after. Los datos, accessors,
`human_summary`, HTML, CLI y contratos versionados permanecen sin cambios.

## Package release v0.3.1 — HTML reporting + bounded repr

**COMPLETE.** Los cuatro reportes públicos incorporan `to_html(path)` para una
vista completa, local y autosuficiente. El `repr` limita cada colección a cinco
elementos completos y muestra `... N more items`, sin modificar los datos ni
los accessors. La CLI y los contratos versionados permanecen sin cambios.

No convertir reportes o recomendaciones en la fuente de verdad: los resultados
estructurados siguen siendo el contrato.

# v0.4 — Hardening, performance, escalabilidad y backends

Objetivo: robustecer y medir el motor para datasets mayores y backends
adicionales.

Áreas candidatas:

- hardening y casos límite;
- profiling y validación de rendimiento;
- reducción medida de copias;
- paralelización donde los benchmarks la justifiquen;
- interoperabilidad con Arrow;
- evaluación de un backend Polars;
- escalabilidad y consumo de memoria.

Vzor seguirá complementando pandas/Polars. No son objetivos centrales de v0.4:

- un `read_csv` propio;
- un `read_excel` propio;
- una ingestion layer pública;
- reemplazar los lectores o DataFrames del ecosistema.

# v0.5 — Excel / Power BI exports

Objetivo: exportar resultados de Vzor a flujos de trabajo habituales de
analistas sin convertir Vzor en una herramienta BI.

Áreas candidatas:

- exportaciones Excel;
- artefactos consumibles por Power BI;
- plantillas de reporte para validación y drift;
- preservación del machine payload como fuente de verdad.

# Fuera del roadmap comprometido

- plataforma cloud;
- base de datos propia;
- dashboard SaaS;
- ETL completo;
- agente IA integrado;
- LLM como dependencia;
- corrección automática de reglas de negocio;
- sistema de plugins complejo.

# Regla de desarrollo

Cada versión debe cerrar sus invariantes, pruebas y contratos antes de ampliar
la siguiente:

```text
v0.1 = entender
v0.2 = validar y operar
v0.3 = madurar y reportar
v0.4 = robustecer y escalar
v0.5 = exportar
```

Principio rector:

> Detectar antes de corregir. Observar antes de restringir. Validar antes de
> confiar.

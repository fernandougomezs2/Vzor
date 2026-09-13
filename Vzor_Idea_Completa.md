# Vzor

> **Vzor es una capa de confianza para datos.** Complementa pandas y otros
> backends; no pretende reemplazarlos ni convertirse en un motor general de
> ingesta.

Estado actual: **Vzor v0.3.2 — Compact Report Repr — COMPLETE**. La subfase
v0.4.1 cerró la infraestructura de benchmarks locales y el inventario de
memoria. v0.4.2-A cerró la eliminación de clones internos redundantes de
`DatasetInput`. v0.4.2-B cerró la reducción de materialización transitoria en
la frontera privada pandas/PyO3 y v0.4.2-C eliminó clones redundantes de
strings durante el conteo exacto de únicos. v0.4.2-D redujo trabajo interno de
schema drift que no forma parte de su contrato y v0.4.2-E cerró la auditoría y
la matriz final de rendimiento documentada; no modifican el runtime público ni
implican soporte general para datasets de 5M filas. Los reportes
mantienen todos sus datos y HTML completo, mientras que su `repr` de alto nivel
presenta summaries y previews estructurales acotados. El paquete es `0.3.2`.

## Contrato real de la API Python

La API Python pública actual es:

```python
vzor.__version__
vzor.version()
vzor.profile(df)
vzor.observed_schema(df)
vzor.suggest_schema(df)
vzor.inspect(df)
vzor.validate(df, schema)
vzor.compare(before, after)
vzor.schema_drift(before, after)
```

`validate`, `compare` y `schema_drift` devuelven reportes inmutables con
`result` completo y `summary` profesional. Delegan las reglas y el orden al
core Rust existente. La persistencia soportada es JSON. La CLI emite JSON
agent-ready por defecto y no utiliza una opción `--json`.

Los cuatro reportes públicos exponen `to_html(path)`. El `repr` de alto nivel
muestra el summary completo y hasta cinco previews estructurales por colección,
señalando el resto con `... N more items`; el HTML y los objetos conservan el
contenido completo y los modelos individuales mantienen su detalle.

La CLI admite CSV mediante pandas y reconoce rutas Excel y Parquet cuando está
instalado el engine opcional correspondiente de pandas. Vzor no declara esos
engines como dependencias runtime. Mantiene stdout exclusivamente para
resultados y stderr exclusivamente para errores. Ejemplos habituales:

```text
vzor inspect data.csv
vzor validate data.csv --schema schema.json
vzor compare before.csv after.csv
vzor drift before.csv after.csv
```

`AGENTS.md` es documentación técnica en inglés para asistentes de código. No
es leído, importado ni requerido por Vzor en runtime.

La documentación humana en inglés se organiza en `README.md`, `docs/` y
`examples/basic_workflow.py`: introducción rápida, conceptos, workflows
profesionales y un flujo ejecutable sin archivos externos ni red.

Los cuatro reportes públicos (`inspect`, `validate`, `compare` y
`schema_drift`) también exponen `human_summary`: un texto corto en inglés que
deriva exclusivamente de `summary`, sin volver a inspeccionar los datos.

```python
report = vzor.validate(df, schema)
print(report.human_summary)
# Validation failed: 2 errors, 0 warnings.

print(report.is_valid)
print(report.error_count)
for issue in report.errors:
    print(issue)

comparison = vzor.compare(before, after)
for column in comparison.changed:
    print(column.name)

inspection = vzor.inspect(df)
print(inspection.row_count, inspection.column_count)

profile = vzor.profile(df)
sales = profile.column("sales")  # exact, case-sensitive lookup
```

Las secciones posteriores describen también la visión de producto. Los ejemplos
con `save_schema`, `load_schema`, YAML o `--json` son API conceptual futura.

## Visión general

**Vzor** es una **librería para Python con un motor principal escrito en Rust**, diseñada para ayudar a analistas de datos, desarrolladores, pipelines y agentes de IA a **perfilar datasets, proponer contratos de datos, validar información entrante y detectar cambios antes de que afecten análisis, dashboards o procesos automáticos**.

La idea central es convertir un proceso normalmente manual:

```text
abrir dataset
→ revisar columnas
→ buscar nulos
→ revisar tipos
→ detectar valores extraños
→ decidir reglas
→ repetir todo en el siguiente archivo
```

en un flujo reutilizable:

```text
Dataset
   ↓
Profiling automático
   ↓
Esquema observado
   ↓
Contrato de datos sugerido
   ↓
Revisión humana
   ↓
Contrato aprobado
   ↓
Validación recurrente
   ↓
Detección de errores y schema drift
```

La filosofía de Vzor puede resumirse como:

> **Profile once. Define the contract. Validate forever.**

---

# 1. Problema que resuelve

## 1.1 Exploración manual repetitiva

Cada vez que llega un CSV, Excel, Parquet o DataFrame nuevo, un analista suele revisar manualmente:

- columnas;
- tipos;
- nulos;
- duplicados;
- valores únicos;
- categorías;
- rangos;
- fechas;
- outliers;
- inconsistencias de texto;
- errores de captura.

Vzor automatiza esa primera inspección.

## 1.2 Falta de contratos de datos

En muchos proyectos las reglas del dataset existen solo de manera implícita:

```text
cliente_id no debería tener nulos
monto debería ser positivo
fecha debería ser datetime
region debería contener valores conocidos
pedido_id debería ser único
```

Estas reglas suelen estar en la memoria del analista, dispersas en notebooks o directamente sin documentar.

Vzor convierte esas expectativas en un **contrato de datos explícito y reutilizable**.

## 1.3 Cambios silenciosos

Un pipeline puede funcionar correctamente durante meses y después recibir:

```text
precio: float → string
```

O:

```text
cliente_id:
0% nulos → 8% nulos
```

O una columna nueva:

```text
descuento
```

O una columna eliminada:

```text
codigo_promocion
```

Estos cambios pueden romper scripts o producir dashboards y KPIs incorrectos sin que el problema sea evidente de inmediato.

Vzor busca detectarlos antes de que los datos sigan avanzando.

---

# 2. Qué es Vzor

Vzor será una **librería**, no un framework.

El usuario mantiene el control del flujo:

```python
import vzor

profile = vzor.profile(df)
result = vzor.validate(df, schema)
```

Vzor no obliga a estructurar todo el proyecto alrededor de él.

Definición técnica:

> **Vzor is a Rust-powered Python library for data profiling, data contracts, validation and schema drift detection.**

En español:

> **Vzor es una librería para Python, impulsada por un motor en Rust, orientada al profiling, contratos, validación y detección de cambios en datos.**

---

# 3. Objetivo principal

Vzor no busca ser simplemente otra herramienta de EDA.

Su núcleo será:

```text
profiling
    ↓
schema suggestion
    ↓
human approval
    ↓
data contract
    ↓
validation
    ↓
schema drift detection
```

La parte más importante es transformar una exploración inicial en un contrato reutilizable.

---

# 4. Principios de diseño

## Rust desde el inicio

Rust formará parte del núcleo desde la primera versión.

No como elemento de marketing, sino como motor de:

- profiling;
- estadísticas;
- validaciones;
- comparación de datasets;
- schema drift;
- procesamiento intensivo.

## Python como interfaz principal

El usuario normal trabajará con:

```python
import vzor
```

y no con bindings de bajo nivel.

Python será responsable principalmente de:

- API pública;
- integración con pandas;
- configuración;
- reportes;
- serialización;
- ergonomía.

## Detectar antes de corregir

Vzor no debe borrar o modificar datos automáticamente de forma agresiva.

No debería decidir por sí solo:

- eliminar outliers;
- eliminar filas;
- imputar medias o medianas;
- reemplazar valores de negocio;
- declarar inválido un valor negativo;
- convertir valores observados en valores permitidos.

La herramienta debe ayudar a decidir, no sustituir el conocimiento del negocio.

## Separar observaciones de restricciones

Si un dataset contiene edades entre 18 y 65, Vzor puede registrar:

```yaml
observed:
  min: 18
  max: 65
```

pero no debe concluir automáticamente:

```yaml
constraints:
  min: 18
  max: 65
```

Las restricciones de negocio deben ser revisadas o confirmadas por el usuario.

## Machine-readable by design

Las salidas importantes deben ser estructuradas y estables, no depender únicamente de texto libre.

---

# 5. Arquitectura general

```text
┌───────────────────────────────┐
│           Python API          │
│                               │
│ pandas integration            │
│ configuration                 │
│ reports                       │
│ schema editing                │
└───────────────┬───────────────┘
                │
                │ PyO3 / maturin
                ▼
┌───────────────────────────────┐
│          Vzor Core            │
│             Rust              │
│                               │
│ profiling                     │
│ statistics                    │
│ validation                    │
│ schema comparison             │
│ drift detection               │
│ rules engine                  │
└───────────────┬───────────────┘
                │
                ▼
       NumPy / Arrow / Data
```

Conceptualmente:

```text
Python = interfaz
Rust   = motor
```

---

# 6. Stack tecnológico

## Lenguajes

### Python 3.10+

Para:

- API pública;
- integración con pandas;
- configuración;
- notebooks;
- reportes;
- serialización;
- experiencia de usuario.

### Rust

Para:

- profiling;
- estadísticas;
- validación;
- schema drift;
- procesamiento pesado;
- comparaciones;
- optimización.

## Interoperabilidad

### PyO3

Bindings entre Rust y Python.

### maturin

Construcción y distribución del paquete Python que incluye el componente Rust.

## Datos

### pandas

Primera integración oficial.

### NumPy

Intercambio eficiente de arrays cuando sea apropiado.

### Apache Arrow

Objetivo importante para minimizar copias y facilitar compatibilidad futura.

Arquitectura deseada:

```text
pandas ─┐
        │
Polars ─┼──► Arrow ───► Vzor Core
        │
otros ──┘
```

### Polars

Soporte futuro, no requisito del MVP.

## Serialización

- JSON para agentes, APIs y automatización.
- YAML para edición humana de contratos en una versión futura.

## Reportes

- HTML;
- Jinja2;
- matplotlib o Plotly de forma opcional.

## Testing

- `pytest` en Python;
- `cargo test` en Rust.

## Benchmarking

- Criterion en Rust;
- benchmarks comparativos con pandas cuando tenga sentido.

---

# 7. API principal

El MVP se concentrará en:

```python
profile(df)
suggest_schema(df)
validate(df, schema)
compare(old, new)
```

Además:

```python
save_schema(schema)
load_schema(path)
```

---

# 8. `profile(df)`

Realiza un diagnóstico automático del dataset.

```python
profile = vzor.profile(df)
```

## Información general

- filas;
- columnas;
- memoria;
- duplicados;
- porcentaje global de nulos.

## Por columna

Vzor podrá calcular:

- nombre;
- dtype;
- tipo lógico;
- nulos;
- porcentaje de nulos;
- valores únicos;
- cardinalidad;
- mínimo;
- máximo;
- media;
- mediana;
- desviación estándar;
- percentiles;
- frecuencias;
- valores dominantes;
- outliers;
- memoria.

Ejemplo:

```text
Column: municipio

dtype: object
logical_type: categorical
rows: 128430
nulls: 0.4%
unique: 11

Top values:
Aguascalientes    41.8%
Jesús María       17.2%
Rincón de Romos    9.4%
```

Vzor también puede detectar inconsistencias potenciales:

```text
Possible inconsistent categories:

"Jesus Maria"
"Jesús María"
"JESUS MARIA"
" Jesús María "
```

---

# 9. Recomendaciones

Vzor podrá sugerir acciones sin ejecutarlas automáticamente.

Ejemplo:

```text
Recommendation

municipio has:
11 unique values
1.2M rows
dtype: object

Potential categorical column
```

O:

```text
cliente_id
99.8% unique values
Possible identifier column
```

Las recomendaciones serán explícitamente recomendaciones, no decisiones automáticas.

---

# 10. `suggest_schema(df)`

Después del profiling:

```python
schema = vzor.suggest_schema(df)
```

Vzor genera un esquema inicial con observaciones.

```yaml
version: 1

dataset: ventas

columns:

  pedido_id:
    type: integer
    nullable: false
    observed:
      min: 1
      max: 982304

  monto:
    type: number
    nullable: false
    observed:
      min: -500
      max: 28000

  fecha:
    type: datetime
    nullable: false

  region:
    type: string
    nullable: false
    observed_values:
      - Norte
      - Centro
      - Sur
```

---

# 11. Revisión humana y contrato

El analista puede transformar observaciones en reglas reales.

```yaml
monto:
  type: number
  nullable: false
  constraints:
    min: 0
```

O:

```yaml
region:
  type: string
  constraints:
    allowed_values:
      - Norte
      - Centro
      - Sur
      - Oeste
```

Una vez aprobado:

```python
schema.save("ventas.vzor.yaml")
```

Ese archivo se convierte en el contrato del dataset y puede guardarse en Git.

---

# 12. `validate(df, schema)`

Valida un dataset contra su contrato.

```python
result = vzor.validate(df, schema)
```

Validaciones iniciales:

- columnas requeridas;
- columnas adicionales;
- tipos;
- nullable;
- unique;
- min/max;
- allowed values;
- formatos;
- regex en versiones posteriores.

Ejemplo:

```text
VZOR VALIDATION REPORT

Rows checked: 105320
Columns checked: 12

PASSED
✓ pedido_id type
✓ pedido_id uniqueness
✓ fecha type
✓ monto nullable

WARNINGS
⚠ region contains unseen values:
    "Noroeste"

ERRORS
✗ monto
    14 values below minimum 0

✗ cliente_id
    328 null values

STATUS: FAILED
```

Un resultado podrá exponer:

```python
result.valid
result.errors
result.warnings
result.metrics
result.summary()
result.to_dict()
result.to_json()
```

---

# 13. Códigos de incidencia estables

Las incidencias tendrán códigos predecibles.

Ejemplos:

```text
VZOR_NULL_RATE_HIGH
VZOR_TYPE_MISMATCH
VZOR_NEW_COLUMN
VZOR_MISSING_COLUMN
VZOR_ALLOWED_VALUE_VIOLATION
VZOR_RANGE_VIOLATION
VZOR_DUPLICATE_VALUE
VZOR_SCHEMA_DRIFT
```

Ejemplo JSON:

```json
{
  "column": "cliente_id",
  "issue_code": "VZOR_NULL_RATE_HIGH",
  "severity": "warning",
  "observed": 0.087,
  "expected_max": 0.01
}
```

---

# 14. Diseño para agentes de IA

Vzor será diseñado desde el inicio para que un agente o LLM pueda interpretar sus resultados de forma confiable.

No dependerá solo de mensajes en lenguaje natural.

Ejemplo:

```json
{
  "dataset": "ventas",
  "rows": 105320,
  "columns": 12,
  "status": "warning",
  "issues": [
    {
      "column": "cliente_id",
      "issue_code": "VZOR_NULL_RATE_HIGH",
      "severity": "warning",
      "observed": 0.087,
      "expected_max": 0.01
    }
  ]
}
```

Cada resultado puede incluir:

```text
human_summary
machine_payload
```

Ejemplo:

```json
{
  "human_summary": "La columna cliente_id tiene 8.7% de valores nulos.",
  "machine_payload": {
    "column": "cliente_id",
    "issue_code": "VZOR_NULL_RATE_HIGH",
    "severity": "warning",
    "null_rate": 0.087
  }
}
```

La filosofía será:

> Vzor debe ser entendible por IA, pero no depender de IA.

El core debe ser:

- determinístico;
- testeable;
- reproducible;
- auditable.

---

# 15. CLI para humanos, scripts y agentes

Vzor v0.2.0 incluye una CLI que emite JSON agent-ready por defecto:

```bash
vzor profile ventas.csv
```

```bash
vzor validate ventas.csv --schema ventas.json
```

```bash
vzor compare enero.csv febrero.csv
```

Esto permitirá integrarlo fácilmente con:

- agentes;
- scripts;
- CI/CD;
- servidores;
- automatizaciones.

---

# 16. `compare(old, new)` y schema drift

Una función central será:

```python
drift = vzor.compare(df_old, df_new)
```

Ejemplo:

```text
VZOR DATA DRIFT

SCHEMA CHANGES

+ descuento
  new column

- codigo_promocion
  removed column

~ precio
  float64 → string

QUALITY CHANGES

! cliente_id
  null rate:
  0.2% → 8.7%

! region
  cardinality:
  4 → 7

NEW VALUES

region:
  + Oeste
  + Noroeste
```

Schema drift incluirá cambios como:

- columnas nuevas;
- columnas eliminadas;
- cambios de dtype;
- nullable;
- cardinalidad;
- categorías nuevas.

---

# 17. Data drift

En versiones posteriores Vzor podrá comparar cambios de comportamiento.

Ejemplo:

```text
ticket_promedio
enero:   $780
febrero: $1240
change: +58.9%
```

Vzor podrá reportar:

```text
SIGNIFICANT DISTRIBUTION CHANGE
```

sin afirmar automáticamente que exista un error.

Se distinguirá claramente entre:

```text
schema drift
```

y:

```text
data drift
```

---

# 18. Safe Fix

No se utilizará un `fix=True` agresivo dentro de `validate()`.

En su lugar podrá existir:

```python
vzor.safe_fix(df)
```

Solo para transformaciones determinísticas y seguras.

Ejemplos:

```text
" Norte "
→ "Norte"
```

```text
" TRUE "
→ True
```

```text
"2026-01-15"
→ datetime
```

si la conversión es inequívoca.

Principio:

> **Vzor puede corregir representación; no debe inventar significado.**

---

# 19. Core en Rust

El núcleo podrá llamarse:

```text
vzor-core
```

Responsabilidades:

```text
profiling
null counting
unique counting
statistics
percentiles
outlier detection
categorical frequencies
validation
schema comparison
schema drift
```

Estructuras internas posibles:

```rust
ColumnProfile
DatasetProfile
ColumnSchema
DatasetSchema
ValidationRule
ValidationIssue
ValidationResult
SchemaDiff
```

---

# 20. Gestión eficiente de memoria

Un objetivo importante será evitar este patrón:

```text
pandas
↓
copiar 5 GB
↓
Rust
↓
procesar
↓
copiar 5 GB
↓
Python
```

porque puede eliminar gran parte de la ventaja del motor Rust.

Se estudiará el uso de:

- NumPy buffers;
- Arrow arrays;
- Arrow C Data Interface;
- zero-copy cuando sea posible.

Aunque pandas sea la primera integración, el core no debería depender conceptualmente de pandas.

Arquitectura futura:

```text
pandas ─┐
        │
Polars ─┼──► Vzor Core
        │
Arrow ──┘
```

---

# 21. Reporte HTML

Vzor podrá generar:

```python
profile.save_html("ventas.html")
```

El reporte inicial incluiría:

```text
Dataset Overview
Rows
Columns
Memory
Duplicates
Null percentage

Column Profiles
Potential Issues
Schema Proposal
Validation
Schema Drift
Recommendations
```

El reporte visual será complementario.

La fuente de verdad seguirá siendo el resultado estructurado.

---

# 22. Estructura del proyecto

```text
vzor/
│
├── crates/
│   └── vzor-core/
│       ├── src/
│       │   ├── profile/
│       │   ├── schema/
│       │   ├── validation/
│       │   ├── drift/
│       │   ├── types/
│       │   └── lib.rs
│       └── Cargo.toml
│
├── python/
│   └── vzor/
│       ├── __init__.py
│       ├── profile.py
│       ├── schema.py
│       ├── validation.py
│       ├── drift.py
│       ├── report.py
│       └── io.py
│
├── tests/
├── benchmarks/
├── examples/
├── docs/
├── pyproject.toml
├── Cargo.toml
└── README.md
```

---

# 23. MVP — Vzor 0.1

La primera versión debe ser pequeña, rápida y confiable.

## Profiling

```python
profile(df)
```

Soporte inicial:

- tipos;
- nulos;
- únicos;
- min/max;
- media;
- mediana;
- percentiles;
- cardinalidad.

## Schema

```python
suggest_schema(df)
```

Soporte:

- type;
- nullable;
- observed range;
- observed categories.

## Validation

```python
validate(df, schema)
```

Soporte:

- columnas;
- tipos;
- nullable;
- unique;
- min/max;
- allowed values.

## Drift

```python
compare(old, new)
```

Soporte:

- columnas nuevas;
- columnas eliminadas;
- cambios de dtype;
- cambios de null rate;
- categorías nuevas.

## Storage

```python
save_schema()
load_schema()
```

Formatos:

- JSON;
- YAML.

---

# 24. Roadmap posterior

## Vzor 0.3 — Madurez, reporting y UX avanzada

```text
reporting HTML complementario
UX avanzada de notebook
documentación y diagnósticos maduros
integraciones de pipeline
benchmarks iniciales
safe fixes determinísticos, si se define su contrato
```

## Vzor 0.4 — Hardening, performance, escalabilidad y backends

```text
hardening y casos límite
performance medida
reducción de copias
Arrow
evaluación de backend Polars
escalabilidad y memoria
```

Vzor seguirá siendo complemento de pandas/Polars. Un `read_csv` propio, un
`read_excel` propio y una ingestion layer pública no son objetivos centrales.

## Vzor 0.5 — Excel / Power BI exports

```text
exportaciones Excel
artefactos consumibles por Power BI
plantillas de resultados de validación y drift
```

---

# 25. Integraciones futuras

Posibles integraciones:

- Airflow;
- Prefect;
- Dagster;
- dbt;
- FastAPI;
- notebooks;
- CI/CD;
- GitHub Actions;
- Power BI preprocessing;
- ETL propios;
- agentes IA.

---

# 26. Dónde se aplicará

## Análisis de datos

Antes de trabajar con un dataset:

```text
CSV / Excel / Parquet
↓
Vzor
↓
limpieza
↓
análisis
↓
KPIs
↓
visualización
```

## Power BI

```text
Fuente de datos
↓
Vzor validation
↓
dataset aprobado
↓
Power BI
```

Vzor puede detectar problemas antes de actualizar un dashboard.

## SQL

```text
CSV
↓
Vzor
↓
validación
↓
INSERT / COPY
↓
Database
```

## Pipelines

```text
Source
↓
Extract
↓
Vzor Quality Gate
↓
Transform
↓
Load
↓
Dashboard
```

## APIs y backend

Un backend puede validar datasets antes de almacenarlos o procesarlos.

## Agentes IA

Un agente puede ejecutar:

```bash
vzor profile ventas.csv --json
```

y consumir resultados estructurados para:

- solicitar revisión;
- explicar problemas;
- crear tickets;
- detener un pipeline;
- proponer correcciones;
- comparar periodos.

---

# 27. Ejemplo de uso real

Cada semana llega:

```text
ventas_semana.csv
```

Código:

```python
import pandas as pd
import vzor

df = pd.read_csv("ventas_semana.csv")

schema = vzor.load_schema("ventas.yaml")

result = vzor.validate(df, schema)

if not result.valid:
    print(result.summary())
    raise SystemExit(1)
```

Después:

```text
Vzor
↓
limpieza
↓
análisis
↓
KPIs
↓
Power BI
```

Vzor funciona como una primera barrera de calidad.

---

# 28. Ejemplo de experiencia completa

```python
import pandas as pd
import vzor

df = pd.read_csv("ventas.csv")

# 1. Profiling
profile = vzor.profile(df)
print(profile.summary())

# 2. Schema sugerido
schema = vzor.suggest_schema(df)

# 3. Ajustes del analista
schema["monto"].constraints.min = 0
schema["pedido_id"].unique = True

# 4. Guardar contrato
vzor.save_schema(schema, "ventas.yaml")
```

Un mes después:

```python
new_df = pd.read_csv("ventas_nuevo.csv")

schema = vzor.load_schema("ventas.yaml")

result = vzor.validate(new_df, schema)

if not result.valid:
    print(result.summary())
```

Comparación:

```python
drift = vzor.compare(df, new_df)
print(drift.summary())
```

---

# 29. Qué no es Vzor

Vzor no será inicialmente:

- plataforma cloud;
- dashboard BI;
- herramienta ETL completa;
- framework web;
- sistema de Machine Learning;
- reemplazo de pandas;
- reemplazo de Power BI;
- limpiador automático total;
- agente IA autónomo.

---

# 30. Prioridades técnicas

Orden recomendado:

```text
1. Correctness
2. API clara
3. Contratos
4. Validación
5. Drift
6. Salidas estructuradas
7. Rendimiento
8. Reportes
9. Integraciones
10. Funciones avanzadas
```

Rust estará presente desde el inicio, pero sin convertir el proyecto en sobreingeniería.

La optimización se basará en:

- benchmarks;
- profiling;
- mediciones de memoria;
- pruebas con distintos tamaños de dataset.

---

# 31. Valor práctico

Para un analista de datos, Vzor puede convertirse en una herramienta reutilizable para:

- revisar datasets;
- detectar errores antes de analizar;
- proteger dashboards;
- documentar reglas;
- comparar archivos recurrentes;
- automatizar validaciones;
- mantener consistencia entre periodos;
- trabajar con agentes IA;
- integrar controles de calidad en scripts y pipelines.

---

# 32. Definición final

> **Vzor es una librería Python con un motor de calidad de datos escrito en Rust. Su función es perfilar datasets, generar esquemas observados, sugerir contratos de datos, validar nueva información y detectar schema drift antes de que los datos incorrectos lleguen a análisis, dashboards, bases de datos o pipelines.**

Está diseñada para ser utilizada por:

```text
Analistas
Developers
Data Engineers
Pipelines
Automatizaciones
Agentes IA
```

y para producir resultados que sean simultáneamente:

```text
human-readable
machine-readable
agent-readable
```

Su núcleo será determinístico y no dependerá de inteligencia artificial.

La IA será un consumidor posible de Vzor, no una dependencia.

---

# Principio rector

> **Detectar antes de corregir.**  
> **Observar antes de restringir.**  
> **Validar antes de confiar.**

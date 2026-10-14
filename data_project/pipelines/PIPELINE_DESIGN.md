# PIPELINE_DESIGN — Weekly Office & Programme Performance

## 1. Estado actual

El repositorio ya tiene una capa de telemetría operativa funcional:

- `services/api/telemetry/routes.py` recibe batches de eventos, valida el envelope y los persiste en `telemetry_events`.
- `services/models.py` define `TelemetryEventRecord` con `timestamp`, `service`, `event_type`, `level`, `value`, `message` y `tags`.
- El endpoint `GET /telemetry/report` ya responde preguntas técnicas del equipo de ingeniería: volumen, tasa de errores, latencia y actividad por tipo de evento.
- La documentación de telemetría en `docs/telemetry/telemetry-plan.md` y `docs/telemetry/event-schemas.json` ya define los eventos obligatorios del negocio de Nexova, entre los que están `inbound_order_created`, `outbound_order_created`, `stock_threshold_triggered` y `kit_cost_variance_detected`.

En otras palabras, el repositorio sabe `qué eventos ocurrieron` y `cómo se comporta el sistema`, pero aún no responde una pregunta del negocio: `¿cómo está cada oficina y cada programa en inversión y entrega de material de formación, por semana?`

## 2. Brecha de negocio

El actual reporte técnico es útil para ingeniería, pero no sirve a Laura (CEO) ni a Elena (Gerente de L&D). No existe una capa de reporting de negocio que consolide, por oficina y por programa, los siguientes indicadores semanales:

- costo de material por oficina/programa,
- kits entregados,
- frecuencia de escasez,
- frecuencia de variación de costo.

La falta de este agregado hace que la decisión de compra, reorden, reasignación y negociación con proveedores siga dependiendo de procesos manuales y de hojas de cálculo. Esa brecha es la que justifica este pipeline nuevo.

## 3. Propósito del pipeline

`Producción del consolidado semanal de desempeño por oficina y programa que alimenta el Reporte Semanal de Desempeño de Nexova, calculando los KPI de costo de material, kits entregados, escasez y variación de costo a partir de los eventos obligatorios de telemetría: inbound_order_created, outbound_order_created, stock_threshold_triggered y kit_cost_variance_detected.`

## 4. Fuentes de datos y formato de extracción

### 4.1 Fuente principal

La fuente de verdad del pipeline será la tabla `telemetry_events` en modo lectura.

Se filtrará por los eventos obligatorios del negocio:

- `inbound_order_created`
- `outbound_order_created`
- `stock_threshold_triggered`
- `kit_cost_variance_detected`

El pipeline no escribe en `telemetry_events`; solo consulta los registros ya almacenados. La ventana de interés es una semana ISO, con `week_start` identificado como el lunes (UTC) de cada semana.

### 4.2 Formato de eventos que alimenta el pipeline

Los payloads ya están definidos en `docs/telemetry/event-schemas.json` y cumplen el contrato necesario para esta v1.

Ejemplos relevantes:

- `inbound_order_created` incluye `office`, `programme_id`, `currency`, `unit_cost`, `quantity`, `supplier_id` y `inbound_order_id`.
- `outbound_order_created` incluye `office`, `programme_id`, `currency`, `quantity`, `outbound_order_id` y `recipient_type`.
- `stock_threshold_triggered` incluye `office`, `programme_id`, `current_stock`, `minimum_threshold`, `currency`.
- `kit_cost_variance_detected` incluye `office`, `programme_id`, `currency`, `actual_unit_cost`, `expected_unit_cost`, `threshold_percentage`, `supplier_id` y `inbound_order_id`.

La frecuencia de extracción será semanal y programada para la mañana del lunes, con posibilidad de ejecución manual por el equipo de negocio o de ingeniería.

### 4.3 Granularidad y columnas objetivo

La agregación final debe tener una fila por:

- `office`
- `programme_id`
- `week_start`

Y los campos calculados por fila:

- `total_material_cost` = suma de costos de `inbound_order_created`
- `kits_delivered_count` = conteo de `outbound_order_created`
- `shortage_events_count` = conteo de `stock_threshold_triggered`
- `cost_variance_events_count` = conteo de `kit_cost_variance_detected`
- `currency` = `EUR` o `USD`, según la oficina

No se mezclan monedas en una misma fila. Valencia reporta en EUR y Miami en USD, y ambas aparecen como filas distintas bajo el mismo `week_start` si corresponde.

## 5. Tabla de destino

La salida del pipeline vive en un esquema dedicado `reporting`, no en `telemetry_events`.

La tabla exacta será:

```sql
create table reporting.weekly_office_program_performance (
  id uuid primary key default gen_random_uuid(),
  office text not null,
  programme_id text not null,
  week_start date not null,
  total_material_cost numeric not null default 0,
  kits_delivered_count integer not null default 0,
  shortage_events_count integer not null default 0,
  cost_variance_events_count integer not null default 0,
  currency text not null,
  computed_at timestamptz not null default now(),
  unique (office, programme_id, week_start)
);
```

También se usará una tabla de control de ejecuciones:

```sql
create table reporting.pipeline_runs (
  run_id uuid primary key default gen_random_uuid(),
  pipeline_name text not null,
  status text not null,
  week_start date not null,
  started_at timestamptz not null default now(),
  finished_at timestamptz,
  records_read integer not null default 0,
  records_written integer not null default 0,
  rows_upserted integer not null default 0,
  error_message text,
  triggered_by text not null default 'scheduled',
  metadata jsonb not null default '{}'::jsonb
);
```

La clave de idempotencia será el `unique (office, programme_id, week_start)` de la tabla `reporting.weekly_office_program_performance`.

## 6. Flujo de datos

```mermaid
flowchart LR
    A[telemetry_events\nsource system of record] --> B[Extract business events\nfilter event_type IN (...) ]
    B --> C[Transform & aggregate\nby office + programme_id + week_start]
    C --> D[Load reporting.weekly_office_program_performance\nUPSERT by unique key]
    D --> E[Expose endpoints in services/reporting\nweekly KPI feed + run metadata]
```

### 6.1 Etapa 1 — Extracción

Se consulta la tabla `telemetry_events` y se filtran solo los eventos del negocio relevantes para la v1.

Se recuperan solo los campos necesarios:

- `timestamp`
- `event_type`
- `tags` / `properties`
- `eventId` para deduplicación y auditoría

Se aplica una ventana temporal por semana ISO y se descartan eventos con `event_type` no admitidos.

### 6.2 Etapa 2 — Transformación

Se convierten los eventos en una tabla de agregación semanal con este patrón:

- `inbound_order_created`: cada fila aporta `unit_cost * quantity` en la moneda local de la oficina.
- `outbound_order_created`: cada fila suma `1` al conteo del programa/oficina/semana.
- `stock_threshold_triggered`: cada fila suma `1` al conteo de escasez.
- `kit_cost_variance_detected`: cada fila suma `1` al conteo de variación de costo.

La transformación debe mantener el origen de cada cálculo y la semana en la que ocurre.

### 6.3 Etapa 3 — Carga

Se usa `INSERT ... ON CONFLICT (office, programme_id, week_start) DO UPDATE SET ...` para garantizar la idempotencia de la tabla de reporting.

Se persiste la ejecución en `reporting.pipeline_runs` para dejar rastro de auditoría, incluyendo la ventana procesada, el número de filas leídas y la marca temporal de finalización.

## 7. Manejo de registros existentes y actualizaciones tardías

La estrategia para eventos que actualizan registros ya procesados y para eventos tardíos es la siguiente:

1. Se define la clave natural de la fila agregada como `(office, programme_id, week_start)`.
2. La carga usa upsert sobre esa clave, no insert simple.
3. La ejecución guarda `computed_at` actual para la fila y reemplaza los valores derivados para esa ventana si la semana vuelve a recalcularse.
4. Si llega un evento tardío para una semana ya cargada, se re-ejecuta el pipeline sobre esa ventana y se vuelve a calcular la agregación, dejando evidencia en `pipeline_runs` de la re-carga.
5. El sistema registra `run_id` y `week_start` para distinguir la última recomputación de una versión anterior.

Esto evita duplicados, conserva el rastro y hace que una corrección posterior pueda auditarse sin perder consistencia.

## 8. Estrategia de idempotencia y recuperabilidad

### 8.1 Idempotencia en la segunda corrida

Si la carga falla a mitad del proceso, la siguiente ejecución debe dejar el resultado final igual al de una corrida limpia.

La estrategia será:

- usar una tabla intermedia de staging para preparar la agregación semanal,
- validar la ventana `week_start` y el número esperado de filas,
- hacer el merge final con upsert de la clave `(office, programme_id, week_start)`,
- guardar un `run_id` único por ejecución,
- considerar la ventana como atómica para la carga final.

En consecuencia, la segunda ejecución no duplica filas ni corrompe los resultados ya cargados. Si la primera mitad anterior ya había escrito datos válidos, la segunda re-ejecuta la misma ventana y actualiza la fila en el mismo punto de clave única.

### 8.2 Recuperabilidad

La recuperación se basa en dos niveles:

- `pipeline_runs`: guarda el estado de ejecución y lo que fue procesado.
- `reporting.weekly_office_program_performance`: mantiene la vista final consistente para consultas de negocio, aunque la ejecución falle en una iteración previa.

Con esto, si hay pérdida de conexión, timeout de base de datos o un reintento de la ejecución programada, se puede reanudar por `week_start` y no se pierde la línea base de la tabla de reporting.

## 9. Log de ejecución y observabilidad

Cada ejecución del pipeline dejará un registro mínimo en `reporting.pipeline_runs` con los campos y su propósito:

| Campo | Tipo | Descripción | Por qué importa para auditoría |
|---|---|---|---|
| `run_id` | UUID | Identificador único de la ejecución | Permite asociar todos los eventos del pipeline a una misma corrida |
| `pipeline_name` | text | Nombre del pipeline | Facilita distinguir pipelines futuros que compartan infraestructura |
| `status` | text | `running`, `completed`, `failed` | Indica el estado final y permite detectar ejecuciones incompletas |
| `week_start` | date | Semana ISO que se procesó | Define la partición de negocio sobre la que se trabajó |
| `started_at` | timestamptz | Inicio de la corrida | Permite ordenar y comparar ejecuciones por cronología |
| `finished_at` | timestamptz | Fin de la ejecución | Sirve para medir latencia y detectar bloqueos |
| `records_read` | integer | Número de eventos de `telemetry_events` leídos | Permite comparar volumen de datos con la actividad real |
| `records_written` | integer | Número de filas finales cargadas | Muestra el impacto de la ejecución sobre reporting |
| `rows_upserted` | integer | Cantidad de filas realmente persistidas con upsert | Verifica idempotencia y el tamaño del cambio real |
| `error_message` | text | Mensaje de error si falla | Permite diagnosticar fallos sin regresar a la base sin contexto |
| `triggered_by` | text | `scheduled` o `manual` | Diferencia corridas automáticas y manuales |
| `metadata` | jsonb | Contexto adicional (e.g., source window, filters) | Permite depurar y extender el pipeline en el futuro |

También se puede registrar un heartbeat simple por la lectura de `telemetry_events` para distinguir actividad real de “no hubo eventos” vs. “no corrió el pipeline”.

## 10. Mapeo a Prefect

### 10.1 Flow principal

```python
weekly_office_program_performance_flow(week_start: date | None = None, trigger: str = "scheduled")
```

Este flow orquesta toda la ejecución del pipeline.

### 10.2 Tasks

1. `extract_business_events(week_start)`
   - Lee `telemetry_events`.
   - Filtra por `inbound_order_created`, `outbound_order_created`, `stock_threshold_triggered`, `kit_cost_variance_detected`.
   - Devuelve el conjunto mínimo necesario para agregar.

2. `aggregate_weekly_performance(events)`
   - Agrupa por `(office, programme_id, week_start)`.
   - Calcula `total_material_cost`, `kits_delivered_count`, `shortage_events_count`, `cost_variance_events_count` y `currency`.
   - Genera una tabla intermedia de staging.

3. `load_reporting_table(staging_rows, week_start)`
   - Upsert a `reporting.weekly_office_program_performance`.
   - Marca la fila en `reporting.pipeline_runs` con el `run_id` y el estado final.

4. `record_run_status(run_id, status, metadata, error_message=None)`
   - Guarda el estado final de la ejecución para observabilidad y auditoría.

### 10.3 Estados relevantes

Los estados de Prefect que son directamente útiles aquí son:

- `Running`
- `Completed`
- `Failed`
- `Retrying` (si se reintenta una carga o un acceso a la base)

También es útil un `Cancelled` si la ejecución es interrumpida por una corrida concurrente o por una ventana no válida.

### 10.4 Prefect blocks

Los bloques necesarios serían:

- `DatabaseCredentials` o `SupabaseCredentials` para conectar con la base de datos de reporting.
- `Secret` para la cadena de conexión o la clave del servicio de base de datos.
- `NotificationBlock` opcional para alertar por Slack o email si `status == Failed`.

Esto permite externalizar credenciales, reutilizar la conexión en múltiples flows y atenerse a un patrón de producción.

## 11. Integración con la aplicación y endpoints del negocio

El pipeline debe exponerse como servicio nuevo, separado de `services/telemetry/`.

Se creará un módulo nuevo en `services/reporting/` con responsabilidades limpias:

- `services/reporting/__init__.py`
- `services/reporting/routes.py`
- `services/reporting/service.py` (si se requiere una capa de dominio)

### 11.1 Endpoint 1 — Consulta del KPI consolidado

`GET /reporting/weekly-office-program-performance`

- Parámetro opcional: `week_start`
- Si no se manda, usa la semana calculada más reciente.
- Devuelve todas las combinaciones de oficina/programa para esa semana.

Ejemplo de respuesta:

```json
{
  "week_start": "2026-07-13",
  "entries": [
    {
      "office": "valencia",
      "programme_id": "b2b-sales",
      "total_material_cost": 1240.50,
      "kits_delivered_count": 18,
      "shortage_events_count": 1,
      "cost_variance_events_count": 0,
      "currency": "EUR"
    }
  ]
}
```

Esta ruta invoca la función de pipeline `get_weekly_office_program_performance(week_start)` o un wrapper de lectura desde `data/pipelines/business_performance_pipeline.py`.

### 11.2 Endpoint 2 — Consulta del estado de la última ejecución

`GET /reporting/pipeline-runs/latest`

- Devuelve el estado y metadata de la última ejecución del pipeline.
- Sirve como chequeo de salud para la operación y el dashboard de operación.

Esta ruta llama a la función `get_latest_pipeline_run()` dentro del módulo de pipeline, que consulta `reporting.pipeline_runs` ordenado por `started_at` desc.

### 11.3 Endpoint 3 — Disparo manual del pipeline

`POST /reporting/pipeline-runs`

- Acepta una ventana `week_start` opcional.
- Si no se incluye, usa la semana más reciente.
- Ejecuta el flow de Prefect `weekly_office_program_performance_flow` en modo manual.

Se trata de una operación administrativa para re-ejecutar una ventana o corregir una semana con eventos tardíos.

### 11.4 Separación de responsabilidades

La lógica ETL no vive en `services/`. La capa de API solo orquesta la carga y devuelve resultados. La lógica real del pipeline se mantiene en:

- `data/pipelines/business_performance_pipeline.py`
- `data/pipelines/tasks/*.py` o un módulo equivalente, según la estructura final

Esto respeta la separación entre aplicación y pipeline de datos.

## 12. Reglas de negocio y validaciones

- Nunca mezclar monedas en una misma fila agregada.
- `week_start` debe ser un lunes ISO en UTC.
- La ventana `week_start` se debe validar antes de ejecutar la carga.
- Si se dispara un pipeline para una semana con datos incompletos, se registra el estado `failed` y se deja el `error_message` en `reporting.pipeline_runs`.
- El pipeline solo lee `telemetry_events`; nunca escribe a `telemetry_events`.
- El pipeline no modifica `services/telemetry/analysis.py` ni `GET /telemetry/report`.

## 13. Criterio de aceptación del diseño

Este diseño cumple la necesidad de negocio de Nexova porque:

- responde a la pregunta de Laura y Elena en el lenguaje del negocio,
- produce exactamente los KPI de costo, entrega, escasez y variación,
- usa la telemetría ya disponible sin ampliarla fuera del contexto permitido,
- guarda idempotencia y trazabilidad en tablas separadas de reporting,
- no altera el reporte técnico ni la fuente original de telemetría,
- deja listos los endpoints del negocio para consumir el dashboard semanal.

## 14. Resumen ejecutivo

El pipeline nuevo convertirá los eventos de negocio ya registrados en `telemetry_events` en un agregado semanal, por oficina y por programa, listo para ser leído por liderazgo sin intervención manual. La salida se materializa en `reporting.weekly_office_program_performance`, se registra en `reporting.pipeline_runs` para auditoría y se expone mediante un módulo nuevo `services/reporting/` con tres endpoints: KPI, estado y disparo manual.

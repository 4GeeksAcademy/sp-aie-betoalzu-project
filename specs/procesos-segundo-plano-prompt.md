# Tarea: proceso nocturno independiente para telemetría

Implementa en este monorepo el ticket **DEV-53 — Script nocturno de telemetría**. Antes de cambiar código, inspecciona la persistencia y los modelos actuales de `telemetry_events`, el pipeline de telemetría existente y las convenciones de configuración, pruebas y logging. Adapta la solución a las implementaciones reales del repositorio; no inventes nombres de tablas, columnas, comandos o rutas si ya existe una convención equivalente.

## Objetivo

Crear un proceso de línea de comandos independiente de FastAPI que, para una fecha objetivo, exporte un respaldo CSV de telemetría si todavía no existe, ejecute el pipeline de datos como subproceso y registre en base de datos el estado y el resultado de la ejecución.

El script debe poder ejecutarse con:

```bash
python scripts/nightly_export.py
```

No inicies el proceso desde FastAPI, sus endpoints, hilos, tareas de background ni hooks de lifespan. La API y el trabajo nocturno deben poder ejecutarse de forma independiente.

## Inspección previa

- Identifica el motor, las sesiones, la configuración de base de datos y las convenciones de modelos/migraciones existentes; reutilízalos.
- Localiza el entry point CLI real del pipeline del Hito 6 y verifica cómo debe invocarse como subproceso. No conectes el pipeline al CSV: el pipeline lee `telemetry_events` de la base de datos.
- Comprueba el esquema y el campo temporal de `telemetry_events` para definir correctamente el filtro UTC de la exportación.
- Evita cambios no relacionados y conserva las responsabilidades existentes de `pipeline_runs`.

## Modelo y servicio de estado

Implementa un servicio en `services/` para administrar `job_runs`, y crea o documenta el esquema necesario siguiendo las convenciones del proyecto. La tabla debe incluir como mínimo:

- `id`, `job_name`, `target_date` (tipo fecha), `status`, `started_at`, `finished_at`, `error_message` y `created_at`.
- Un índice sobre `(job_name, target_date)` para idempotencia.
- Los estados permitidos: `pending`, `processing`, `completed` y `failed`.

El servicio debe ofrecer operaciones para crear, consultar y actualizar ejecuciones, además de `has_processing_lock` y `has_completed_for_date`. `job_runs` registra la orquestación nocturna; `pipeline_runs` sigue registrando exclusivamente las fases internas del ETL.

## Fechas, idempotencia y concurrencia

- Si existe `TARGET_DATE` con formato `YYYY-MM-DD`, úsala; si no, usa el día calendario anterior en UTC: `datetime.now(timezone.utc).date() - timedelta(days=1)`.
- La idempotencia es por `(job_name='nightly_export', target_date)`. Si ya hay una ejecución completada para esa fecha, no reexportes ni vuelvas a lanzar el pipeline. Registra la omisión en el log sin inventar estados fuera de los cuatro permitidos.
- El estado `processing` de `job_runs` es el único lock. Si ya hay un `nightly_export` en `processing`, la nueva instancia debe abortar silenciosamente y no ejecutar trabajo.
- La comprobación y adquisición del lock deben ser atómicas para dos procesos concurrentes, usando las capacidades transaccionales de la base de datos y el propio registro `processing`. Una secuencia separada de “consultar y luego insertar/actualizar” que permita una carrera no satisface este requisito. No añadas una tabla, columna, archivo de lock, Redis, advisory lock ni otro mecanismo de bloqueo.
- Cada invocación debe quedar trazable en `job_runs`, también cuando termina como no-op por duplicado o encuentra el lock ocupado. Mantén el flujo de estados permitido y documenta claramente cómo se representa una omisión sin confundirla con una ejecución del pipeline.

## Exportación CSV y ejecución del pipeline

- Exporta los registros de `telemetry_events` correspondientes a `target_date` en UTC a `data/raw/telemetry_YYYY-MM-DD.csv`.
- Usa un intervalo temporal semiabierto desde el inicio del día objetivo hasta el inicio del día siguiente, ambos en UTC, para evitar ambigüedades en los límites.
- Crea `data/raw/` si hace falta. Si el archivo ya existe, no lo sobrescribas; considera el CSV un respaldo/auditoría, no una entrada del pipeline.
- Haz la exportación de forma determinista: conserva un conjunto de columnas estable y un orden estable de filas cuando el esquema lo permita.
- Después de la exportación (o de confirmar que el CSV existente se conserva), ejecuta el entry point real del pipeline mediante `subprocess`, comprobando el código de salida. Usa el intérprete actual (`sys.executable`) y una ruta de trabajo explícita cuando sea necesario.

## Máquina de estados, errores y logs

- Crea el registro antes de empezar el trabajo con `pending`; al adquirir la ejecución, cambia a `processing` antes de exportar o lanzar el pipeline.
- Al completar todos los pasos, establece `completed` y `finished_at`.
- Ante cualquier excepción del trabajo, guarda `failed`, `finished_at` y el mensaje de excepción en `error_message`; registra el error y propágalo para que la ejecución CLI termine con código distinto de cero.
- Ninguna ruta de error de la ejecución debe dejar el registro en `processing`. Usa manejo de excepciones y cierre/transacciones adecuados para garantizar la transición; si falla la propia escritura del estado final, informa explícitamente del fallo de persistencia en el log.
- Usa logs con timestamp, nombre del job y estado en cada evento relevante. Los eventos normales (inicio, finalización y omisiones) usan `INFO`; los errores usan `ERROR`.
- El trabajo y la persistencia de estados no deben depender de importar ni arrancar la aplicación FastAPI.

## Disparador

Elige un disparador externo al proceso de API. Prefiere crontab del sistema o un contenedor scheduler dedicado; no añadas APScheduler ni un hook de FastAPI. Documenta la expresión cron recomendada, el método elegido y por qué es apropiado. No alteres la crontab del entorno de desarrollo como efecto lateral de la implementación.

## Pruebas

Añade o amplía pruebas focalizadas, usando el framework y las fixtures existentes. Cubre como mínimo:

- Resolución de `TARGET_DATE`, fecha por defecto UTC y rechazo de formatos inválidos.
- Exportación con filtro UTC y conservación de un CSV ya existente.
- Ejecución del subprocess y manejo de su código de salida.
- Transiciones `pending` → `processing` → `completed` y `pending` → `processing` → `failed`, incluido el mensaje de error.
- Omisión por ejecución completada y aborto silencioso por lock ocupado.
- Adquisición concurrente del lock: dos instancias no deben poder ejecutar el trabajo simultáneamente.

Ejecuta las pruebas relevantes y el lint/typecheck disponible para el área modificada. No intentes corregir fallos preexistentes ajenos a esta tarea; identifícalos en el resumen.

## Entrega

Al terminar, resume los archivos modificados, el comando CLI y el entry point real del pipeline utilizado, la expresión cron recomendada, cómo se garantiza la atomicidad/idempotencia, y los comandos/resultados de verificación. Incluye ejemplos breves de logs de éxito, fallo y omisión/bloqueo. No crees un commit salvo que se solicite expresamente.
# Carpeta `scripts`

Esta carpeta contiene **scripts auxiliares** del monorepo: automatizaciones de desarrollo, utilidades de mantenimiento, tareas repetitivas (setup, lint, migraciones, generación de datos, etc.) y tooling interno.

- **Propósito principal**: agrupar herramientas de soporte que no pertenecen a una app/agente/pipeline específico, pero facilitan el trabajo del equipo.
- **Recomendación**: documenta cada script (qué hace, parámetros, requisitos, ejemplos de uso) y procura que sean reproducibles (y seguros) en distintos entornos.

## Exportación nocturna de telemetría

`python scripts/nightly_export.py` crea un respaldo en `data/raw/telemetry_YYYY-MM-DD.csv` para `TARGET_DATE` o, por defecto, el día anterior en UTC. Después ejecuta el entry point real `data/pipelines/pipeline.py` como subproceso con el intérprete actual. El CSV es una auditoría y no una entrada del pipeline.

La ejecución es independiente de FastAPI. El disparador recomendado es crontab del sistema, por ejemplo `15 2 * * * cd /ruta/al/repositorio && /ruta/al/venv/bin/python scripts/nightly_export.py >> /var/log/nexova-nightly-export.log 2>&1`; así el scheduler externo controla la periodicidad y la API no mantiene trabajo persistente. `TARGET_DATE=2026-09-28` permite reprocesar una fecha concreta.

`job_runs` registra cada invocación. La adquisición cambia una fila `pending` a `processing` dentro de una actualización transaccional y el índice único parcial de `processing` impide dos locks para el mismo job y fecha. Las omisiones se guardan como `completed` con `error_message` descriptivo (`already_completed` o `processing_lock_occupied`); `has_completed_for_date` solo considera completadas las filas sin ese mensaje, para no confundir una omisión con una ejecución del pipeline.

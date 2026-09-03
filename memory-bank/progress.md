# Progress — Estado del Proyecto

## Historial completo del proyecto (hitos por rama/commit, cronologico)
Resumen consolidado de todo el trabajo realizado en el monorepo hasta la fecha, incluyendo hitos previos no documentados anteriormente en el memory bank:

1. **Estructura inicial** (`hito4`, `main`): migracion del frontend a `uis/` (website + backoffice separados) y estructura base de backend (`estructura backend`).
2. **Analizador de Incidentes** (`feat/incident_analyzer`): CSV upload, calculo de metricas/resumen y export CSV; ajustes posteriores de backoffice y endpoints.
3. **Suppliers**: seeder inicial (`scripts/seed.py`/`seed_suppliers`), interfaz de proveedores en backoffice y servicios asociados.
4. **Auth** (`feature/auth`, `feat/auth-2`, `feat/auth-password_reset`): registro/login, interfaz login/register, JWT completo, perfil de usuario, flujo de "forgot password".
5. **Gestor de Incidencias Centralizado** (`feat/Centralized_Incident_Manager`): modelo `Incident`, categorias/branches de Nexova, transiciones de estado, resumen agregado (ver `gestor-incidentes-centralizado.md`).
6. **Manejo de errores** (`Feat/manejo_errores`) y **Bateria de pruebas** (`feat/bateria_pruebas`): endurecimiento de manejo de errores en backend/frontend y primeras suites de pruebas automatizadas.
7. **Inventario** (`feat/inventory-backend`, `feat/inventory-interface`): productos, ordenes de entrada/salida, calculo/validacion de stock, interfaz completa en backoffice, seed demo (`scripts/seed_inventory.py`).
8. **Dockerizacion** (`docker done`, `docker fix`): `docker-compose.yml`, `services/Dockerfile`, `uis/Dockerfile` y `uis/start.sh` para levantar backend + interfaces juntos.
9. **Auditoria de duplicacion frontend** (`feat/auditory`): analisis en `AUDIT.md` (antes/despues en `audit/before/`) sobre logica CRUD duplicada (`IncidentsManagerClient` vs `SuppliersManagerClient`) y validacion de formularios en el website; motivo varios refactors posteriores (`fix/backoffice-suppliers-crud-refactor`, `fix/backoffice-incidents-crud-refactor`, `fix/backoffice-consolidar-backend-proxy`, `fix/website-refactor-validation-js`, `fix/backoffice-eliminar-setError-duplicado`).
10. **Optimizaciones puntuales de frontend**: migracion de CSS a Tailwind compilado en el website (`fix/website-migracion-a-tailwind-css-compilado`), preload de imagen LCP del hero (`fix/website-preload-lcp-hero-image`), modo produccion de `start.sh` (`fix/start-sh-modo-produccion`).
11. **Fixes de Suppliers e inventario post-docker** (`fix/Suppliers api`, `fix/pipeline_tracker`, `inventory fix`): correccion de auth SSR sin token, `FileNotFoundError` de TinyDB por falta de volumen Docker, y `updated_at` faltante en el modelo `Supplier` (detalle en memoria de repo `/memories/repo/notes.md`).
12. **Auditoria de serializacion** (`feature/serialization-audit`): revision completa de endpoints en `services/api` clasificados en serializado/parcial/no serializado (`docs/serialization-audit.md`), con hallazgos en `incident_analyzer`, `incidents` (summary y seed sin modelo Pydantic de salida) e `inventory`.
13. **Optimizacion de caching** (`feature/caching-optimisation`): sistema `TTLCache` con tags e invalidacion por escritura en `services/cache.py` (decorador `@cached`, cache global `backend_cache`, TTL 120s en `GET /api/incidents/summary` y otros endpoints costosos); en frontend, `next/dynamic` para componentes pesados (`CandidateTable`, `CandidateDetailClient`, `IncidentsManagerClient`, etc.) y `useMemo` en listas/filtros ordenados (detalle en `CACHING_REPORT.md`).
14. **Diseno de telemetria** (`feat/telemetry-desing`): plan de eventos y schemas JSON (`docs/telemetry/telemetry-plan.md`, `docs/telemetry/event-schemas.json`) definiendo 5 eventos obligatorios de negocio (inventario, login, errores, etc.).
15. **Captura frontend de telemetria** (`feat/telemetry-frontend-capture`, commit `92d77d7`): servicio `uis/backoffice/services/telemetry.ts` con envelope normalizado (`eventId`, `timestamp`, `sessionId`, `userId`, `event_type`, `schemaVersion`, `requestId`, `properties`), cola local, lotes de 20 eventos, flush temporizado, hasta 3 reintentos con backoff y `navigator.sendBeacon` en descarga de pagina; endpoint inicial `POST /telemetry/events` en el backend (sin persistencia) y pruebas unitarias frontend/backend.
16. **Persistencia de telemetria** (rama actual `feat/telemetry-storage`, commit `b670644`, sesion en curso): ver detalle en la seccion "Completado" punto 12 y "Sesion actual" mas abajo.

## Completado
1. Contexto de negocio de Nexova y estructura de monorepo documentados.
2. Backend FastAPI modularizado con routers de usuarios, perfiles, proveedores, inventario, incidencias, analizador y telemetria.
3. Autenticacion JWT completa en el backend: registro, login, usuario actual, cambio/restablecimiento de contrasena y permisos admin.
4. CRUD de proveedores e incidencias, resumen y transiciones de incidencias, seed CSV con validacion e idempotencia.
5. Inventario funcional con productos, ordenes de entrada/salida, calculo de stock, validacion de stock y datos demo mediante `scripts/seed_inventory.py`.
6. Cache TTL global en memoria con invalidacion por tags e integracion en servicios de backend; existe prueba de regresion para evitar resultados obsoletos tras cachear una lista vacia.
7. Backoffice Next.js con paginas de autenticacion, cuenta, inventario, incidencias, analizador, proveedores y Talent Pipeline Tracker; incluye rutas proxy y servicios/tipos frontend.
8. Website estatico y dockerizacion conjunta de backend e interfaces.
9. Plan y schemas JSON de telemetria para inventario completados.
10. Captura frontend de telemetria implementada con envelope normalizado, cola local, lotes de 20, flush temporizado, hasta tres reintentos con backoff y `sendBeacon`.
11. Endpoint backend `POST /telemetry/events` y pruebas unitarias frontend/backend basicas.
12. Persistencia de telemetria en backend (sesion actual, commit `b670644`): tabla `TelemetryEventRecord` (`telemetry_events`) en `services/models.py` via SQLModel, con indice GIN (`ix_telemetry_events_tags_gin`) sobre la columna `tags` (JSON) para consultas analiticas. El endpoint `POST /telemetry/events` ahora valida cada evento del batch contra el modelo Pydantic `TelemetryEvent` (`extra="forbid"`), descarta silenciosamente (`rejected`) los eventos invalidos, filtra `properties` contra una lista blanca `ALLOWED_TAG_KEYS`, deriva `level` (`error` vs `info`) segun `ERROR_EVENT_TYPES`, extrae un `value` numerico best-effort (`value` o `unit_cost`) y hace un `insert` bulk via SQLAlchemy/SQLModel en una sola transaccion. Respuesta ampliada a `{received, stored, rejected}`. Pruebas actualizadas en `tests/test_telemetry_backend.py` (44 lineas, cubre validacion, rechazo y persistencia).

## Parcial o pendiente
1. Telemetría de almacenamiento implementada: tabla SQLModel `telemetry_events`, índices analíticos, validación parcial por evento y bulk insert.
2. La telemetría no esta instrumentada todavia en los flujos de negocio del backoffice; el uso actual queda limitado al servicio y su test.
3. Los cinco eventos obligatorios del plan estan definidos, pero no todos tienen productores implementados ni validacion especifica de `properties` en el endpoint.
4. TinyDB y SQLModel conviven; falta consolidar una fuente de verdad para modelos compartidos y completar el uso de `packages/shared`.
5. No hay runner de workspace en la raiz ni agente/workflow productivo consolidado; `agents/`, `skills/` y `workflows/` son principalmente plantillas y documentacion.
6. Falta ampliar pruebas de API, servicios, integracion y flujos principales de UI; las pruebas visibles cubren telemetria, inventario y usuarios.
7. CORS abierto, secretos/configuracion de desarrollo y cache en memoria requieren endurecimiento para produccion.
8. El README raiz mantiene texto de plantilla y no describe el estado real del monorepo.

## Validacion conocida
- Backend: `pytest` es el runner configurado en `pyproject.toml`; existen suites en `tests/` y dentro de los modulos de usuarios/inventario.
- Frontend: `npm run lint`, `npm run build` y Jest estan disponibles en `uis/backoffice`; la raiz tambien contiene dependencias Jest para pruebas puntuales.
- Validacion de esta actualizacion: las pruebas focalizadas de telemetria e inventario pasan (`2 passed`) y la prueba frontend de telemetria pasa (`1 suite, 1 test`).
- La suite backend completa con `PYTHONPATH=.` termina en `47 passed, 13 failed`; los fallos se concentran en usuarios porque varias pruebas esperan diccionarios subscriptables y los servicios devuelven `UserOut`.
- El lint del backoffice termina con `11 errors, 4 warnings`; destaca `setState` sincronico dentro de un efecto en `lib/auth-context.tsx` y avisos de variables no usadas en `services/api.ts`.
- La raiz no define script npm `lint`; el lint debe ejecutarse desde `uis/backoffice`.
- La rama actual es `feat/telemetry-storage` (ahead de `origin/feat/telemetry-frontend-capture` por 1 commit); el ultimo commit funcional es `b670644` ("feat: persist telemetry batches"), que anade la tabla `TelemetryEventRecord` y la validacion/persistencia del endpoint de telemetria descritas arriba.
- Cambio pendiente de commit al cierre de esta sesion: `.env.example` (staged) actualiza `NEXT_PUBLIC_TELEMETRY_ENDPOINT` de vacio a `http://localhost:8000/telemetry/events` para que el frontend apunte al backend local por defecto.

## Siguiente iteracion recomendada
1. Conectar `track()` a navegacion, autenticacion y operaciones inbound/outbound.
2. Definir almacenamiento y pipeline de ingestia de telemetria con controles de PII, retencion y consulta.
3. Validar schemas por tipo de evento y añadir pruebas de fallos, reintentos y duplicados.
4. Consolidar tipos compartidos y actualizar la documentacion de ejecucion de cada aplicacion.
5. Ejecutar lint, build y suites backend/frontend antes de cualquier release.


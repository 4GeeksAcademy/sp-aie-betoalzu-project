# Progress — Estado del Proyecto

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
- La rama actual es `feat/telemetry-frontend-capture`; el ultimo commit funcional es `92d77d7` (Telemetry phase 1 complete), precedido por ajustes de inventario.
- Hay modificaciones locales no funcionales, incluyendo `.env.example` y varios `__pycache__`; no forman parte de esta actualizacion de memoria.

## Siguiente iteracion recomendada
1. Conectar `track()` a navegacion, autenticacion y operaciones inbound/outbound.
2. Definir almacenamiento y pipeline de ingestia de telemetria con controles de PII, retencion y consulta.
3. Validar schemas por tipo de evento y añadir pruebas de fallos, reintentos y duplicados.
4. Consolidar tipos compartidos y actualizar la documentacion de ejecucion de cada aplicacion.
5. Ejecutar lint, build y suites backend/frontend antes de cualquier release.


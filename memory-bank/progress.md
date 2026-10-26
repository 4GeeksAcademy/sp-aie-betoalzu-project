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
13. Dise1o del pipeline de negocio para el reporte semanal por oficina y programa: documento `data/pipelines/PIPELINE_DESIGN.md` con objetivos del negocio, agregaciones, tabla `reporting.weekly_office_program_performance`, estrategia de idempotencia, logging de ejecucion y mapeo a Prefect y endpoints `services/reporting/`.

14. **Implementacion del pipeline de reporting** (sesion `feat/pipeline-implemented`): `data/pipelines/pipeline.py` implementa el flow Prefect `weekly_office_program_performance_flow` con tareas independientes de registro, extraccion de `telemetry_events`, agregacion semanal, carga idempotente por upsert y exportacion opcional de evaluacion. Se añadieron reintentos para tareas de base de datos, cache de 15 minutos en la transformacion con clave SHA-256, tablas de reporting y auditoria de corridas.
15. **API de reporting**: nuevo router `services/reporting/routes.py` con consulta de KPIs semanales, ultima corrida y disparo manual autenticado; el router queda montado en `server.py`. Prefect 3 se declaro en `pyproject.toml` y `services/requirements.txt`.

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
- La rama actual es `feat/pipeline-implemented`; en esta sesion se crearon los commits `17d5a19` (pipeline) y `80a2cc5` (API de reporting).
- Validacion del pipeline de reporting: `python data/pipelines/pipeline.py` ejecuta el flow CLI; una prueba aislada con cuatro eventos sinteticos produjo `200 EUR`, un kit entregado, un evento de escasez y un evento de variacion, y dos corridas dejaron una sola fila por clave natural. `SECRET_KEY=test-secret python -m pytest tests/test_telemetry_backend.py -q` termina en `2 passed`; las tres rutas de reporting se confirmaron montadas en FastAPI.

## Siguiente iteracion recomendada
1. Conectar `track()` a navegacion, autenticacion y operaciones inbound/outbound.
2. Definir almacenamiento y pipeline de ingestia de telemetria con controles de PII, retencion y consulta.
3. Validar schemas por tipo de evento y añadir pruebas de fallos, reintentos y duplicados.
4. Consolidar tipos compartidos y actualizar la documentacion de ejecucion de cada aplicacion.
5. Ejecutar lint, build y suites backend/frontend antes de cualquier release.

## Avance de pipeline de reporting

- Rama `feat/reporting-pipeline-subflows-dashboard`: el flow semanal ahora separa extracción, transformación, carga y exportación opcional en subflows Prefect con inputs/outputs explícitos.
- Se añadieron tasks aisladas para los cuatro KPIs y `tests/pipelines/test_pipeline.py`; la suite focalizada termina en `4 passed`.
- Se añadió el dashboard `/reporting` del backoffice, conectado a la API semanal y enlazado desde la navegación.
- El CLI del pipeline se validó en SQLite local tras inicializar el esquema SQLModel; el build del backoffice reconoce la nueva ruta.

## Avance RAG Nexova — fase 0

- Se declararon `qdrant-client>=1.16.2` y `fastembed>=0.8.0` en `pyproject.toml` y `services/requirements.txt`, y se sincronizó `uv.lock`.
- `uv sync`, `uv lock --check` y `uv pip check` pasaron. En host y en la imagen Docker se importaron ambos clientes; FastEmbed reporta el modelo `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` con dimensión 384.
- Compose valida, construye el backend e incluye el montaje de solo lectura de los cuatro documentos. Qdrant respondió desde el host. El acceso entre contenedores tuvo timeout incluso desde un contenedor unido directamente a `nexova-network`; queda pendiente repetirlo en un entorno Docker con red entre contenedores habilitada.
- `docs/rag/configuration.md` documenta URL de Qdrant host/Compose, métrica cosine y umbral inicial provisional 0.5. La plantilla `.env.example` aún no refleja estas variables.
- No se encontró endpoint, ID de modelo generativo ni credencial 4Geeks verificables; la integración de generación queda bloqueada hasta obtener endpoint/modelo oficiales. No se guardaron secretos.

## Avance RAG Nexova — fase 1

- Se añadió `data/process/knowledge_base.py`: chunking por secciones y unidades semánticas, embeddings FastEmbed de 384 dimensiones y colección Qdrant `nexova_knowledge` con distancia Cosine.
- `setup()` indexa las cuatro fuentes con payloads completos e IDs deterministas; al reindexar elimina únicamente puntos obsoletos de cada fuente. Dos ejecuciones reales conservaron 17 puntos e IDs.
- Conteos observados: `service-lines` 5, `pricing-model` 3, `hiring-process-sla` 5 y `objection-handling` 4.
- `tests/process/test_knowledge_base.py` y `tests/pipelines/test_pipeline.py`: 7 pruebas aprobadas. Qdrant quedó detenido tras la validación; la colección reside en el volumen persistente de Compose.

## Avance RAG Nexova — configuración del modelo generativo

- El usuario cambió el modelo generativo a `gpt-4o-mini` con `LLM_API_URL=https://api.openai.com/v1`; ambos valores y el contrato OpenAI-compatible se documentaron. La clave está configurada localmente y no se leyó ni se registró.
- El `.env` contiene `EMBED_MODEL=litellm/madrid-spain/openrouter/perplexity/pplx-embed-v1-0.6b` y `EMBED_MODEL_API_KEY`; no se expusieron valores secretos.
- Sigue ausente `EMBED_BASE_URL` y no se conoce la dimensión del modelo remoto. `data/process/knowledge_base.py` aún carga exclusivamente FastEmbed, por lo que falta implementar el adaptador remoto antes de usar este modelo.
- Qdrant se inició con Compose y respondió HTTP 200 desde el host. No se reindexó ni modificó la colección existente; fase 0 sigue pendiente del contrato de embeddings y la dimensión.
- `.env.example` conserva cambios locales del usuario y no se modificó; su plantilla sigue incompleta.

## Avance renombrado `data_project/`

- Se actualizaron los imports Python, las rutas TinyDB/SQLite, los seeders y la salida de evaluación para usar `data_project/`; Compose y Dockerfile montan/copían el paquete bajo `/app/data_project/`.
- Se incluyó `data_project*` en el descubrimiento setuptools. `docker compose config --quiet` pasó y las pruebas de pipeline, indexación e inventario terminaron con `8 passed`.
- Una ejecución más amplia conserva fallos no relacionados: tres tests RAG usan un mock Qdrant con forma distinta a la respuesta esperada (`.points`) y dos tests de usuarios esperan diccionarios en lugar de `UserOut`.

## Fuentes locales del backoffice

- Se reemplazó `next/font/google` por paquetes Fontsource locales para Geist, Geist Mono y Outfit; el build de Next y TypeScript pasan sin descargar fuentes durante el build.
- El backoffice responde en `3001`; el backend y el website mantienen bloqueos independientes de DNS externo y Tailwind, respectivamente.

## Correccion de conectividad RAG en Codespaces

- Se confirmo que la red bridge de Docker no resolvia el proveedor de embeddings, causando reintentos y respuestas 502. Se retiraron los DNS publicos forzados de Compose y se agrego `docker-compose.codespaces.yml` con red de host para el backend y Qdrant en `http://127.0.0.1:6333`.
- El proveedor generativo devolvia 403 `team_model_access_denied` por el prefijo `litellm/`. La variante usa el identificador autorizado del mismo modelo: `madrid-spain/openrouter/deepseek/deepseek-v4-flash`. No se modificaron credenciales ni se reindexo la coleccion.
- Se documento el arranque con ambos archivos Compose. El backend activo usa esta variante y responde HTTP 200 en `/docs`.
- Validacion previa al commit: Compose y `git diff --check` pasan; el endpoint `/knowledge/query`, con autenticacion simulada y proveedores reales, responde HTTP 200 en 5,8 segundos. La prueba completa previa recupero cinco fragmentos de Qdrant.

## Agente de soporte LangGraph — paso 1

- Se añadio el grafo tipado del agente con rutas condicionales para validar preguntas, recuperar contexto, generar respuestas y abstenerse sin contexto.
- Se añadieron checkpoints durables SQLite y trazas estructuradas por ejecucion; las trazas guardan referencias de fuentes/secciones y omiten contenido de chunks y detalles de excepciones.
- Se declararon `langgraph` y `langgraph-checkpoint-sqlite` en `pyproject.toml` y `services/requirements.txt`.
- Pruebas del grafo: `5 passed`; se verificaron las rutas, la separacion `retrieve`/`generate_answer`, la abstencion sin generacion, persistencia tras reabrir SQLite y trazas seguras ante fallos.
- `uv.lock` no se actualizo porque el archivo esta restringido por la politica de exclusion de contenido de la organizacion.

## Agente de soporte LangGraph — paso 2

- Se integro el grafo al lifespan de FastAPI: compila e inicializa el almacen antes de aceptar requests y cierra el checkpointer al apagar.
- Se añadieron `POST /agent/query` y `GET /agent/traces/{run_id}`, ambos autenticados. La pregunta vacia se traza y responde con 422; los fallos inesperados responden con mensaje generico y `run_id`.
- `POST /knowledge/query` se mantuvo sin cambios de contrato.
- Pruebas focalizadas de agente y conocimiento: `15 passed`, incluyendo autenticacion, respuesta, trazas, fallos genericos y lifecycle.

## Agente de soporte LangGraph — paso 3

- Se añadieron tres fixtures de trazas sanitizadas y evaluaciones offline: respuesta con contexto y tarifa del 22%, pregunta vacia con 422 y abstencion por recuperacion vacia.
- La evaluacion de pricing confirma el 22% contra `nexova-pricing-model.es.md`, y verifica la referencia `pricing-model / Headhunting ejecutivo` sin ejecutar Qdrant ni LLM.
- Se documentaron dependencias, `SUPPORT_AGENT_DB_PATH`, persistencia y endpoints; Compose fija la base en `/app/data_project/support-agent.sqlite3`, persistida por el montaje existente de `data_project/`, y Git ignora ese archivo local.
- `docker compose config --quiet` paso. Las pruebas del agente, Prefect y APIs terminaron en `30 passed`.
- La ejecucion de regresion que incluyo `tests/pipelines/test_rag.py` termino en `36 passed, 3 failed`; son los fallos preexistentes documentados: el mock de Qdrant devuelve una lista mientras `rag.retrieve()` espera `.points`. No se modifico ni debilito esa suite.

## Tools del agente de soporte - paso 1

- Se implementaron tools HTTP independientes y tipadas para incidentes e inventario, reutilizando los modelos reales; solo GET, timeout de 4 segundos y sin redirecciones.
- Incidentes usa JWT de servicio desde el entorno; inventario conserva sus consultas publicas existentes. Se distinguen success, not_found y failed sin registrar credenciales ni respuestas crudas.
- Se documento configuracion, filtros soportados y tratamiento de errores. Validacion: 14 pruebas offline aprobadas, Ruff y diff check correctos.
- Revision previa al commit: alcance limitado a tools, sus pruebas, documentacion y este avance autorizado; sin secretos ni cambios en las demas rutas protegidas. La especificacion local no seguida queda fuera del commit.

## Tools del agente de soporte - paso 2

- Se integraron nodos independientes de incidentes e inventario y rutas condicionales segun la pregunta, incluyendo consultas mixtas con RAG sin reemplazar recuperacion ni generacion.
- Las respuestas operativas se construyen exclusivamente con datos confirmados; los fallos y ausencias se indican por dominio. Cada fuente deja resultado y referencias seguras en la secuencia durable de trazas.
- Se conserva la API autenticada, SQLite, el error HTTP de fallos RAG puros y el contrato de knowledge/query. En consultas mixtas los fallos conocidos del RAG no ocultan los resultados operativos confirmados.
- Validacion: 23 pruebas focalizadas de grafo y APIs aprobadas, lint E9/F/I y diff check correctos. El lint completo detecto dos reglas antiguas fuera del cambio (UP017 y SIM117), sin modificarlas.
- Revision previa al commit: solo grafo, routing, pruebas relacionadas, documentacion y avance autorizado; sin secretos ni cambios adicionales en rutas protegidas.

## Tools del agente de soporte - paso 3

- Se agregaron 11 casos versionados de routing offline y evaluaciones de las trazas persistidas tras cerrar el grafo: tickets, documentos, inventario, fuentes combinadas y fallback.
- Se cubrieron filtros reales, identificador externo, SKU, timeout de la tool real con transporte simulado, fallos RAG mixtos y ausencia de datos inventados. Las evaluaciones bloquean HTTP externo y no requieren credenciales.
- Una regresion detecto que AssetResponse asignaba cero cuando faltaba current_stock; la tool ahora rechaza ese contrato incompleto como invalid_response en lugar de confirmar stock no recibido.
- Validacion combinada de agente, APIs, Prefect y RAG: 75 passed, 3 failed. Los tres fallos son los preexistentes de tests/pipelines/test_rag.py: FakeQdrantClient devuelve una lista mientras retrieve espera .points; no se modificaron el RAG ni sus pruebas.
- Lint focalizado E9/F/I y diff check correctos. Revision previa al commit: solo evaluaciones, correccion acoplada del contrato de inventario, documentacion y este avance autorizado; sin secretos ni cambios en otras rutas protegidas.
## Servidor MCP OAuth — paso 1

- Se añadieron los seis tools MCP de incidencias e inventario con esquemas tipados, filtros limitados, backend HTTP allowlisted y scopes `incidents:read`, `incidents:write` e `inventory:read`.
- El servidor usa `mcpauth` para validar tokens JWT con issuer, audiencia y JWKS; publica Protected Resource Metadata, protege inicialización/listado/ejecución y responde 403 ante scopes insuficientes. Las escrituras de inventario se rechazan sin llamar al backend.
- Se añadieron `mcpauth`, `mcp` y `langchain-mcp-adapters` a los manifiestos Python. `uv.lock` no se actualizó porque permanece restringido por la política de exclusión.
- Se documentaron configuración de desarrollo, permisos, endpoints allowlisted, errores, logging y el estado pendiente de Playground en `docs/mcp/README.md`.
- Validación focalizada: 17 pruebas MCP aprobadas, Ruff y `git diff --check` correctos. No se ejecutó MCP Playground; no se configuraron proveedor OAuth, token de prueba ni URL pública reenviada.
## Migración del agente LangGraph a MCP — paso 2

- El grafo ahora consulta `incidents_get` e `inventory_get_products` a través de `langchain-mcp-adapters` sobre Streamable HTTP con `SUPPORT_AGENT_MCP_URL` y un bearer OAuth vigente en `SUPPORT_AGENT_MCP_ACCESS_TOKEN`.
- Se retiraron las llamadas HTTP directas de `services/agent/tools.py`; fallos de conexión, autenticación, autorización y contratos MCP se devuelven como fuente fallida, sin fallback directo. Se conserva el formato de resultados, las trazas y la composición con RAG.
- Validación focalizada: 37 pruebas de herramientas MCP, routing y grafo aprobadas; Ruff y compilación correctos. `tests/api/test_support_agent_router.py` no se pudo recolectar porque el entorno no tiene `bcrypt`; no se modificó esa ruta.

## Memoria operativa del agente de soporte

- Se implementó almacenamiento SQLite separado para recuerdos, propuestas y auditoría; recuperación limitada al área de soporte y cliente, confirmación explícita para escribir, permisos `admin`/`manager`, deduplicación y expiración/consolidación.
- El grafo incorpora recuerdos pertinentes y salida estructurada con propuesta nullable; clasifica primero respuestas a propuestas pendientes. La API devuelve y acepta `conversation_id`; Compose configura el archivo durable independiente.
- Se documentaron los ciclos aprobados/rechazados y las reglas de datos no memorables. Validación: 17 pruebas focalizadas de grafo/memoria aprobadas, Ruff de los archivos nuevos, compilación y `git diff --check` correctos. Las pruebas de API no se recolectaron porque el entorno carece de `prefect`.
- La API autenticada conserva `conversation_id` entre turnos y admite el alcance opcional por identificador de cliente; el lifecycle ejecuta consolidación al inicio y diariamente, con ruta de SQLite propia en Compose. Las pruebas de API siguen sin recolectarse por la dependencia `prefect` ausente; Ruff detectó además un `RUF059` preexistente en `server.py`, fuera de este cambio.
- La documentación describe configuración, permisos, caducidad, consolidación y ciclos reproducibles de aprobación/rechazo, además de los ejemplos que no deben memorizarse.

## Guardrails del agente de soporte — paso 1

- Se añadió un guard de entrada determinista antes de resolver memoria, consultar fuentes o generar respuestas. Rechaza intentos de cambio de instrucciones y uso personal, permite saludos/hora en Tokio con redirección y redirige consultas fuera de dominio.
- Los bloqueos/redirecciones quedan en la traza con identificador, categoría y acción, sin guardar el texto del usuario. Se añadieron pruebas offline para cuatro ataques, tareas personales y small talk.
- Validación: `tests/pipelines/test_support_agent_guardrails.py` (9 passed), `tests/pipelines/test_support_agent_graph.py` (8 passed) y Ruff focalizado aprobado.

## Guardrails del agente de soporte — paso 2

- Se reforzó el system prompt del agente interno: define dominio Nexova, small talk, rechazo personal, jerarquía de instrucciones y tratamiento de usuario/RAG/tools/memoria como datos no confiables serializados en el mensaje user.
- Se valida el esquema exacto de `answer`/`propuesta_memoria`, el contenido sensible y secretos antes de guardar propuestas y antes de devolver la respuesta. Las salidas rechazadas usan fallback y no escriben memoria.
- Validación offline: guardrails, memoria y grafo, `29 passed`. Ruff focalizado pasa; `rag.py` conserva un `F841` preexistente en `retrieve` (ignorado solo para el chequeo de ese archivo). El test de timeout operativo quedó determinista en el paso 3 con un generador estructurado simulado.

## Guardrails del agente de soporte — paso 3

- Se agregó `GET /agent/guardrails/summary`, autenticado con la dependencia existente, con agregados por categoría, guardrail y acción obtenidos de trazas SQLite. No expone texto de usuario, salida, documentos ni secretos.
- Las entradas vacías registran la activación estructural en el evento de validación existente. Tests verifican resumen de entrada/salida y acceso anónimo/autenticado al endpoint mediante una app FastAPI mínima.
- Validación offline del agente: `52 passed`. Ruff pasa en los archivos modificados, ignorando solo reglas preexistentes (`B008` en rutas y `F841` en `rag.py`). La suite API completa no se pudo recolectar porque este entorno no tiene Prefect.

## Recepción RFP — tarea 1: grafo de análisis

- Se creó `data_project/pipelines/rfp_intake/` con conversión previa a Markdown mediante MarkItDown, clasificación estructurada, extracción con evidencia/preguntas abiertas, activación determinista de departamentos, workers paralelizables y handoff versionado `1.0`.
- Los workers reciben únicamente metadatos compartidos y su extracto; el grafo no incorpora propuestas ni datos ausentes. Se registran métricas de legibilidad como conteos/unidades con sus limitaciones.
- Se añadieron pruebas offline de RFP formal/informal, pitch rechazado, orden conversión-clasificación y ausencia de invención de volúmenes. Validación: `6 passed`, Ruff y `git diff --check` correctos.
- Los PDFs de aceptación bajo `rfp-requests/nexova/` no están disponibles en este entorno; no se crearon fixtures que los simulen.

## Recepción RFP — tarea 2: persistencia y API

- Se añadieron las tablas SQLModel para tickets, metadatos, secciones departamentales y handoff; FastAPI las registra y recupera ejecuciones interrumpidas.
- La API autenticada valida tipo, firma y tamaño del PDF, lo persiste con nombre UUID y permisos `0600`, y ofrece carga asíncrona, listado, consulta y reintento del mismo ticket.
- Metadatos, secciones, handoff y cambio a `analisis_completo` se confirman juntos. Los tickets quedan aislados por usuario; la clasificación negativa persiste como `descartado` y los errores técnicos quedan visibles sin exponer contenido del archivo.
- Se documentó el contrato de handoff v1. Validación combinada API/pipeline: `11 passed`; Ruff, compilación, OpenAPI y `git diff --check` correctos.

## Generación de respuestas RFP — Parte 2, paso 1

- Se añadió generación identificable por departamento desde el handoff, sin releer el PDF ni exponer a un generador extractos de otros departamentos. Las secciones se procesan en paralelo; legibilidad, pertinencia y cumplimiento se evalúan concurrentemente.
- El ciclo cuenta hasta tres evaluaciones válidas por sección. Los errores técnicos no consumen intentos; las secciones aprobadas no se repiten y los borradores agotados conservan evaluación estructurada, estado de revisión y digest del contenido evaluado.
- Se documentaron métrica/umbral de legibilidad, reglas evaluadas, feedback y esquema de handoff 2.0. Pruebas offline de respuesta y regresión de recepción: `15 passed`; Ruff y `git diff --check` correctos.

## Generación de respuestas RFP — Parte 2, paso 2

- Se añadió `POST /rfp-intake/tickets/{ticket_id}/generate` al router autenticado existente. Carga y contrasta handoff, metadatos y secciones de Parte 1; cada evaluación válida persiste borrador y resultado juntos, y el cierre actualiza secciones, ticket y handoff 2.0 en una transacción.
- Se exponen estados de generación/evaluación/revisión, se rechazan ejecuciones duplicadas y se conservan resultados parciales para reanudar. Errores técnicos mantienen el ticket recuperable y no descartan el RFP; la recuperación de ejecuciones interrumpidas verifica la marca temporal para no permitir que una tarea antigua sobrescriba un reintento.
- Se documentó el endpoint y su persistencia. Pruebas API y pipeline RFP: `23 passed`; Ruff y `git diff --check` correctos.

## Generación de respuestas RFP — integración del grafo dedicado

- El fan-out por departamento ahora es parte del grafo LangGraph de RFP mediante `Send`, seguido por el ensamblado del handoff; se mantiene la evaluación paralela por sección. Se reforzó la prueba offline para comprobar ejecución concurrente de generadores sin LLM.
- Se actualizó la documentación de Parte 2. Validación final focalizada de API, generación e intake: `23 passed`; Ruff y `git diff --check` correctos.

## Aprobación y cierre de RFP — decisiones pendientes

- El usuario autorizó a cualquier usuario con rol global `admin` a aprobar todas las secciones activas. Aunque el backend no mantiene una matriz por departamento, esta autorización explícita define el alcance solicitado para los aprobadores.
- El formato/estructura del documento final sigue pendiente. El arbitraje debe permanecer inhabilitado mientras no existan triggers estructurados y una regla/arbitro de negocio autorizados.
- La Parte 3 no está implementada; no habilitar su flujo ni sintetizar/marcar terminado hasta que se defina el formato final y la implementación mantenga transiciones de estado coherentes. El adjunto de requisitos es una instantánea de solo lectura y permanece sin cambios.

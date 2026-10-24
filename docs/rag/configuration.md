# Docker en Codespaces

Si el backend no puede resolver el dominio del proveedor de embeddings desde
la red bridge de Docker, pero el workspace si tiene conectividad, utilizar
la configuracion opcional de red de host:

```bash
docker compose -f docker-compose.yml -f docker-compose.codespaces.yml up -d backend qdrant
```

Esta variante esta destinada a Codespaces/Linux: el backend usa la red del
host y accede a Qdrant mediante su puerto publicado en `127.0.0.1:6333`.
El puerto 8000 debe estar libre; detener antes cualquier backend iniciado
por separado con `docker compose run --service-ports`.
No requiere cambiar claves, modelos ni reindexar la coleccion.

La variante usa el identificador autorizado del modelo generativo actual,
`madrid-spain/openrouter/deepseek/deepseek-v4-flash`, sin el prefijo de cliente
`litellm/`. En llamadas HTTP directas ese prefijo provoca un rechazo 403
`team_model_access_denied`. Si se elige otro modelo, actualizar este valor
con el identificador exacto autorizado por el proveedor.

# Configuración del RAG Nexova

## Dependencias y ejecución

`qdrant-client` y `requests` gestionan la conexión a Qdrant y al proveedor de embeddings vía HTTP. Ambos están declarados en `pyproject.toml` y en `services/requirements.txt`. No se requiere FastEmbed ni ONNX Runtime.

El embedding se realiza mediante llamada HTTP a un endpoint compatible con la API de OpenAI (`/v1/embeddings`), configurado vía `EMBED_BASE_URL` y `EMBED_MODEL`.

## Variables

| Variable | Ejemplo no secreto | Uso |
| --- | --- | --- |
| `EMBED_MODEL` | `madrid-spain/openrouter/perplexity/pplx-embed-v1-0.6b` | ID del modelo remoto de embeddings, enviado en el campo `model` de la request HTTP al endpoint de embeddings. |
| `EMBED_BASE_URL` | `https://litellm.4geeks.ai` | URL base del servicio LiteLLM que sirve el modelo de embeddings (debe terminar en `/v1` o se completa automáticamente). |
| `EMBED_MODEL_API_KEY` | (secreto local, no guardar en Git) | Credencial para el endpoint de embeddings (`Authorization: Bearer <key>`). |
| `EMBEDDING_DIMENSION` | `1024` | Dimensión del vector que devuelve el modelo. Se determina experimentalmente con una llamada real y se usa al crear la colección Qdrant. Si no se define, la colección se crea con la dimensión dinámica del primer embedding. |
| `QDRANT_URL` | `http://localhost:6333` | URL para procesos ejecutados desde el host. |
| `QDRANT_COLLECTION` | `nexova_knowledge` | Colección fija definida por el contrato Nexova. |
| `QDRANT_DISTANCE` | `Cosine` | Métrica de similitud compatible con el modelo elegido. |
| `RAG_MIN_SCORE` | `0.5` | Umbral inicial provisional; debe calibrarse en evaluación. |
| `LLM_API_URL` | `https://api.openai.com/v1` | URL base de la API de generación indicada. |
| `LLM_MODEL` | `gpt-4o-mini` | Modelo generativo elegido; distinto de `EMBED_MODEL`. |
| `LLM_API_KEY` | (secreto local, no guardar en Git) | Credencial del proveedor de generación. |

Definir en el `.env` local las variables de esta tabla que necesite cada proceso. `.env.example` todavía no refleja la configuración RAG completa; usar los nombres de esta tabla y no guardar credenciales en la plantilla, logs, pruebas ni respuestas.

## Red y corpus

- Desde el host, Qdrant se publica en `http://localhost:6333` por `docker-compose.yml`; un indexador ejecutado localmente usa esa URL.
- El backend en Compose resuelve el servicio por `http://qdrant:6333` en la red `nexova-network`. Compose fija esta URL para el contenedor aunque `.env` contenga la URL del host.
- Compose monta `docs/company-knowledge-base/` en `/app/docs/company-knowledge-base/` como solo lectura. El backend puede acceder al corpus sin copiar una segunda versión; procesos locales lo leen desde la ruta del repositorio.
- La colección conserva el nombre `nexova_knowledge`. El volumen `qdrant-storage` persiste sus datos.

## Estado de la integración generativa

`gpt-4o-mini` configurado en `LLM_API_URL=https://api.openai.com/v1`. La API compatible con OpenAI usa el contrato de chat completions. La integración está implementada en `data/pipelines/rag.py` usando `requests.post` contra `/v1/chat/completions`. La credencial se configura localmente y nunca se incorpora al repositorio ni a los logs.

## Estado de embeddings remotos

El ID configurado es `madrid-spain/openrouter/perplexity/pplx-embed-v1-0.6b` con `EMBED_MODEL_API_KEY` definida localmente. La implementación en `data/process/knowledge_base.py` usa `requests.post` contra `EMBED_BASE_URL/v1/embeddings` siguiendo el contrato OpenAI. La dimensión se determina dinámicamente desde la primera respuesta del endpoint. FastEmbed ha sido eliminado tanto de dependencias como de la implementación.

## Validación de conectividad

`docker compose up -d qdrant` publica Qdrant en el host y en la red de Compose. En esta sesión, Qdrant respondió HTTP 200 en `http://localhost:6333/` después de iniciar el servicio. Para detenerlo, usar `docker compose stop qdrant`.

## Agente de soporte LangGraph

El backend declara `langgraph` y `langgraph-checkpoint-sqlite` en `pyproject.toml` y `services/requirements.txt`. Al iniciar FastAPI, el grafo se compila y se conecta al almacén SQLite antes de aceptar consultas.

`SUPPORT_AGENT_DB_PATH` configura el archivo de checkpoints y trazas. Por defecto es `data_project/support-agent.sqlite3`; Compose lo fija en `/app/data_project/support-agent.sqlite3` y monta `./data_project/` de forma persistente en esa ruta. Mantener el archivo en almacenamiento durable y con acceso restringido: los checkpoints conservan la pregunta, el contexto recuperado y la respuesta, mientras que las trazas exponen referencias de fuente y sección.

La memoria operativa aprobada usa una base SQLite independiente, nunca el checkpoint ni Qdrant. `SUPPORT_AGENT_MEMORY_DB_PATH` la configura; por defecto es `data_project/support-agent-memory.sqlite3` y Compose la mantiene en el mismo volumen durable. El agente solo habilita recuerdos de soporte: procedimientos de escalación, preferencias de empresas cliente e incidentes repetibles. Las propuestas se resuelven dentro de la conversación usando el `conversation_id` UUID devuelto por `POST /agent/query`; se puede enviar además un `customer_id` opaco para limitar propuestas y recuperación a esa empresa. Los recuerdos generales y los de ese cliente pueden recuperarse, nunca los de otra empresa.

Todos los usuarios autenticados pueden consultar recuerdos del alcance solicitado; únicamente los roles `admin` y `manager` pueden proponer, aprobar, rechazar o editar. Las propuestas caducan a los 7 días, los recuerdos tras 180 días sin uso y la auditoría se retiene durante 365 días. La consolidación se ejecuta al iniciar el servicio y luego diariamente; los mensajes originales no se guardan en la auditoría, solo una referencia SHA-256. Los recuerdos sin referencia documental verificable se marcan como pendientes de verificación y no prevalecen sobre fuentes operativas vigentes.

`POST /agent/query` y `GET /agent/traces/{run_id}` requieren autenticación. La respuesta de consulta contiene `answer` y `run_id`; la traza se consulta por separado y no devuelve el estado completo del checkpoint. `POST /knowledge/query` sigue disponible con su contrato existente.

### Tools de consulta operativa

Las tools de incidentes e inventario usan exclusivamente `GET`, con timeout
explícito de 4 segundos y sin seguir redirecciones. Reutilizan `IncidentOut`
y `AssetResponse`; no mantienen una copia de los datos del servicio.

- `SUPPORT_AGENT_BACKEND_URL`: URL base del backend (por defecto,
  `http://127.0.0.1:8000`, también válido dentro del contenedor del backend).
- `SUPPORT_AGENT_SERVICE_TOKEN`: JWT de servicio válido para consultar
  `/api/incidents`, enviado como Bearer. Configurarlo en el entorno del
  proceso; no incluirlo en prompts, repositorio ni trazas. Su ausencia produce
  `failed / not_configured`; no se realiza una consulta anónima alternativa.
- `/inventory/products` y `/inventory/products/{id}` no requieren
  autenticación en el contrato actual; la tool no envía credenciales allí.

Incidentes acepta ID interno, `ticket_id` externo y filtros reales de estado,
categoría, sede y origen. Como la API no filtra `ticket_id`, la tool lo compara
exactamente sobre la lista obtenida. Inventario acepta ID interno o búsqueda
local por nombre/SKU sobre los productos obtenidos. Un listado vacío o un
detalle con 404 produce `not_found`; timeout, contrato inválido y fallos HTTP
producen `failed` con código seguro, nunca datos operativos supuestos.

### Enrutamiento y trazas de las fuentes

El nodo de entrada decide las fuentes a partir de identificadores, vocabulario
operativo y términos documentales en la pregunta, sin necesitar un LLM para
enrutar. Un estado de ticket va a `consult_incidents`; una consulta de stock,
a `consult_inventory`; las preguntas documentales conservan la ruta RAG
`retrieve_context -> generate_response | answer_without_context`. Las preguntas
mixtas consultan incidentes, inventario y RAG, en ese orden, únicamente cuando
se seleccionan esas fuentes. La decisión queda en la salida `sources` de
`receive_question`.

`compose_response` presenta los campos operativos confirmados de forma
determinista, separados de la respuesta documental. Los errores y ausencias
se expresan explícitamente, sin entregar datos ficticios al generador. En una
consulta mixta, un fallo conocido del RAG conserva las fuentes operativas
confirmadas e indica la indisponibilidad documental; las consultas únicamente
RAG conservan el error HTTP controlado existente ante fallos de infraestructura.

Los eventos de cada nodo de fuente incluyen `source` (`incidents`, `inventory`
o `rag`) y `outcome` (`success`, `not_found`, `failed`) al terminar. La secuencia
persistida permite reconstruir el orden. Las trazas operativas guardan solo
referencias ID/ticket/SKU y códigos de error seguros, no registros completos,
credenciales ni respuestas operativas. Los checkpoints conservan los resultados
tipados serializados bajo los mismos controles de acceso existentes.

### Evaluaciones offline

```bash
python -m pytest tests/pipelines/test_support_agent.py tests/pipelines/test_support_agent_graph.py tests/pipelines/test_support_agent_tools.py tests/pipelines/test_support_agent_routing.py -q
```

Las evaluaciones de routing usan preguntas versionadas y dobles de prueba,
cierran el grafo y evalúan la traza SQLite persistida. Bloquean HTTP externo y
no necesitan tokens, Qdrant ni LLM. Cubren tickets, documentos, productos,
combinaciones de fuentes, ausencias, timeout y fallos de generación/recuperación.
Los datos operativos ficticios existen únicamente en pruebas. También se
verifica que el stock esté presente en la respuesta del servicio: el valor
por defecto del modelo no constituye una confirmación de existencias.
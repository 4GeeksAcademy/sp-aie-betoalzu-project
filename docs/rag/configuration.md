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
# Configuración inicial del RAG Nexova

## Dependencias y ejecución

`qdrant-client` y `fastembed` están declarados en `pyproject.toml` y en `services/requirements.txt`. El backend Docker los instala desde este último manifiesto. FastEmbed ejecuta los embeddings localmente mediante ONNX Runtime; no requiere una credencial de proveedor.

## Variables

| Variable | Ejemplo no secreto | Uso |
| --- | --- | --- |
| `EMBED_MODEL` | `litellm/madrid-spain/openrouter/perplexity/pplx-embed-v1-0.6b` | ID del modelo remoto de embeddings elegido. La implementación actual todavía usa FastEmbed y debe migrarse antes de indexar con este ID. |
| `EMBED_BASE_URL` | (pendiente de confirmar) | URL base del servicio LiteLLM que sirve el modelo de embeddings. |
| `EMBED_MODEL_API_KEY` | (secreto local, no guardar en Git) | Credencial para el endpoint de embeddings. |
| `EMBEDDING_DIMENSION` | (por verificar con el endpoint) | Dimensión que debe usarse al crear la colección Qdrant para este modelo. |
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

La configuración local indica `gpt-4o-mini` en `https://api.openai.com/v1`. La API compatible con OpenAI usa el contrato de chat completions; la integración del proyecto aún debe implementarse y probarse. La credencial se configura localmente y nunca se incorpora al repositorio ni a los logs.

## Estado de embeddings remotos

El ID configurado es `litellm/madrid-spain/openrouter/perplexity/pplx-embed-v1-0.6b` y `EMBED_MODEL_API_KEY` está definida localmente. Falta `EMBED_BASE_URL`; no se debe asumir que `https://api.openai.com/v1` sirve el modelo LiteLLM de Perplexity. La dimensión se comprobará con una respuesta real del endpoint antes de migrar la colección. La implementación actual de `data/process/knowledge_base.py` carga todos los modelos con FastEmbed, por lo que todavía no puede usar el ID remoto.

## Validación de conectividad

`docker compose up -d qdrant` publica Qdrant en el host y en la red de Compose. En esta sesión, Qdrant respondió HTTP 200 en `http://localhost:6333/` después de iniciar el servicio. Para detenerlo, usar `docker compose stop qdrant`.
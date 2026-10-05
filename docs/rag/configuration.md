# Configuración inicial del RAG Nexova

## Dependencias y ejecución

`qdrant-client` y `fastembed` están declarados en `pyproject.toml` y en `services/requirements.txt`. El backend Docker los instala desde este último manifiesto. FastEmbed ejecuta los embeddings localmente mediante ONNX Runtime; no requiere una credencial de proveedor.

## Variables

| Variable | Ejemplo no secreto | Uso |
| --- | --- | --- |
| `EMBED_MODEL` | `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` | Identificador FastEmbed usado para indexar y consultar. |
| `EMBEDDING_DIMENSION` | `384` | Dimensión esperada del embedding de ese modelo. |
| `QDRANT_URL` | `http://localhost:6333` | URL para procesos ejecutados desde el host. |
| `QDRANT_COLLECTION` | `nexova_knowledge` | Colección fija definida por el contrato Nexova. |
| `QDRANT_DISTANCE` | `Cosine` | Métrica de similitud compatible con el modelo elegido. |
| `RAG_MIN_SCORE` | `0.5` | Umbral inicial provisional; debe calibrarse en evaluación. |
| `LLM_BASE_URL` | (pendiente de confirmar) | Endpoint del proveedor de generación. |
| `LLM_MODEL` | `litellm/madrid-spain/openrouter/deepseek/deepseek-v4-flash` | ID de generación proporcionado para la integración; distinto de `EMBED_MODEL`. |
| `LLM_API_KEY` | (secreto local, no guardar en Git) | Credencial del proveedor de generación. |

Definir en el `.env` local las variables de esta tabla que necesite cada proceso. `.env.example` todavía no refleja la configuración RAG completa; usar los nombres de esta tabla y no guardar credenciales en la plantilla, logs, pruebas ni respuestas.

## Red y corpus

- Desde el host, Qdrant se publica en `http://localhost:6333` por `docker-compose.yml`; un indexador ejecutado localmente usa esa URL.
- El backend en Compose resuelve el servicio por `http://qdrant:6333` en la red `nexova-network`. Compose fija esta URL para el contenedor aunque `.env` contenga la URL del host.
- Compose monta `docs/company-knowledge-base/` en `/app/docs/company-knowledge-base/` como solo lectura. El backend puede acceder al corpus sin copiar una segunda versión; procesos locales lo leen desde la ruta del repositorio.
- La colección conserva el nombre `nexova_knowledge`. El volumen `qdrant-storage` persiste sus datos.

## Estado de la integración generativa

El ID de generación proporcionado es `litellm/madrid-spain/openrouter/deepseek/deepseek-v4-flash`. Aún no se ha confirmado un `LLM_BASE_URL`, una credencial ni el contrato HTTP esperado por el proxy; por tanto, no se afirma que la integración de generación esté operativa. Antes de implementar y validar la llamada de la fase 2, hay que obtener esos datos y comprobar el contrato. La credencial se configura localmente y nunca se incorpora al repositorio.

## Validación de conectividad

`docker compose up -d qdrant` publica Qdrant en el host y en la red de Compose; confirmar disponibilidad con `curl http://localhost:6333/`. Para detenerlo, usar `docker compose stop qdrant`. La conectividad real depende de que el servicio esté iniciado.
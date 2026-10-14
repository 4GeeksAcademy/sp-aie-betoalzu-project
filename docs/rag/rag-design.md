# Diseño del Sistema RAG — Asistente Comercial Nexova

## 1. Arquitectura General

```
┌────────────┐    POST /knowledge/query    ┌──────────────────┐
│  Backoffice │ ──────────────────────────> │  FastAPI Router  │
│  (Next.js)  │                             │  knowledge_api   │
└────────────┘ <────────────────────────── └──────┬───────────┘
       JSON { answer }                            │
                                                  ▼
                                          ┌──────────────────┐
                                          │  data/pipelines/ │
                                          │  rag.py          │
                                          │                  │
                                          │  query() ────────┤
                                          │  retrieve()      │
                                          │  generate_answer()│
                                          └───┬──────┬───────┘
                                              │      │
                                              ▼      ▼
                                   ┌──────────┐  ┌─────────────┐
                                   │  Qdrant   │  │  LLM (GPT)  │
                                   │  (vectores)│  │  (generación)│
                                   └──────────┘  └─────────────┘
```

## 2. Flujo de Retrieval-Augmented Generation

### 2.1 Indexación (`setup` en `knowledge_base.py`)

1. Lee 4 archivos Markdown de `docs/company-knowledge-base/`
2. Divide cada archivo en chunks semánticos usando `chunk_markdown()`:
   - Cada sección `##` se convierte en un chunk independiente
   - Los ítems de listas consecutivas se separan en chunks individuales
   - Reglas y condiciones se preservan intactas
3. Cada chunk se embedding mediante API HTTP (modelo configurado en `EMBED_MODEL` vía `EMBED_BASE_URL/v1/embeddings`, contrato OpenAI)
4. Los vectores se almacenan en Qdrant con metadatos: `company`, `source_document`, `section`, `language`, `chunk_index`, `text`
5. IDs determinísticos (UUID5 basado en SHA-256 del contenido normalizado) para idempotencia
6. Limpieza de puntos huérfanos (stale points) por `source_document`

### 2.2 Recuperación (`retrieve` en `rag.py`)

1. Recibe pregunta del SDR como texto
2. Embediza la pregunta usando el mismo endpoint de embeddings
3. Busqueda por similitud coseno en colección `nexova_knowledge`
4. Retorna hasta `k=5` resultados con `score >= min_score` (default: 0.5)
5. Devuelve solo los payloads (sin scores ni vectores)

### 2.3 Generación (`generate_answer` en `rag.py`)

1. Si el contexto está vacío, abstiene explícitamente sin llamar al LLM
2. Construye un prompt con:
   - **System prompt**: voz de SDR, español, reglas de negocio (no inventar, citar fuentes, no descuentos, promedios vs garantías)
   - **User prompt**: contexto formateado + pregunta del SDR
3. LLM: `gpt-4o-mini` vía `https://api.openai.com/v1/chat/completions`
4. Temperature: 0.3, Max tokens: 1024
5. La respuesta incluye citas de `source_document` y `section`

## 3. Colección en Qdrant

| Propiedad | Valor |
|-----------|-------|
| Nombre | `nexova_knowledge` |
| Distancia | `Cosine` |
| Dimensión | Determinada por el endpoint de embeddings (configurado en `EMBED_MODEL` y `EMBED_BASE_URL`). Se obtiene dinámicamente del primer embedding generado. |

### Payload por punto

| Campo | Tipo | Ejemplo |
|-------|------|---------|
| `company` | str | `Nexova` |
| `source_document` | str | `pricing-model` |
| `section` | str | `Headhunting ejecutivo` |
| `language` | str | `es` |
| `chunk_index` | int | `2` |
| `text` | str | Contenido del chunk |

## 4. Endpoint API

### `POST /knowledge/query`

- **Auth**: Bearer token (cualquier usuario autenticado)
- **Request**: `{ "question": "string (1-2000 chars)" }`
- **Response 200**: `{ "answer": "string" }`
- **Response 422**: Validación Pydantic (pregunta inválida)
- **Response 502**: Error del LLM o Qdrant

### `POST /knowledge/index`

- **Auth**: Bearer token (rol admin)
- **Response 201**: `{ "status": "ok", "indexed": { "source_document": count } }`
- **Propósito**: Re-indexación idempotente de todos los documentos fuente

## 5. Evaluación (Recall@3)

- **Dataset**: `data/eval/test-queries.json` — 10 preguntas con ground truth
- **Métrica**: Proporción de consultas donde al menos un `source_document` esperado aparece en los top-3 resultados
- **Umbral**: 80%
- **Ejecución**: `uv run python data/eval/evaluate_recall.py`

## 6. Configuración de Entorno (`.env`)

| Variable | Propósito | Requerida |
|----------|-----------|-----------|
| `EMBED_MODEL` | Modelo de embeddings | Sí |
| `EMBED_BASE_URL` | URL del endpoint de embeddings | Sí |
| `EMBED_MODEL_API_KEY` | API key de embeddings | Sí |
| `EMBEDDING_DIMENSION` | Dimensión del vector (opcional, se determina dinámicamente) | No |
| `QDRANT_URL` | URL del servidor Qdrant | No (default `http://localhost:6333`) |
| `QDRANT_DISTANCE` | Métrica de similitud | No (default `Cosine`) |
| `RAG_MIN_SCORE` | Umbral mínimo de similitud para retrieval | No (default `0.5`) |
| `LLM_API_URL` | URL base del LLM (OpenAI-compatible) | Sí |
| `LLM_MODEL` | Modelo de generación | Sí (default `gpt-4o-mini`) |
| `LLM_API_KEY` | API key del LLM | Sí |

## 7. System Prompt del Asistente

El system prompt (en `rag.py`) define:

1. **Rol**: Asistente de ventas de Nexova para SDRs y account managers
2. **Idioma**: Siempre español, voz segura y comercial
3. **Fuente**: Solo información de los chunks proporcionados. No inventar.
4. **Citas**: Al final de cada respuesta, citar `source_document` y `section`
5. **Descuentos**: Nunca ofrecer descuento sobre 22%; derivar a Marcos Ibáñez
6. **Promedios vs Garantías**: Tiempos de entrega son promedios; la garantía de reemplazo de 6 meses sí es contractual
7. **Competidores**: Transparencia sobre conflicto de interés
8. **Abstención**: Si no hay contexto relevante, decirlo explícitamente

## 8. Pruebas

| Archivo | Propósito |
|---------|-----------|
| `tests/process/test_knowledge_base.py` | Unit tests del indexador (3 tests) |
| `tests/pipelines/test_rag.py` | Contract tests del pipeline RAG (10 tests) |
| `tests/api/test_knowledge_router.py` | Contract tests del endpoint API (8 tests) |

Todas las pruebas usan dobles (FakeQdrant, mock de HTTP) sin dependencias externas.
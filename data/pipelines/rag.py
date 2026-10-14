"""RAG pipeline for Nexova commercial knowledge base.

Exports:
- retrieve(query, *, k=5, min_score=0.5)  → list[dict]
- generate_answer(question, context)      → str
- query(question)                         → str

Uses embed() from data.process.knowledge_base and the OpenAI-compatible
LLM configured in the environment (LLM_API_URL, LLM_MODEL, LLM_API_KEY).
"""

from __future__ import annotations

import json
import os
from typing import Any

import requests
from dotenv import load_dotenv
from qdrant_client import QdrantClient

from data.process.knowledge_base import COLLECTION_NAME, embed

ROOT_DIR = __import__("pathlib").Path(__file__).resolve().parents[2]
REQUEST_TIMEOUT = (5, 60)
_RAG_MIN_SCORE = 0.5  # default; overridable via env


def _load_llm_config() -> tuple[str, str, str]:
    load_dotenv(ROOT_DIR / ".env", override=False)
    url = (os.getenv("LLM_API_URL") or "").strip().rstrip("/")
    model = (os.getenv("LLM_MODEL") or "").strip()
    key = (os.getenv("LLM_API_KEY") or "").strip()
    if not url or not model or not key:
        raise RuntimeError(
            "LLM_API_URL, LLM_MODEL and LLM_API_KEY are required for generation."
        )
    return url, model, key


def _chat_url(base_url: str) -> str:
    if base_url.endswith("/v1"):
        return f"{base_url}/chat/completions"
    return f"{base_url}/v1/chat/completions"


def _default_qdrant() -> QdrantClient:
    load_dotenv(ROOT_DIR / ".env", override=False)
    return QdrantClient(
        url=os.getenv("QDRANT_URL", "http://localhost:6333"), timeout=10
    )


# ── System prompt for the SDR assistant ──────────────────────────────────

SYSTEM_PROMPT = (
    "Eres un asistente de ventas de Nexova Solutions, una consultora de "
    "recursos humanos y adquisición de talento. Respondes preguntas de "
    "SDRs y account managers durante conversaciones con prospectos.\n\n"
    "Reglas obligatorias:\n"
    "1. Responde siempre en español, con voz segura, comercial y orientada "
    "a cerrar.\n"
    "2. Usa ÚNICAMENTE la información de los chunks proporcionados como "
    "contexto. No inventes datos, porcentajes, plazos ni condiciones.\n"
    "3. Al final de cada respuesta, cita brevemente la fuente entre "
    "paréntesis, indicando el nombre del documento (source_document) y la "
    "sección (section) de donde obtuviste la información.\n"
    "4. NUNCA ofrezcas un descuento sobre la tarifa del 22%. Si el prospecto "
    "pregunta por un descuento, indica que esa decisión requiere aprobación "
    "de una persona autorizada (Marcos Ibáñez).\n"
    "5. Los tiempos de entrega son promedios, NO garantías, a menos que se "
    "trate de la garantía de reemplazo de 6 meses, que sí es contractual.\n"
    "6. Si hablas de competidores, sé transparente: Nexova no toma "
    "búsquedas simultáneas para dos empresas en conflicto directo, pero "
    "puede haber trabajado con competidores en el pasado.\n"
    "7. Si el contexto está vacío o no contiene información relevante, di "
    "explicitamente que la base de conocimiento no contiene información "
    "suficiente para responder. No completees con conocimiento general.\n"
    "8. No menciones puntuaciones, IDs de chunks ni metadatos técnicos en "
    "la respuesta."
)

USER_TEMPLATE = (
    "Contexto:\n{context_text}\n\n"
    "Pregunta del SDR: {question}\n\n"
    "Respuesta:"
)


# ── Public API ───────────────────────────────────────────────────────────

def retrieve(
    query: str,
    *,
    k: int = 5,
    min_score: float | None = None,
    _client: QdrantClient | None = None,
) -> list[dict[str, Any]]:
    """Vector search in the Nexova knowledge base.

    Returns up to *k* payload dicts (without scores) for results whose
    score ≥ *min_score*.  Fewer than *k* results may be returned when
    scores fall below the threshold.
    """
    if not query or not query.strip():
        return []

    threshold = _RAG_MIN_SCORE if min_score is None else min_score
    client = _client or _default_qdrant()

    query_vector = embed(query)

    response = client.query_points(
        collection_name=COLLECTION_NAME,
        query=query_vector,
        limit=k,
        score_threshold=min_score,
        with_payload=True,
    )
    hits = response.points

    return [hit.payload for hit in hits]


def generate_answer(question: str, context: list[dict[str, Any]]) -> str:
    """Generate a grounded answer from the retrieved context chunks.

    When *context* is empty the function returns an explicit abstention
    without calling the LLM.
    """
    if not context:
        return (
            "Lo siento, la base de conocimiento no contiene información "
            "suficiente para responder esa pregunta. Por favor, consulta "
            "con un account manager senior o con Marcos Ibáñez para "
            "obtener una respuesta precisa."
        )

    context_text = "\n\n".join(
        f"[{c.get('source_document', '?')} / {c.get('section', '?')}]\n"
        f"{c.get('text', '')}"
        for c in context
    )

    base_url, model, api_key = _load_llm_config()

    try:
        resp = requests.post(
            _chat_url(base_url),
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": USER_TEMPLATE.format(
                            context_text=context_text, question=question
                        ),
                    },
                ],
                "temperature": 0.3,
                "max_tokens": 1024,
            },
            timeout=REQUEST_TIMEOUT,
        )
    except requests.RequestException as exc:
        raise RuntimeError(
            "LLM provider request failed; check connectivity."
        ) from exc

    if resp.status_code in (401, 403):
        raise RuntimeError(
            f"LLM provider rejected authentication (HTTP {resp.status_code}); "
            "check LLM_API_KEY and provider access."
        )
    if not resp.ok:
        raise RuntimeError(
            f"LLM provider request failed (HTTP {resp.status_code}); "
            "check LLM_API_URL and LLM_MODEL."
        )

    try:
        body = resp.json()
        answer = body["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError, ValueError) as exc:
        raise RuntimeError("LLM provider returned an invalid response body.") from exc

    return answer.strip()


def query(question: str) -> str:
    """Compose retrieval and generation for a single question.

    This is the top-level entry point.  Callers receive only the final
    answer text; no raw chunks, scores or metadata are exposed.
    """
    results = retrieve(question)
    return generate_answer(question, results)
"""FastAPI router for the Nexova RAG knowledge base.

Endpoints:
- POST /knowledge/query   — Ask a question (any authenticated user)
- POST /knowledge/index   — Trigger re-indexing (admin only)
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from data.pipelines.rag import query as rag_query
from data.process.knowledge_base import setup as index_setup
from services.api.users.auth import get_admin_user, get_current_user
from services.api.users.models import UserInDB

knowledge_api = APIRouter(prefix="/knowledge", tags=["knowledge"])


# ── Request / Response models ────────────────────────────────────────────

class QueryRequest(BaseModel):
    question: str = Field(
        ..., min_length=1, max_length=2000,
        description="Pregunta del SDR sobre servicios, pricing o procesos de Nexova.",
    )


class QueryResponse(BaseModel):
    answer: str


class IndexResponse(BaseModel):
    status: str
    indexed: dict


# ── Endpoints ────────────────────────────────────────────────────────────

@knowledge_api.post("/query", response_model=QueryResponse)
def query_knowledge(
    body: QueryRequest,
    _: UserInDB = Depends(get_current_user),
):
    """Ask a question to the Nexova commercial knowledge base."""
    try:
        answer = rag_query(body.question)
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return QueryResponse(answer=answer)


@knowledge_api.post("/index", response_model=IndexResponse, status_code=201)
def index_knowledge(
    _: UserInDB = Depends(get_admin_user),
):
    """Re-index all company knowledge documents into Qdrant.

    This is an idempotent operation: already indexed chunks are preserved,
    new chunks are added, and stale chunks (for a source document that was
    removed or renamed) are cleaned up.
    """
    try:
        result = index_setup()
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return IndexResponse(status="ok", indexed=result)
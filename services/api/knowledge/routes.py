"""FastAPI router for the Nexova RAG knowledge base.

Endpoints:
- POST /knowledge/query   — Ask a question (any authenticated user)
- POST /knowledge/index   — Trigger re-indexing (admin only)
"""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, Field

from data_project.pipelines.rag import KnowledgeNotIndexedError, query as rag_query
from data_project.process.knowledge_base import setup as index_setup
from services.api.rate_limit import require_model_inference_capacity
from services.api.knowledge.jobs import create_job, get_job, run_job
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


class JobResponse(BaseModel):
    job_id: str
    status: Literal["pending", "completed", "failed"]
    answer: str | None = None
    detail: str | None = None


# ── Endpoints ────────────────────────────────────────────────────────────

@knowledge_api.post(
    "/jobs",
    response_model=JobResponse,
    status_code=202,
    dependencies=[Depends(require_model_inference_capacity)],
)
def start_knowledge_job(
    body: QueryRequest,
    background_tasks: BackgroundTasks,
    user: UserInDB = Depends(get_current_user),
):
    job = create_job(user.id)
    background_tasks.add_task(run_job, job.job_id, body.question)
    return JobResponse(job_id=job.job_id, status=job.status)


@knowledge_api.get("/jobs/{job_id}", response_model=JobResponse)
def read_knowledge_job(
    job_id: UUID,
    user: UserInDB = Depends(get_current_user),
):
    job = get_job(str(job_id), user.id)
    return JobResponse(
        job_id=job.job_id, status=job.status, answer=job.answer, detail=job.detail
    )

@knowledge_api.post(
    "/query",
    response_model=QueryResponse,
    dependencies=[Depends(require_model_inference_capacity)],
)
def query_knowledge(
    body: QueryRequest,
    _: UserInDB = Depends(get_current_user),
):
    """Ask a question to the Nexova commercial knowledge base."""
    try:
        answer = rag_query(body.question)
    except KnowledgeNotIndexedError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
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
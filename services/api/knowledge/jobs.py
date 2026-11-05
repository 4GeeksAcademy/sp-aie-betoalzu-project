"""Bounded, process-local knowledge jobs for the single-worker backend."""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, replace
from typing import Literal
from uuid import uuid4

from fastapi import HTTPException

from data_project.pipelines.rag import query as rag_query

logger = logging.getLogger(__name__)
_lock = threading.Lock()
_MAX_JOBS = 64
_MAX_PENDING = 8
_RETENTION_SECONDS = 900


@dataclass
class KnowledgeJob:
    job_id: str
    owner_id: int
    status: Literal["pending", "completed", "failed"] = "pending"
    answer: str | None = None
    detail: str | None = None
    finished_at: float | None = None


_jobs: dict[str, KnowledgeJob] = {}


def _prune() -> None:
    cutoff = time.monotonic() - _RETENTION_SECONDS
    for job_id in [
        key for key, job in _jobs.items()
        if job.finished_at is not None and job.finished_at <= cutoff
    ]:
        del _jobs[job_id]


def create_job(owner_id: int) -> KnowledgeJob:
    with _lock:
        _prune()
        pending = [job for job in _jobs.values() if job.status == "pending"]
        if any(job.owner_id == owner_id for job in pending):
            raise HTTPException(409, "Ya tienes una consulta en curso. Espera a que termine.")
        if len(pending) >= _MAX_PENDING or len(_jobs) >= _MAX_JOBS:
            raise HTTPException(
                429, "El servicio de consultas está ocupado. Inténtalo más tarde.",
                headers={"Retry-After": "30"},
            )
        job = KnowledgeJob(job_id=str(uuid4()), owner_id=owner_id)
        _jobs[job.job_id] = job
        return replace(job)


def get_job(job_id: str, owner_id: int) -> KnowledgeJob:
    with _lock:
        _prune()
        job = _jobs.get(job_id)
        if job is None or job.owner_id != owner_id:
            raise HTTPException(
                404, "Consulta no disponible o caducada. Envía una nueva pregunta."
            )
        return replace(job)


def run_job(job_id: str, question: str) -> None:
    answer = None
    detail = None
    try:
        answer = rag_query(question)
    except RuntimeError as exc:
        detail = str(exc)
        logger.warning("Knowledge job %s failed: %s", job_id, type(exc).__name__)
    except Exception as exc:
        logger.error("Knowledge job %s failed: %s", job_id, type(exc).__name__)
        detail = "Error interno al consultar la base de conocimiento."
    with _lock:
        job = _jobs[job_id]
        job.answer = answer
        job.detail = detail
        job.status = "failed" if detail is not None else "completed"
        job.finished_at = time.monotonic()

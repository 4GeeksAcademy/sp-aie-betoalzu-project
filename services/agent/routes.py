from __future__ import annotations

import hashlib
import hmac
import logging
import os
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from services.agent.support import TraceEvent, get_support_agent
from services.api.rate_limit import require_model_inference_capacity
from services.api.users.auth import get_current_user, get_operations_user
from services.api.users.models import UserInDB

logger = logging.getLogger(__name__)
AUTHENTICATED_USER = Depends(get_current_user)

agent_api = APIRouter(
    prefix="/agent",
    tags=["support-agent"],
    dependencies=[Depends(get_operations_user)],
)


class AgentQueryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question: str = Field(
        max_length=2000,
        description="Pregunta sobre servicios, precios o procesos de Nexova.",
    )
    conversation_id: UUID | None = Field(
        default=None,
        description="Identificador opaco y estable para resolver propuestas pendientes.",
    )
    customer_id: str | None = Field(
        default=None,
        min_length=1,
        max_length=120,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,119}$",
    )


class AgentQueryResponse(BaseModel):
    answer: str
    run_id: str
    conversation_id: str


class AgentTraceEvent(BaseModel):
    run_id: str
    sequence: int
    node_name: str
    status: str
    timestamp: str
    output: dict[str, Any]


class AgentTraceResponse(BaseModel):
    run_id: str
    events: list[AgentTraceEvent]


class GuardrailSummaryResponse(BaseModel):
    total: int
    by_type: dict[str, int]
    by_guardrail: dict[str, dict[str, int]]


@agent_api.post(
    "/query",
    response_model=AgentQueryResponse,
    dependencies=[Depends(require_model_inference_capacity)],
)
def query_agent(
    body: AgentQueryRequest,
    current_user: UserInDB = Depends(get_current_user),
) -> AgentQueryResponse:
    run_id = str(uuid4())
    conversation_id = str(body.conversation_id or uuid4())
    try:
        result = get_support_agent().invoke(
            body.question,
            run_id=run_id,
            conversation_id=conversation_id,
            customer_id=body.customer_id,
            actor_id=str(current_user.id),
            actor_role=current_user.role.value,
        )
    except Exception as exc:
        logger.error(
            "Support-agent execution failed (run_id=%s, error_type=%s)",
            run_id,
            type(exc).__name__,
        )
        raise HTTPException(
            status_code=500,
            detail={
                "message": "No se pudo completar la consulta. Usa el run_id para investigar.",
                "run_id": run_id,
            },
        ) from exc

    signing_key = os.getenv("SECRET_KEY", "").encode()
    actor_pseudonym = hmac.new(
        signing_key or b"missing-secret-key",
        str(current_user.id).encode(),
        hashlib.sha256,
    ).hexdigest()[:16]
    logger.info(
        "agent_audit",
        extra={
            "audit": {
                "correlation_id": run_id,
                "actor_pseudonym": actor_pseudonym,
                "tenant_pseudonym": None,
                "agent": "support",
                "tool": None,
                "decision": "rejected"
                if result["error"] == "question_required"
                else "completed",
                "reason": result["error"],
                "approval": None,
                "timestamp": datetime.now(UTC).isoformat(),
            }
        },
    )

    if result["error"] == "question_required":
        raise HTTPException(
            status_code=422,
            detail={
                "message": "La pregunta no puede estar vacía.",
                "run_id": run_id,
            },
        )

    return AgentQueryResponse(
        answer=result["answer"],
        run_id=run_id,
        conversation_id=conversation_id,
    )


@agent_api.get("/traces/{run_id}", response_model=AgentTraceResponse)
def read_agent_trace(
    run_id: str,
    current_user: UserInDB = Depends(get_current_user),
) -> AgentTraceResponse:
    events: list[TraceEvent] = get_support_agent().get_trace(
        run_id, actor_id=str(current_user.id)
    )
    if not events:
        raise HTTPException(status_code=404, detail="Trace not found.")
    return AgentTraceResponse(run_id=run_id, events=events)


@agent_api.get("/guardrails/summary", response_model=GuardrailSummaryResponse)
def read_guardrail_summary(
    _: UserInDB = AUTHENTICATED_USER,
) -> GuardrailSummaryResponse:
    return GuardrailSummaryResponse(**get_support_agent().get_guardrail_summary())

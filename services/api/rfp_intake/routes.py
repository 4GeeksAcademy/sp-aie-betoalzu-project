from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import threading
from copy import deepcopy
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, AsyncGenerator, Literal
from uuid import UUID, uuid4

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    HTTPException,
    UploadFile,
    status,
)
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlmodel import Session, select

from data_project.pipelines.rfp_intake.approval import (
    RfpApprovalError,
    authorized_departments,
    detect_structured_conflicts,
    draft_digest,
    validate_approval_handoff,
)
from data_project.pipelines.rfp_intake.graph import RfpIntakeError
from data_project.pipelines.rfp_intake.responses import (
    MAX_GENERATION_ATTEMPTS,
    generate_rfp_responses,
)
from services import database
from services.api.rfp_intake.models import (
    RfpApprovalBranch,
    RfpApprovalDecision,
    RfpArbitrationRecord,
    RfpDepartmentSection,
    RfpFinalDocument,
    RfpHandoff,
    RfpMetadataRecord,
    RfpTicket,
)
from services.api.users.auth import get_current_user
from services.api.users.models import UserInDB
from services.api.rfp_intake.sse import get_sse_manager

logger = logging.getLogger(__name__)
rfp_intake_api = APIRouter(prefix="/rfp-intake", tags=["rfp-intake"])
AUTHENTICATED_USER = Depends(get_current_user)
DATABASE_SESSION = Depends(database.get_db)
PDF_UPLOAD = File(...)

ROOT_DIR = Path(__file__).resolve().parents[3]
RAW_DIR = ROOT_DIR / "data_project" / "raw" / "rfp_intake"
MAX_UPLOAD_BYTES = 20 * 1024 * 1024
STALE_AFTER = timedelta(minutes=20)
PDF_CONTENT_TYPE = "application/pdf"


class TicketSummary(BaseModel):
    ticket_id: str
    rfp_id: str
    status: str
    processing_error: str | None
    retry_count: int
    retry_available: bool
    processing: bool
    created_at: datetime
    updated_at: datetime


class TicketDetail(TicketSummary):
    classification: dict[str, Any] | None = None
    metadata: dict[str, Any] | None = None
    sections: list[dict[str, Any]] = Field(default_factory=list)
    handoff: dict[str, Any] | None = None
    approval_branches: list[dict[str, Any]] = Field(default_factory=list)
    approval_decisions: list[dict[str, Any]] = Field(default_factory=list)
    arbitrations: list[dict[str, Any]] = Field(default_factory=list)
    final_document: dict[str, Any] | None = None
    can_approve: bool = False
    can_generate: bool = False


class ApprovalDecisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: Literal["approve", "reject", "request_changes"]
    draft_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    draft_version: int = Field(ge=1)
    comment: str | None = Field(default=None, max_length=4000)

    @model_validator(mode="after")
    def require_feedback(self) -> ApprovalDecisionRequest:
        if self.action in {"reject", "request_changes"} and not (
            self.comment and self.comment.strip()
        ):
            raise ValueError("Se requiere un comentario para rechazar o pedir cambios.")
        return self


def _owned_ticket(
    session: Session, ticket_id: str, current_user: UserInDB
) -> RfpTicket:
    ticket = session.get(RfpTicket, ticket_id)
    if ticket is None or ticket.created_by != str(current_user.id):
        raise HTTPException(status_code=404, detail="Ticket no encontrado.")
    if _mark_if_stale(ticket):
        session.add(ticket)
        session.commit()
    return ticket


def _visible_ticket(
    session: Session, ticket_id: str, current_user: UserInDB
) -> RfpTicket:
    ticket = session.get(RfpTicket, ticket_id)
    if ticket is None:
        raise HTTPException(status_code=404, detail="Ticket no encontrado.")
    if _mark_if_stale(ticket):
        session.add(ticket)
        session.commit()
    if ticket.created_by == str(current_user.id):
        return ticket
    departments = authorized_departments(current_user)
    if departments:
        handoff = session.get(RfpHandoff, ticket_id)
        workstreams = (
            handoff.payload.get("active_workstreams", [])
            if handoff and isinstance(handoff.payload, dict)
            else []
        )
        if any(
            isinstance(item, dict)
            and item.get("department_id") in departments
            for item in workstreams
        ):
            return ticket
    raise HTTPException(status_code=404, detail="Ticket no encontrado.")


def _mark_if_stale(ticket: RfpTicket) -> bool:
    started_at = ticket.processing_started_at
    if ticket.status not in {
        "analizando",
        "generando_borrador",
        "en-evaluación",
    } or started_at is None:
        return False
    if started_at.tzinfo is None:
        started_at = started_at.replace(tzinfo=UTC)
    if started_at >= datetime.now(UTC) - STALE_AFTER:
        return False
    ticket.processing_error = "La ejecución anterior se interrumpió; puede reintentarse."
    if ticket.status != "analizando":
        ticket.status = "analisis_completo"
    ticket.processing_started_at = None
    ticket.updated_at = datetime.now(UTC)
    return True


def _can_retry(ticket: RfpTicket) -> bool:
    return (
        ticket.status == "analizando"
        and ticket.processing_error is not None
        and ticket.processing_started_at is None
    )


def _summary(ticket: RfpTicket) -> TicketSummary:
    return TicketSummary(
        ticket_id=ticket.ticket_id,
        rfp_id=ticket.rfp_id,
        status=ticket.status,
        processing_error=ticket.processing_error,
        retry_count=ticket.retry_count,
        retry_available=_can_retry(ticket),
        processing=ticket.processing_started_at is not None,
        created_at=ticket.created_at,
        updated_at=ticket.updated_at,
    )


def _detail(
    session: Session, ticket: RfpTicket, current_user: UserInDB
) -> TicketDetail:
    metadata = session.get(RfpMetadataRecord, ticket.ticket_id)
    handoff = session.get(RfpHandoff, ticket.ticket_id)
    sections = session.exec(
        select(RfpDepartmentSection).where(
            RfpDepartmentSection.ticket_id == ticket.ticket_id
        )
    ).all()
    branches = session.exec(
        select(RfpApprovalBranch).where(
            RfpApprovalBranch.ticket_id == ticket.ticket_id
        )
    ).all()
    decisions = session.exec(
        select(RfpApprovalDecision)
        .where(RfpApprovalDecision.ticket_id == ticket.ticket_id)
        .order_by(RfpApprovalDecision.created_at)
    ).all()
    arbitrations = session.exec(
        select(RfpArbitrationRecord)
        .where(RfpArbitrationRecord.ticket_id == ticket.ticket_id)
        .order_by(RfpArbitrationRecord.created_at)
    ).all()
    final_document = session.get(RfpFinalDocument, ticket.ticket_id)
    return TicketDetail(
        **_summary(ticket).model_dump(),
        classification=ticket.classification_result,
        metadata=metadata.model_dump(mode="json") if metadata else None,
        sections=[section.model_dump(mode="json") for section in sections],
        handoff=handoff.payload if handoff else None,
        approval_branches=[branch.model_dump(mode="json") for branch in branches],
        approval_decisions=[
            decision.model_dump(
                mode="json",
                exclude={"draft_snapshot", "evaluation_snapshot", "idempotency_key"},
            )
            for decision in decisions
        ],
        arbitrations=[item.model_dump(mode="json") for item in arbitrations],
        final_document=(
            final_document.model_dump(mode="json") if final_document else None
        ),
        can_approve=bool(authorized_departments(current_user)),
        can_generate=ticket.created_by == str(current_user.id),
    )


def _write_uploaded_pdf(upload: UploadFile, ticket_id: str) -> Path:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    path = RAW_DIR / f"{ticket_id}.pdf"
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    size = 0
    first_chunk = True
    try:
        with os.fdopen(descriptor, "wb") as output:
            while True:
                chunk = upload.file.read(64 * 1024)
                if not chunk:
                    break
                if first_chunk:
                    first_chunk = False
                    if not chunk.startswith(b"%PDF-"):
                        raise HTTPException(
                            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                            detail="El contenido recibido no es un PDF válido.",
                        )
                size += len(chunk)
                if size > MAX_UPLOAD_BYTES:
                    raise HTTPException(
                        status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                        detail=f"El PDF supera el límite de {MAX_UPLOAD_BYTES // (1024 * 1024)} MB.",
                    )
                output.write(chunk)
    except Exception:
        path.unlink(missing_ok=True)
        raise
    if first_chunk:
        path.unlink(missing_ok=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El archivo PDF está vacío.",
        )
    return path


def _record_processing_failure(ticket_id: str, error_type: str) -> None:
    with Session(database.engine) as session:
        ticket = session.get(RfpTicket, ticket_id)
        if ticket is None:
            return
        ticket.processing_error = f"Error técnico de análisis ({error_type})."
        ticket.processing_started_at = None
        ticket.updated_at = datetime.now(UTC)
        session.add(ticket)
        session.commit()


def process_rfp_ticket(ticket_id: str) -> None:
    with Session(database.engine) as session:
        ticket = session.get(RfpTicket, ticket_id)
        if (
            ticket is None
            or ticket.status != "analizando"
            or ticket.processing_started_at is None
        ):
            return
        pdf_path = ticket.raw_pdf_path

    try:
        from data_project.pipelines.rfp_intake import run_rfp_intake

        result = run_rfp_intake(pdf_path, ticket_id)
        with Session(database.engine) as session:
            ticket = session.get(RfpTicket, ticket_id)
            if ticket is None:
                raise RuntimeError("El ticket desapareció durante el análisis.")

            ticket.classification_result = result.get("classification")
            ticket.status = result["status"]
            ticket.processing_error = None
            ticket.processing_started_at = None
            ticket.updated_at = datetime.now(UTC)

            if result["status"] == "analisis_completo":
                metadata = result["metadata"]
                session.add(
                    RfpMetadataRecord(
                        ticket_id=ticket_id,
                        client_name=metadata["client_name"],
                        client_hq=metadata["client_hq"],
                        services_requested=metadata["services_requested"],
                        service_types=metadata["service_types"],
                        scope=metadata["scope"],
                        deadline=metadata["deadline"],
                        budget_range=metadata["budget_range"],
                        currency=metadata["currency"],
                        departments_needed=metadata["departments_needed"],
                        department_extracts=metadata["department_extracts"],
                        explicitly_requests_recruitment=metadata[
                            "explicitly_requests_recruitment"
                        ],
                        open_questions=metadata["open_questions"],
                        field_evidence=metadata["field_evidence"],
                        readability_metrics=metadata["readability_metrics"],
                    )
                )
                for section in result["sections"]:
                    session.add(
                        RfpDepartmentSection(
                            ticket_id=ticket_id,
                            department_id=section["department_id"],
                            key_aspects=[
                                aspect.model_dump()
                                if hasattr(aspect, "model_dump")
                                else aspect
                                for aspect in section["key_aspects"]
                            ],
                        )
                    )
                handoff = result["handoff"]
                session.add(
                    RfpHandoff(
                        ticket_id=ticket_id,
                        schema_version=handoff["schema_version"],
                        payload=handoff,
                    )
                )
            session.add(ticket)
            session.commit()
    except (RfpIntakeError, SQLAlchemyError, KeyError, TypeError, ValueError) as exc:
        logger.error(
            "RFP intake failed (ticket_id=%s, error_type=%s)",
            ticket_id,
            type(exc).__name__,
        )
        _record_processing_failure(ticket_id, type(exc).__name__)


def _load_response_generation_input(
    session: Session, ticket_id: str
) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    handoff = session.get(RfpHandoff, ticket_id)
    metadata = session.get(RfpMetadataRecord, ticket_id)
    sections = session.exec(
        select(RfpDepartmentSection).where(
            RfpDepartmentSection.ticket_id == ticket_id
        )
    ).all()
    if handoff is None or metadata is None or not sections:
        raise RfpIntakeError(
            "No se puede generar la respuesta: faltan datos persistidos de Parte 1."
        )

    payload = handoff.payload
    workstreams = payload.get("active_workstreams") if isinstance(payload, dict) else None
    key_aspects = payload.get("key_aspects") if isinstance(payload, dict) else None
    handoff_metadata = payload.get("metadata") if isinstance(payload, dict) else None
    if not isinstance(workstreams, list) or not isinstance(key_aspects, dict):
        raise RfpIntakeError("El handoff persistido tiene una estructura incompatible.")
    if not isinstance(handoff_metadata, dict):
        raise RfpIntakeError("El handoff persistido no contiene metadatos RFP.")
    department_ids = [
        item.get("department_id") for item in workstreams if isinstance(item, dict)
    ]
    section_by_department = {section.department_id: section for section in sections}
    if (
        not department_ids
        or len(department_ids) != len(workstreams)
        or len(set(department_ids)) != len(department_ids)
        or set(department_ids) != set(section_by_department)
        or set(department_ids) != set(metadata.departments_needed)
    ):
        raise RfpIntakeError(
            "Los departamentos del handoff no coinciden con las secciones persistidas."
        )
    metadata_fields = (
        "client_name",
        "client_hq",
        "services_requested",
        "service_types",
        "scope",
        "deadline",
        "budget_range",
        "currency",
        "departments_needed",
        "open_questions",
    )
    if any(
        handoff_metadata.get(field) != getattr(metadata, field)
        for field in metadata_fields
    ):
        raise RfpIntakeError(
            "Los metadatos del handoff no coinciden con la persistencia de Parte 1."
        )
    existing_sections: dict[str, dict[str, Any]] = {}
    for department_id in department_ids:
        section = section_by_department[department_id]
        if key_aspects.get(department_id) != section.key_aspects:
            raise RfpIntakeError(
                f"Los key_aspects persistidos no coinciden para {department_id}."
            )
        existing_sections[department_id] = {
            "draft_content": section.draft_content,
            "evaluation_results": section.evaluation_results,
        }
    if payload.get("ticket_id") != ticket_id:
        raise RfpIntakeError("El handoff persistido no es válido para este ticket.")
    return payload, existing_sections


def _is_current_generation(ticket: RfpTicket, started_at: datetime) -> bool:
    current_started_at = ticket.processing_started_at
    if current_started_at is None:
        return False
    if current_started_at.tzinfo is None:
        current_started_at = current_started_at.replace(tzinfo=UTC)
    return (
        ticket.status in {"generando_borrador", "en-evaluación"}
        and current_started_at == started_at
    )


def _persist_response_phase(
    ticket_id: str, started_at: datetime, status_value: str
) -> None:
    with Session(database.engine) as session:
        ticket = session.get(RfpTicket, ticket_id)
        if ticket is None or not _is_current_generation(ticket, started_at):
            raise RfpIntakeError("El ticket ya no está en generación de respuesta.")
        ticket.status = status_value
        ticket.updated_at = datetime.now(UTC)
        session.add(ticket)
        session.commit()


def _persist_response_evaluation(
    ticket_id: str,
    started_at: datetime,
    department_id: str,
    draft_content: str,
    evaluation_results: dict[str, Any],
) -> None:
    with Session(database.engine) as session:
        section = session.get(
            RfpDepartmentSection, (ticket_id, department_id)
        )
        ticket = session.get(RfpTicket, ticket_id)
        if (
            section is None
            or ticket is None
            or not _is_current_generation(ticket, started_at)
        ):
            raise RfpIntakeError(
                f"No se puede persistir la evaluación de {department_id}."
            )
        section.draft_content = draft_content
        section.evaluation_results = evaluation_results
        session.add(section)
        session.commit()


def _persist_response_generation(
    ticket_id: str, started_at: datetime, result: dict[str, Any]
) -> bool:
    schedule_revision = False
    resolution_required = False
    with Session(database.engine) as session:
        ticket = session.get(RfpTicket, ticket_id)
        handoff = session.get(RfpHandoff, ticket_id)
        if (
            ticket is None
            or handoff is None
            or not _is_current_generation(ticket, started_at)
        ):
            raise RfpIntakeError("El ticket o handoff desapareció durante la generación.")
        approval_branches = session.exec(
            select(RfpApprovalBranch).where(
                RfpApprovalBranch.ticket_id == ticket_id
            )
        ).all()
        has_approval_workflow = bool(approval_branches)
        branches_by_department = {
            branch.department_id: branch for branch in approval_branches
        }
        for section_result in result["sections"]:
            section = session.get(
                RfpDepartmentSection,
                (ticket_id, section_result["department_id"]),
            )
            if section is None:
                raise RfpIntakeError(
                    "Una sección desapareció durante la generación de respuestas."
                )
            new_draft = section_result["draft_content"]
            new_bundle = section_result["evaluation_results"]
            branch = branches_by_department.get(section_result["department_id"])
            if branch is not None:
                new_digest = draft_digest(new_draft)
                new_version = int(new_bundle["iteration_count"])
                if (
                    branch.draft_sha256 != new_digest
                    or branch.draft_version != new_version
                ):
                    section.approval_status = "pending"
                    section.approver = None
                    section.approved_at = None
                    branch.status = "pending"
                    branch.draft_sha256 = new_digest
                    branch.draft_version = new_version
                    branch.updated_at = datetime.now(UTC)
                    session.add(branch)
            section.draft_content = new_draft
            section.evaluation_results = new_bundle
            session.add(section)

        if has_approval_workflow:
            for section_result in result["sections"]:
                department_id = section_result["department_id"]
                section = session.get(
                    RfpDepartmentSection, (ticket_id, department_id)
                )
                branch = branches_by_department.get(department_id)
                if section is None or branch is None:
                    raise RfpIntakeError(
                        "Una rama de aprobación desapareció durante la revisión."
                    )
                if branch.status in {"revision_requested", "needs_human_review"}:
                    branch.draft_sha256 = draft_digest(section.draft_content or "")
                    branch.draft_version = int(
                        section.evaluation_results["iteration_count"]
                    )
                    branch.status = "pending"
                    branch.updated_at = datetime.now(UTC)
                    section.approval_status = "pending"
                    section.approver = None
                    section.approved_at = None
                    session.add(section)
                    session.add(branch)

        handoff.payload = result["handoff"]
        handoff.schema_version = result["handoff"]["schema_version"]
        handoff.status = result["handoff"]["response_generation"]["status"]
        if has_approval_workflow:
            metadata = session.get(RfpMetadataRecord, ticket_id)
            current_sections = session.exec(
                select(RfpDepartmentSection).where(
                    RfpDepartmentSection.ticket_id == ticket_id
                )
            ).all()
            if metadata is None:
                raise RfpApprovalError(
                    "Faltan metadatos para continuar la aprobación."
                )
            validated_sections = validate_approval_handoff(
                ticket_id, handoff.payload, current_sections
            )
            conflicts = detect_structured_conflicts(
                metadata.model_dump(), validated_sections
            )
            for conflict in conflicts:
                arbitration = _store_arbitration(
                    session, ticket_id, conflict, validated_sections
                )
                for department_id in conflict["departments"]:
                    section = session.get(
                        RfpDepartmentSection, (ticket_id, department_id)
                    )
                    branch = session.get(
                        RfpApprovalBranch, (ticket_id, department_id)
                    )
                    if section is None or branch is None:
                        raise RfpApprovalError(
                            "Falta una sección o rama para el arbitraje."
                        )
                    if branch.status in {"revision_requested", "needs_human_review"}:
                        resolution_required = True
                        continue
                    if _prepare_revision(section, branch, conflict["rule"]):
                        schedule_revision = True
                        _sync_handoff_section(handoff, section)
                    else:
                        arbitration.result = "limit_exhausted"
                        session.add(arbitration)
                        ticket.status = "needs_human_review"
                    session.add(section)
                    session.add(branch)
            if schedule_revision:
                ticket.status = "generando_borrador"
                ticket.processing_started_at = datetime.now(UTC)
            elif resolution_required:
                ticket.status = "needs_human_review"
            elif ticket.status != "needs_human_review":
                ticket.status = "esperando_aprobación"
        else:
            ticket.status = result["status"]
        ticket.processing_error = None
        if not schedule_revision:
            ticket.processing_started_at = None
        ticket.updated_at = datetime.now(UTC)
        session.add(handoff)
        session.add(ticket)
        session.commit()
    return schedule_revision


def _record_response_generation_failure(
    ticket_id: str, started_at: datetime | None, error_type: str
) -> None:
    with Session(database.engine) as session:
        ticket = session.get(RfpTicket, ticket_id)
        if (
            ticket is None
            or started_at is None
            or not _is_current_generation(ticket, started_at)
        ):
            return
        has_approval_workflow = session.exec(
            select(RfpApprovalBranch).where(
                RfpApprovalBranch.ticket_id == ticket_id
            )
        ).first() is not None
        ticket.status = "needs_human_review" if has_approval_workflow else "analisis_completo"
        ticket.processing_error = f"Error técnico al generar respuestas ({error_type})."
        ticket.processing_started_at = None
        ticket.updated_at = datetime.now(UTC)
        session.add(ticket)
        session.commit()


def process_rfp_response_generation(ticket_id: str) -> None:
    run_started_at: datetime | None = None
    try:
        with Session(database.engine) as session:
            ticket = session.get(RfpTicket, ticket_id)
            if (
                ticket is None
                or ticket.status not in {"generando_borrador", "en-evaluación"}
                or ticket.processing_started_at is None
            ):
                return
            run_started_at = ticket.processing_started_at
            if run_started_at.tzinfo is None:
                run_started_at = run_started_at.replace(tzinfo=UTC)
            handoff, existing_sections = _load_response_generation_input(
                session, ticket_id
            )

        phases: dict[str, str] = {}
        phase_lock = threading.Lock()

        def report_phase(phase: str, department_id: str) -> None:
            with phase_lock:
                if phase == "completed":
                    phases.pop(department_id, None)
                else:
                    phases[department_id] = phase
                status_value = (
                    "generando_borrador"
                    if "generating" in phases.values()
                    else "en-evaluación"
                )
                _persist_response_phase(ticket_id, run_started_at, status_value)

        result = generate_rfp_responses(
            ticket_id,
            handoff,
            existing_sections=existing_sections,
            on_phase=report_phase,
            on_evaluated=lambda department, draft, evaluation: (
                _persist_response_evaluation(
                    ticket_id, run_started_at, department, draft, evaluation
                )
            ),
        )
        if _persist_response_generation(ticket_id, run_started_at, result):
            process_rfp_response_generation(ticket_id)
    except (RfpIntakeError, SQLAlchemyError, KeyError, TypeError, ValueError) as exc:
        logger.error(
            "RFP response generation failed (ticket_id=%s, error_type=%s)",
            ticket_id,
            type(exc).__name__,
        )
        _record_response_generation_failure(
            ticket_id, run_started_at, type(exc).__name__
        )


def recover_interrupted_rfp_intake() -> None:
    with Session(database.engine) as session:
        interrupted = session.exec(
            select(RfpTicket).where(
                RfpTicket.status.in_(
                    ["analizando", "generando_borrador", "en-evaluación"]
                ),
                RfpTicket.processing_started_at.is_not(None),
            )
        ).all()
        stale_ticket_found = False
        for ticket in interrupted:
            stale_ticket_found = _mark_if_stale(ticket) or stale_ticket_found
        if stale_ticket_found:
            session.add_all(interrupted)
            session.commit()


@rfp_intake_api.post(
    "/tickets",
    response_model=TicketSummary,
    status_code=status.HTTP_202_ACCEPTED,
)
async def upload_rfp(
    background_tasks: BackgroundTasks,
    file: UploadFile = PDF_UPLOAD,
    current_user: UserInDB = AUTHENTICATED_USER,
    session: Session = DATABASE_SESSION,
) -> TicketSummary:
    if file.content_type != PDF_CONTENT_TYPE or not (file.filename or "").lower().endswith(
        ".pdf"
    ):
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Solo se aceptan archivos PDF.",
        )

    ticket_id = str(uuid4())
    pdf_path = _write_uploaded_pdf(file, ticket_id)
    ticket = RfpTicket(
        ticket_id=ticket_id,
        rfp_id=str(uuid4()),
        raw_pdf_path=str(pdf_path),
        created_by=str(current_user.id),
        processing_started_at=datetime.now(UTC),
    )
    try:
        session.add(ticket)
        session.commit()
        session.refresh(ticket)
    except Exception:
        session.rollback()
        pdf_path.unlink(missing_ok=True)
        raise

    # Publish SSE event for new ticket in analyzing state
    sse_manager = get_sse_manager()
    event_payload = {
        "ticket_id": ticket.ticket_id,
        "rfp_id": ticket.rfp_id,
        "client_name": None,  # Will be updated after analysis
        "client_hq": None,  # Will be updated after analysis
        "services_requested": [],  # Will be updated after analysis
        "status": "analyzing",
        "created_at": ticket.created_at.isoformat() if ticket.created_at else datetime.now(UTC).isoformat(),
    }
    await sse_manager.publish("rfp_ticket_created", event_payload)

    background_tasks.add_task(process_rfp_ticket, ticket_id)
    return _summary(ticket)



@rfp_intake_api.get("/tickets", response_model=list[TicketSummary])
def list_rfp_tickets(
    current_user: UserInDB = AUTHENTICATED_USER,
    session: Session = DATABASE_SESSION,
) -> list[TicketSummary]:
    departments = authorized_departments(current_user)
    tickets = session.exec(
        select(RfpTicket)
        .where(
            (RfpTicket.created_by == str(current_user.id))
            | (RfpTicket.status.in_((
                "en-evaluación",
                "needs_human_review",
                "esperando_aprobación",
                "terminado",
            )))
        )
        .order_by(RfpTicket.created_at.desc())
        .limit(200)
    ).all()
    stale_ticket_found = False
    for ticket in tickets:
        stale_ticket_found = _mark_if_stale(ticket) or stale_ticket_found
    if stale_ticket_found:
        session.add_all(tickets)
        session.commit()
    visible = []
    for ticket in tickets:
        if ticket.created_by == str(current_user.id):
            visible.append(ticket)
            continue
        handoff = session.get(RfpHandoff, ticket.ticket_id)
        workstreams = (
            handoff.payload.get("active_workstreams", [])
            if handoff and isinstance(handoff.payload, dict)
            else []
        )
        if any(
            isinstance(item, dict)
            and item.get("department_id") in departments
            for item in workstreams
        ):
            visible.append(ticket)
    return [_summary(ticket) for ticket in visible]


@rfp_intake_api.get("/stream")
async def rfp_sse_stream(
    current_user: UserInDB = AUTHENTICATED_USER,
) -> StreamingResponse:
    """Stream SSE events for RFP ticket creation.

    Each client subscribes and receives `rfp_ticket_created` events
    when new tickets enter the `analyzing` state.

    Requires JWT authentication. Returns text/event-stream.
    """
    sse_manager = get_sse_manager()
    sub_id, queue = await sse_manager.subscribe()

    async def event_generator() -> AsyncGenerator[str, None]:
        try:
            async for frame in sse_manager.stream(sub_id, queue):
                yield frame
        except Exception as e:
            logger.error(f"SSE stream error for {sub_id}: {e}")

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@rfp_intake_api.get("/tickets/{ticket_id}", response_model=TicketDetail)
def read_rfp_ticket(
    ticket_id: UUID,
    current_user: UserInDB = AUTHENTICATED_USER,
    session: Session = DATABASE_SESSION,
) -> TicketDetail:
    ticket = _visible_ticket(session, str(ticket_id), current_user)
    return _detail(session, ticket, current_user)


@rfp_intake_api.post(
    "/tickets/{ticket_id}/retry",
    response_model=TicketSummary,
    status_code=status.HTTP_202_ACCEPTED,
)
def retry_rfp_ticket(
    ticket_id: UUID,
    background_tasks: BackgroundTasks,
    current_user: UserInDB = AUTHENTICATED_USER,
    session: Session = DATABASE_SESSION,
) -> TicketSummary:
    ticket = _owned_ticket(session, str(ticket_id), current_user)
    if not _can_retry(ticket):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="El ticket no tiene un fallo técnico recuperable.",
        )

    ticket.processing_error = None
    ticket.processing_started_at = datetime.now(UTC)
    ticket.retry_count += 1
    ticket.updated_at = datetime.now(UTC)
    session.add(ticket)
    session.commit()
    session.refresh(ticket)
    background_tasks.add_task(process_rfp_ticket, ticket.ticket_id)
    return _summary(ticket)


@rfp_intake_api.post(
    "/tickets/{ticket_id}/generate",
    response_model=TicketSummary,
    status_code=status.HTTP_202_ACCEPTED,
)
def generate_rfp_response_ticket(
    ticket_id: UUID,
    background_tasks: BackgroundTasks,
    current_user: UserInDB = AUTHENTICATED_USER,
    session: Session = DATABASE_SESSION,
) -> TicketSummary:
    ticket = session.exec(
        select(RfpTicket)
        .where(RfpTicket.ticket_id == str(ticket_id))
        .with_for_update()
    ).first()
    if ticket is None or ticket.created_by != str(current_user.id):
        raise HTTPException(status_code=404, detail="Ticket no encontrado.")
    if ticket.status != "analisis_completo" or ticket.processing_started_at is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="El ticket no está listo para generar respuestas RFP.",
        )

    ticket.status = "generando_borrador"
    ticket.processing_error = None
    ticket.processing_started_at = datetime.now(UTC)
    ticket.updated_at = datetime.now(UTC)
    session.add(ticket)
    session.commit()
    session.refresh(ticket)
    background_tasks.add_task(process_rfp_response_generation, ticket.ticket_id)
    return _summary(ticket)


def _approval_branch(
    session: Session, ticket_id: str, section: dict[str, Any]
) -> RfpApprovalBranch:
    department_id = section["department_id"]
    branch = session.get(RfpApprovalBranch, (ticket_id, department_id))
    if branch is None:
        branch = RfpApprovalBranch(
            ticket_id=ticket_id,
            department_id=department_id,
            thread_id=f"rfp-{ticket_id}:{department_id}",
            draft_sha256=section["draft_sha256"],
            draft_version=section["draft_version"],
        )
        session.add(branch)
    return branch


def _store_arbitration(
    session: Session, ticket_id: str, conflict: dict[str, Any], sections: list[dict[str, Any]]
) -> RfpArbitrationRecord:
    affected = [
        section for section in sections
        if section["department_id"] in conflict["departments"]
    ]
    identity = json.dumps(
        {
            "ticket_id": ticket_id,
            "trigger_id": conflict["trigger_id"],
            "drafts": {
                section["department_id"]: {
                    "digest": section["draft_sha256"],
                    "version": section["draft_version"],
                }
                for section in affected
            },
        },
        sort_keys=True,
    )
    key = hashlib.sha256(identity.encode("utf-8")).hexdigest()
    existing = session.exec(
        select(RfpArbitrationRecord).where(
            RfpArbitrationRecord.idempotency_key == key
        )
    ).first()
    if existing is not None:
        return existing
    arbitration = RfpArbitrationRecord(
        idempotency_key=key,
        ticket_id=ticket_id,
        trigger_id=conflict["trigger_id"],
        departments=conflict["departments"],
        arbitrator=conflict["arbitrator"],
        rule=conflict["rule"],
        evidence=conflict["evidence"],
        section_snapshots={
            section["department_id"]: {
                "draft_content": section["draft_content"],
                "evaluation_results": deepcopy(section["evaluation_results"]),
                "draft_sha256": section["draft_sha256"],
                "draft_version": section["draft_version"],
            }
            for section in affected
        },
        result="request_changes",
    )
    session.add(arbitration)
    return arbitration


def _record_final_document(
    session: Session,
    ticket: RfpTicket,
    metadata: RfpMetadataRecord,
    sections: list[dict[str, Any]],
) -> RfpFinalDocument:
    existing = session.get(RfpFinalDocument, ticket.ticket_id)
    digests = {
        section["department_id"]: section["draft_sha256"] for section in sections
    }
    if existing is not None:
        if existing.section_digests != digests:
            raise RfpApprovalError(
                "El documento final existente no corresponde a las aprobaciones actuales."
            )
        ticket.status = "terminado"
        ticket.processing_error = None
        ticket.processing_started_at = None
        ticket.updated_at = datetime.now(UTC)
        session.add(ticket)
        return existing

    document = RfpFinalDocument(
        ticket_id=ticket.ticket_id,
        document_format="application/json",
        version=1,
        sections=[
            {
                "department_id": section["department_id"],
                "draft_content": section["draft_content"],
                "evaluation_results": section["evaluation_results"],
                "approver": section["approver"],
                "approved_at": section["approved_at"],
            }
            for section in sections
        ],
        currency=metadata.currency,
        section_digests=digests,
    )
    session.add(document)
    ticket.status = "terminado"
    ticket.processing_error = None
    ticket.processing_started_at = None
    ticket.updated_at = datetime.now(UTC)
    session.add(ticket)
    return document


def _prepare_revision(
    section: RfpDepartmentSection, branch: RfpApprovalBranch, feedback: str
) -> bool:
    bundle = deepcopy(section.evaluation_results)
    if not isinstance(bundle, dict):
        raise RfpApprovalError("La sección no conserva una evaluación válida.")
    iteration_count = bundle.get("iteration_count")
    if not isinstance(iteration_count, int):
        raise RfpApprovalError("La evaluación no conserva su contador de iteraciones.")
    if iteration_count >= MAX_GENERATION_ATTEMPTS:
        section.approval_status = "needs_human_review"
        branch.status = "needs_human_review"
        return False

    result = bundle.get("result")
    if not isinstance(result, dict):
        raise RfpApprovalError("La evaluación estructurada no es válida.")
    existing_feedback = str(result.get("feedback_for_generator", "")).strip()
    result["feedback_for_generator"] = (
        f"{existing_feedback} Feedback del revisor: {feedback.strip()}".strip()
    )
    bundle["section_status"] = "needs_revision"
    section.evaluation_results = bundle
    section.approval_status = "changes_requested"
    branch.status = "revision_requested"
    return True


def _sync_handoff_section(
    handoff: RfpHandoff, section: RfpDepartmentSection
) -> None:
    payload = dict(handoff.payload)
    workstreams = payload.get("active_workstreams")
    if not isinstance(workstreams, list):
        raise RfpApprovalError("El handoff no conserva sus departamentos activos.")
    updated = False
    next_workstreams = []
    for workstream in workstreams:
        if (
            isinstance(workstream, dict)
            and workstream.get("department_id") == section.department_id
        ):
            next_workstreams.append(
                {
                    **workstream,
                    "draft_content": section.draft_content,
                    "evaluation_results": section.evaluation_results,
                    "section_status": (
                        section.evaluation_results.get("section_status")
                        if isinstance(section.evaluation_results, dict)
                        else None
                    ),
                    "iteration_count": (
                        section.evaluation_results.get("iteration_count")
                        if isinstance(section.evaluation_results, dict)
                        else None
                    ),
                    "needs_human_review": (
                        isinstance(section.evaluation_results, dict)
                        and section.evaluation_results.get("section_status")
                        == "needs_human_review"
                    ),
                }
            )
            updated = True
        else:
            next_workstreams.append(workstream)
    if not updated:
        raise RfpApprovalError(
            "La sección no aparece en los departamentos activos del handoff."
        )
    payload["active_workstreams"] = next_workstreams
    response_generation = payload.get("response_generation")
    if isinstance(response_generation, dict):
        payload["response_generation"] = {
            **response_generation,
            "status": "needs_human_review",
        }
    handoff.payload = payload
    handoff.status = "needs_human_review"


@rfp_intake_api.post(
    "/tickets/{ticket_id}/approvals/start",
    response_model=TicketSummary,
    status_code=status.HTTP_202_ACCEPTED,
)
def start_rfp_approvals(
    ticket_id: UUID,
    background_tasks: BackgroundTasks,
    current_user: UserInDB = AUTHENTICATED_USER,
    session: Session = DATABASE_SESSION,
) -> TicketSummary:
    locked_ticket = session.exec(
        select(RfpTicket)
        .where(RfpTicket.ticket_id == str(ticket_id))
        .with_for_update()
    ).first()
    if locked_ticket is None:
        raise HTTPException(status_code=404, detail="Ticket no encontrado.")
    ticket = _visible_ticket(session, str(ticket_id), current_user)
    if ticket.status == "terminado":
        return _summary(ticket)
    if ticket.status not in {
        "en-evaluación",
        "needs_human_review",
        "esperando_aprobación",
    } or ticket.processing_started_at is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="El ticket no está listo para iniciar aprobaciones.",
        )

    handoff = session.get(RfpHandoff, ticket.ticket_id)
    metadata = session.get(RfpMetadataRecord, ticket.ticket_id)
    persisted_sections = session.exec(
        select(RfpDepartmentSection).where(
            RfpDepartmentSection.ticket_id == ticket.ticket_id
        )
    ).all()
    try:
        active_sections = validate_approval_handoff(
            ticket.ticket_id,
            handoff.payload if handoff else None,
            persisted_sections,
        )
    except RfpApprovalError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc
    if metadata is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Faltan metadatos RFP persistidos.",
        )

    conflicts = detect_structured_conflicts(metadata.model_dump(), active_sections)
    section_by_department = {
        section.department_id: section for section in persisted_sections
    }
    reprocess: set[str] = set()
    exhausted = False
    for section_data in active_sections:
        branch = _approval_branch(session, ticket.ticket_id, section_data)
        section = section_by_department[section_data["department_id"]]
        if (
            branch.draft_sha256 != section_data["draft_sha256"]
            or branch.draft_version != section_data["draft_version"]
        ):
            branch.draft_sha256 = section_data["draft_sha256"]
            branch.draft_version = section_data["draft_version"]
            branch.status = "pending"
            section.approval_status = "pending"
            section.approver = None
            section.approved_at = None

    for conflict in conflicts:
        arbitration = _store_arbitration(
            session, ticket.ticket_id, conflict, active_sections
        )
        for department_id in conflict["departments"]:
            section = section_by_department[department_id]
            branch = session.get(RfpApprovalBranch, (ticket.ticket_id, department_id))
            if branch is None:
                raise RfpApprovalError("Falta la rama de aprobación.")
            if branch.status in {"revision_requested", "needs_human_review"}:
                exhausted = True
                continue
            should_reprocess = _prepare_revision(
                section,
                branch,
                conflict["rule"],
            )
            if should_reprocess:
                _sync_handoff_section(handoff, section)
                reprocess.add(department_id)
            else:
                arbitration.result = "limit_exhausted"
                session.add(arbitration)
                exhausted = True
            session.add(section)
            session.add(branch)

    if reprocess:
        ticket.status = "generando_borrador"
        ticket.processing_started_at = datetime.now(UTC)
        ticket.processing_error = None
    elif exhausted:
        ticket.status = "needs_human_review"
    else:
        for section_data in active_sections:
            branch = session.get(
                RfpApprovalBranch,
                (ticket.ticket_id, section_data["department_id"]),
            )
            if branch and branch.status != "approved":
                branch.status = "pending"
                section_by_department[section_data["department_id"]].approval_status = (
                    "pending"
                )
                session.add(section_by_department[section_data["department_id"]])
                session.add(branch)
        ticket.status = "esperando_aprobación"
    ticket.updated_at = datetime.now(UTC)
    session.add(ticket)
    session.commit()
    session.refresh(ticket)
    if reprocess:
        background_tasks.add_task(process_rfp_response_generation, ticket.ticket_id)
    return _summary(ticket)


@rfp_intake_api.post(
    "/tickets/{ticket_id}/approvals/{department_id}/resume",
    response_model=TicketSummary,
    status_code=status.HTTP_202_ACCEPTED,
)
def resume_rfp_approval_revision(
    ticket_id: UUID,
    department_id: str,
    background_tasks: BackgroundTasks,
    current_user: UserInDB = AUTHENTICATED_USER,
    session: Session = DATABASE_SESSION,
) -> TicketSummary:
    if department_id not in authorized_departments(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permiso para reanudar esta sección.",
        )
    ticket = session.exec(
        select(RfpTicket)
        .where(RfpTicket.ticket_id == str(ticket_id))
        .with_for_update()
    ).first()
    if ticket is None:
        raise HTTPException(status_code=404, detail="Ticket no encontrado.")
    ticket = _visible_ticket(session, str(ticket_id), current_user)
    if ticket.status != "needs_human_review" or ticket.processing_started_at is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No hay una revisión interrumpida que pueda reanudarse.",
        )
    branch = session.get(RfpApprovalBranch, (str(ticket_id), department_id))
    section = session.get(
        RfpDepartmentSection, (str(ticket_id), department_id)
    )
    handoff = session.get(RfpHandoff, str(ticket_id))
    if branch is None or section is None or handoff is None:
        raise HTTPException(status_code=404, detail="Rama de aprobación no encontrada.")
    bundle = section.evaluation_results
    if (
        branch.status != "revision_requested"
        or not isinstance(bundle, dict)
        or bundle.get("section_status") != "needs_revision"
        or not isinstance(section.draft_content, str)
        or branch.draft_sha256 != draft_digest(section.draft_content)
        or branch.draft_version != bundle.get("iteration_count")
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="La rama no conserva una revisión interrumpida compatible.",
        )
    if branch.draft_version >= MAX_GENERATION_ATTEMPTS:
        branch.status = "needs_human_review"
        section.approval_status = "needs_human_review"
        session.add(branch)
        session.add(section)
        session.commit()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Se agotó el límite de revisiones automáticas.",
        )
    try:
        validate_approval_handoff(
            str(ticket_id),
            handoff.payload,
            session.exec(
                select(RfpDepartmentSection).where(
                    RfpDepartmentSection.ticket_id == str(ticket_id)
                )
            ).all(),
        )
    except RfpApprovalError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc

    ticket.status = "generando_borrador"
    ticket.processing_error = None
    ticket.processing_started_at = datetime.now(UTC)
    ticket.updated_at = datetime.now(UTC)
    session.add(ticket)
    session.commit()
    background_tasks.add_task(process_rfp_response_generation, str(ticket_id))
    return _summary(ticket)


@rfp_intake_api.post("/tickets/{ticket_id}/approvals/{department_id}/decision")
def decide_rfp_approval(
    ticket_id: UUID,
    department_id: str,
    payload: ApprovalDecisionRequest,
    background_tasks: BackgroundTasks,
    current_user: UserInDB = AUTHENTICATED_USER,
    session: Session = DATABASE_SESSION,
) -> dict[str, Any]:
    if department_id not in authorized_departments(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permiso para aprobar esta sección.",
        )
    locked_ticket = session.exec(
        select(RfpTicket)
        .where(RfpTicket.ticket_id == str(ticket_id))
        .with_for_update()
    ).first()
    if locked_ticket is None:
        raise HTTPException(status_code=404, detail="Ticket no encontrado.")
    ticket = _visible_ticket(session, str(ticket_id), current_user)
    section = session.get(
        RfpDepartmentSection, (str(ticket_id), department_id)
    )
    branch = session.get(RfpApprovalBranch, (str(ticket_id), department_id))
    if section is None or branch is None:
        raise HTTPException(status_code=404, detail="Aprobación no encontrada.")
    bundle = section.evaluation_results
    result = bundle.get("result") if isinstance(bundle, dict) else None
    if (
        not isinstance(section.draft_content, str)
        or not isinstance(result, dict)
        or payload.draft_sha256 != branch.draft_sha256
        or payload.draft_sha256 != result.get("draft_sha256")
        or payload.draft_version != branch.draft_version
        or payload.draft_version != bundle.get("iteration_count")
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="La decisión refiere a un borrador obsoleto.",
        )
    key_source = json.dumps(
        {
            "ticket_id": str(ticket_id),
            "department_id": department_id,
            "user_id": current_user.id,
            "action": payload.action,
            "comment": payload.comment,
            "draft_sha256": payload.draft_sha256,
            "draft_version": payload.draft_version,
        },
        sort_keys=True,
    )
    idempotency_key = hashlib.sha256(key_source.encode("utf-8")).hexdigest()
    previous = session.exec(
        select(RfpApprovalDecision).where(
            RfpApprovalDecision.idempotency_key == idempotency_key
        )
    ).first()
    if previous is not None:
        return {
            "decision": previous.model_dump(
                mode="json",
                exclude={"draft_snapshot", "evaluation_snapshot", "idempotency_key"},
            ),
            "ticket": _summary(ticket).model_dump(),
        }
    if ticket.status != "esperando_aprobación":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="El ticket no está esperando una decisión de aprobación.",
        )
    prior_version_decision = session.exec(
        select(RfpApprovalDecision).where(
            RfpApprovalDecision.ticket_id == str(ticket_id),
            RfpApprovalDecision.department_id == department_id,
            RfpApprovalDecision.draft_sha256 == payload.draft_sha256,
            RfpApprovalDecision.draft_version == payload.draft_version,
        )
    ).first()
    if prior_version_decision is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ya existe una decisión para esta versión del borrador.",
        )
    if branch.status != "pending":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="La rama no está pendiente de decisión humana.",
        )

    decision = RfpApprovalDecision(
        idempotency_key=idempotency_key,
        ticket_id=str(ticket_id),
        department_id=department_id,
        approver_user_id=current_user.id,
        approver_email=current_user.email,
        action=payload.action,
        comment=payload.comment.strip() if payload.comment else None,
        draft_sha256=payload.draft_sha256,
        draft_version=payload.draft_version,
        result=payload.action,
        draft_snapshot=section.draft_content,
        evaluation_snapshot=deepcopy(bundle),
    )
    session.add(decision)

    if payload.action == "approve":
        section.approval_status = "approved"
        section.approver = current_user.email
        section.approved_at = datetime.now(UTC)
        branch.status = "approved"
        session.add(section)
        session.add(branch)
        all_branches = session.exec(
            select(RfpApprovalBranch).where(
                RfpApprovalBranch.ticket_id == str(ticket_id)
            )
        ).all()
        if all(item.status == "approved" for item in all_branches):
            all_sections = session.exec(
                select(RfpDepartmentSection).where(
                    RfpDepartmentSection.ticket_id == str(ticket_id)
                )
            ).all()
            handoff = session.get(RfpHandoff, str(ticket_id))
            metadata = session.get(RfpMetadataRecord, str(ticket_id))
            try:
                active_sections = validate_approval_handoff(
                    str(ticket_id),
                    handoff.payload if handoff else None,
                    all_sections,
                )
            except RfpApprovalError as exc:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT, detail=str(exc)
                ) from exc
            conflicts = detect_structured_conflicts(
                metadata.model_dump() if metadata else {},
                active_sections,
            )
            if conflicts:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="La síntesis está bloqueada por un conflicto de negocio.",
                )
            if metadata is None:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Faltan metadatos RFP persistidos.",
                )
            _record_final_document(
                session,
                ticket,
                metadata,
                [
                    {
                        **item,
                        "approver": section_by_department.approver,
                        "approved_at": section_by_department.approved_at.isoformat()
                        if section_by_department.approved_at
                        else None,
                    }
                    for item in active_sections
                    for section_by_department in [session.get(
                        RfpDepartmentSection, (str(ticket_id), item["department_id"])
                    )]
                ],
            )
    else:
        should_reprocess = _prepare_revision(
            section, branch, payload.comment or ""
        )
        if should_reprocess:
            handoff = session.get(RfpHandoff, str(ticket_id))
            if handoff is None:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="El handoff del ticket no está disponible.",
                )
            _sync_handoff_section(handoff, section)
            session.add(handoff)
            ticket.status = "generando_borrador"
            ticket.processing_started_at = datetime.now(UTC)
            ticket.processing_error = None
        else:
            ticket.status = "needs_human_review"
        section.approver = current_user.email
        section.approved_at = None
        session.add(section)
        session.add(branch)
    ticket.updated_at = datetime.now(UTC)
    session.add(ticket)
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="La sección ya recibió una decisión para esta versión.",
        ) from exc
    session.refresh(ticket)
    if payload.action != "approve" and branch.status == "revision_requested":
        background_tasks.add_task(process_rfp_response_generation, ticket.ticket_id)
    return {
        "decision": decision.model_dump(
            mode="json",
            exclude={"draft_snapshot", "evaluation_snapshot", "idempotency_key"},
        ),
        "ticket": _summary(ticket).model_dump(),
    }


@rfp_intake_api.get("/tickets/{ticket_id}/final-document")
def download_rfp_final_document(
    ticket_id: UUID,
    current_user: UserInDB = AUTHENTICATED_USER,
    session: Session = DATABASE_SESSION,
) -> JSONResponse:
    ticket = _visible_ticket(session, str(ticket_id), current_user)
    document = session.get(RfpFinalDocument, ticket.ticket_id)
    if document is None or ticket.status != "terminado":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="El documento final todavía no está disponible.",
        )
    payload = document.model_dump(mode="json")
    return JSONResponse(
        content=payload,
        headers={
            "Content-Disposition": (
                f'attachment; filename="rfp-{ticket.ticket_id}-final.json"'
            )
        },
    )

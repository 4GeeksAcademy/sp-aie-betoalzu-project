from __future__ import annotations

import logging
import os
import threading
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
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
from pydantic import BaseModel, Field
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Session, select

from data_project.pipelines.rfp_intake.graph import RfpIntakeError
from data_project.pipelines.rfp_intake.responses import generate_rfp_responses
from services import database
from services.api.rfp_intake.models import (
    RfpDepartmentSection,
    RfpHandoff,
    RfpMetadataRecord,
    RfpTicket,
)
from services.api.users.auth import get_current_user
from services.api.users.models import UserInDB

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
    created_at: datetime
    updated_at: datetime


class TicketDetail(TicketSummary):
    classification: dict[str, Any] | None = None
    metadata: dict[str, Any] | None = None
    sections: list[dict[str, Any]] = Field(default_factory=list)
    handoff: dict[str, Any] | None = None


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
        created_at=ticket.created_at,
        updated_at=ticket.updated_at,
    )


def _detail(session: Session, ticket: RfpTicket) -> TicketDetail:
    metadata = session.get(RfpMetadataRecord, ticket.ticket_id)
    handoff = session.get(RfpHandoff, ticket.ticket_id)
    sections = session.exec(
        select(RfpDepartmentSection).where(
            RfpDepartmentSection.ticket_id == ticket.ticket_id
        )
    ).all()
    return TicketDetail(
        **_summary(ticket).model_dump(),
        classification=ticket.classification_result,
        metadata=metadata.model_dump(mode="json") if metadata else None,
        sections=[section.model_dump(mode="json") for section in sections],
        handoff=handoff.payload if handoff else None,
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
) -> None:
    with Session(database.engine) as session:
        ticket = session.get(RfpTicket, ticket_id)
        handoff = session.get(RfpHandoff, ticket_id)
        if (
            ticket is None
            or handoff is None
            or not _is_current_generation(ticket, started_at)
        ):
            raise RfpIntakeError("El ticket o handoff desapareció durante la generación.")
        for section_result in result["sections"]:
            section = session.get(
                RfpDepartmentSection,
                (ticket_id, section_result["department_id"]),
            )
            if section is None:
                raise RfpIntakeError(
                    "Una sección desapareció durante la generación de respuestas."
                )
            section.draft_content = section_result["draft_content"]
            section.evaluation_results = section_result["evaluation_results"]
            session.add(section)

        handoff.payload = result["handoff"]
        handoff.schema_version = result["handoff"]["schema_version"]
        handoff.status = result["handoff"]["response_generation"]["status"]
        ticket.status = result["status"]
        ticket.processing_error = None
        ticket.processing_started_at = None
        ticket.updated_at = datetime.now(UTC)
        session.add(handoff)
        session.add(ticket)
        session.commit()


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
        ticket.status = "analisis_completo"
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
        _persist_response_generation(ticket_id, run_started_at, result)
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

    background_tasks.add_task(process_rfp_ticket, ticket_id)
    return _summary(ticket)


@rfp_intake_api.get("/tickets", response_model=list[TicketSummary])
def list_rfp_tickets(
    current_user: UserInDB = AUTHENTICATED_USER,
    session: Session = DATABASE_SESSION,
) -> list[TicketSummary]:
    tickets = session.exec(
        select(RfpTicket)
        .where(RfpTicket.created_by == str(current_user.id))
        .order_by(RfpTicket.created_at.desc())
        .limit(100)
    ).all()
    stale_ticket_found = False
    for ticket in tickets:
        stale_ticket_found = _mark_if_stale(ticket) or stale_ticket_found
    if stale_ticket_found:
        session.add_all(tickets)
        session.commit()
    return [_summary(ticket) for ticket in tickets]


@rfp_intake_api.get("/tickets/{ticket_id}", response_model=TicketDetail)
def read_rfp_ticket(
    ticket_id: UUID,
    current_user: UserInDB = AUTHENTICATED_USER,
    session: Session = DATABASE_SESSION,
) -> TicketDetail:
    ticket = _owned_ticket(session, str(ticket_id), current_user)
    return _detail(session, ticket)


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

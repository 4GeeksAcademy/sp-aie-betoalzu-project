from __future__ import annotations

import logging
import os
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
    if ticket.status != "analizando" or started_at is None:
        return False
    if started_at.tzinfo is None:
        started_at = started_at.replace(tzinfo=UTC)
    if started_at >= datetime.now(UTC) - STALE_AFTER:
        return False
    ticket.processing_error = "La ejecución anterior se interrumpió; puede reintentarse."
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


def recover_interrupted_rfp_intake() -> None:
    with Session(database.engine) as session:
        interrupted = session.exec(
            select(RfpTicket).where(
                RfpTicket.status == "analizando",
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

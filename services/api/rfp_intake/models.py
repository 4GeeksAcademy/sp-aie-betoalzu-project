from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import Column
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.types import JSON
from sqlmodel import Field, SQLModel

JSON_TYPE = JSON().with_variant(JSONB(), "postgresql")


def _now() -> datetime:
    return datetime.now(UTC)


class RfpTicket(SQLModel, table=True):
    __tablename__ = "rfp_intake_tickets"

    ticket_id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    rfp_id: str = Field(default_factory=lambda: str(uuid4()), unique=True, index=True)
    status: str = Field(default="analizando", index=True)
    raw_pdf_path: str = Field(max_length=1024)
    created_by: str = Field(index=True, max_length=120)
    classification_result: dict | None = Field(
        default=None,
        sa_column=Column(JSON_TYPE, nullable=True),
    )
    processing_error: str | None = Field(default=None, max_length=500)
    processing_started_at: datetime | None = Field(default=None, index=True)
    retry_count: int = Field(default=0, ge=0)
    created_at: datetime = Field(default_factory=_now, index=True)
    updated_at: datetime = Field(default_factory=_now)


class RfpMetadataRecord(SQLModel, table=True):
    __tablename__ = "rfp_intake_metadata"

    ticket_id: str = Field(
        foreign_key="rfp_intake_tickets.ticket_id", primary_key=True
    )
    client_name: str | None = Field(default=None, max_length=255)
    client_hq: str = Field(default="no_especificado", max_length=40)
    services_requested: list[str] = Field(
        default_factory=list,
        sa_column=Column(JSON_TYPE, nullable=False),
    )
    service_types: list[str] = Field(
        default_factory=list,
        sa_column=Column(JSON_TYPE, nullable=False),
    )
    scope: str | None = Field(default=None)
    deadline: str | None = Field(default=None, max_length=255)
    budget_range: str | None = Field(default=None, max_length=255)
    currency: str | None = Field(default=None, max_length=3)
    departments_needed: list[str] = Field(
        default_factory=list,
        sa_column=Column(JSON_TYPE, nullable=False),
    )
    department_extracts: dict[str, str] = Field(
        default_factory=dict,
        sa_column=Column(JSON_TYPE, nullable=False),
    )
    explicitly_requests_recruitment: bool = Field(default=False)
    open_questions: list[str] = Field(
        default_factory=list,
        sa_column=Column(JSON_TYPE, nullable=False),
    )
    field_evidence: dict[str, str] = Field(
        default_factory=dict,
        sa_column=Column(JSON_TYPE, nullable=False),
    )
    readability_metrics: dict = Field(
        default_factory=dict,
        sa_column=Column(JSON_TYPE, nullable=False),
    )
    created_at: datetime = Field(default_factory=_now)


class RfpDepartmentSection(SQLModel, table=True):
    __tablename__ = "rfp_intake_department_sections"

    ticket_id: str = Field(
        foreign_key="rfp_intake_tickets.ticket_id", primary_key=True
    )
    department_id: str = Field(primary_key=True, max_length=40)
    key_aspects: list[dict] = Field(
        default_factory=list,
        sa_column=Column(JSON_TYPE, nullable=False),
    )
    draft_content: str | None = Field(default=None)
    evaluation_results: dict | None = Field(
        default=None,
        sa_column=Column(JSON_TYPE, nullable=True),
    )
    approval_status: str = Field(default="pending", max_length=40)
    approver: str | None = Field(default=None, max_length=120)
    approved_at: datetime | None = Field(default=None)


class RfpHandoff(SQLModel, table=True):
    __tablename__ = "rfp_intake_handoffs"

    ticket_id: str = Field(
        foreign_key="rfp_intake_tickets.ticket_id", primary_key=True
    )
    schema_version: str = Field(max_length=20)
    status: str = Field(default="ready", max_length=40)
    payload: dict = Field(sa_column=Column(JSON_TYPE, nullable=False))
    created_at: datetime = Field(default_factory=_now)

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import Column, Index
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


class RfpApprovalBranch(SQLModel, table=True):
    __tablename__ = "rfp_intake_approval_branches"

    ticket_id: str = Field(
        foreign_key="rfp_intake_tickets.ticket_id", primary_key=True
    )
    department_id: str = Field(primary_key=True, max_length=40)
    thread_id: str = Field(unique=True, max_length=160)
    draft_sha256: str = Field(max_length=64)
    draft_version: int = Field(ge=1)
    status: str = Field(default="pending", max_length=40)
    updated_at: datetime = Field(default_factory=_now)


class RfpApprovalDecision(SQLModel, table=True):
    __tablename__ = "rfp_intake_approval_decisions"
    __table_args__ = (
        Index(
            "uq_rfp_approval_decision_version",
            "ticket_id",
            "department_id",
            "draft_sha256",
            "draft_version",
            unique=True,
        ),
    )

    decision_id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    idempotency_key: str = Field(unique=True, index=True, max_length=64)
    ticket_id: str = Field(
        foreign_key="rfp_intake_tickets.ticket_id", index=True, max_length=36
    )
    department_id: str = Field(max_length=40, index=True)
    approver_user_id: int
    approver_email: str = Field(max_length=255)
    action: str = Field(max_length=40)
    comment: str | None = Field(default=None)
    draft_sha256: str = Field(max_length=64)
    draft_version: int = Field(ge=1)
    result: str = Field(max_length=40)
    draft_snapshot: str = Field()
    evaluation_snapshot: dict = Field(sa_column=Column(JSON_TYPE, nullable=False))
    created_at: datetime = Field(default_factory=_now, index=True)


class RfpFinalDocument(SQLModel, table=True):
    __tablename__ = "rfp_intake_final_documents"

    ticket_id: str = Field(
        foreign_key="rfp_intake_tickets.ticket_id", primary_key=True
    )
    document_format: str = Field(default="application/json", max_length=100)
    version: int = Field(default=1, ge=1)
    sections: list[dict] = Field(
        sa_column=Column(JSON_TYPE, nullable=False),
    )
    currency: str | None = Field(default=None, max_length=3)
    section_digests: dict[str, str] = Field(
        sa_column=Column(JSON_TYPE, nullable=False),
    )
    generated_at: datetime = Field(default_factory=_now)


class RfpArbitrationRecord(SQLModel, table=True):
    __tablename__ = "rfp_intake_arbitrations"

    arbitration_id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    idempotency_key: str = Field(unique=True, index=True, max_length=64)
    ticket_id: str = Field(
        foreign_key="rfp_intake_tickets.ticket_id", index=True, max_length=36
    )
    trigger_id: str = Field(max_length=80)
    departments: list[str] = Field(
        sa_column=Column(JSON_TYPE, nullable=False),
    )
    arbitrator: str = Field(max_length=120)
    rule: str = Field()
    evidence: dict | list = Field(sa_column=Column(JSON_TYPE, nullable=False))
    section_snapshots: dict[str, Any] = Field(
        sa_column=Column(JSON_TYPE, nullable=False),
    )
    result: str = Field(max_length=40)
    created_at: datetime = Field(default_factory=_now, index=True)

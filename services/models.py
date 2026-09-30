from __future__ import annotations

from datetime import date, datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, Column, DateTime, Index, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.types import JSON
from sqlmodel import Field, SQLModel


# ---------------------------------------------------------------------------
# Asset — catálogo de productos/activos (table=True)
# ---------------------------------------------------------------------------


class Asset(SQLModel, table=True):
    """Activo o producto del inventario de Nexova.

    `current_stock` no se almacena aquí; se calcula como:
        SUM(AssetEntry.quantity) - SUM(AssetExit.quantity)
    """

    __tablename__ = "assets"  # type: ignore[ misc ]

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(min_length=1, max_length=255)
    sku: str = Field(min_length=1, max_length=50, unique=True, index=True)
    category: str = Field(max_length=50)  # "hardware" | "peripherals" | "office_supplies" | "training_materials"
    office: str = Field(max_length=50)    # "Valencia" | "Miami"
    currency: str = Field(max_length=3)    # "USD" | "EUR"
    unit_cost: float | None = Field(default=None, description="Coste unitario del producto")
    program: str | None = Field(default=None, max_length=100, description="Programa asociado (ventas B2B, Onboarding, formación de liderazgo)")


# ---------------------------------------------------------------------------
# AssetEntry — entrada/entrega de activos (Inbound order)
# ---------------------------------------------------------------------------


class AssetEntry(SQLModel, table=True):
    """Registro de una compra o entrega recibida por Nexova."""

    __tablename__ = "asset_entries"  # type: ignore[ misc ]

    id: int | None = Field(default=None, primary_key=True)
    asset_id: int = Field(foreign_key="assets.id", index=True)
    quantity: int = Field(gt=0)
    supplier: str = Field(min_length=1, max_length=255)
    office: str = Field(max_length=50)  # "Valencia" | "Miami"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    user_uuid: str = Field(
        min_length=1,
        max_length=100,
        description="UUID del responsable de IT/operaciones (de TinyDB)",
    )


# ---------------------------------------------------------------------------
# AssetExit — salida/asignación/consumo de activos (Outbound order)
# ---------------------------------------------------------------------------


class AssetExit(SQLModel, table=True):
    """Registro de una asignación a un empleado o un evento de consumo."""

    __tablename__ = "asset_exits"  # type: ignore[ misc ]

    id: int | None = Field(default=None, primary_key=True)
    asset_id: int = Field(foreign_key="assets.id", index=True)
    quantity: int = Field(gt=0)
    exit_type: str = Field(max_length=20)  # "allocation" | "consumption"
    assigned_to: str | None = Field(
        default=None,
        max_length=255,
        description="Nombre o ID del empleado si exit_type=allocation. Nulo para consumos.",
    )
    office: str = Field(max_length=50)  # "Valencia" | "Miami"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    user_uuid: str = Field(
        min_length=1,
        max_length=100,
        description="UUID del responsable que registró la salida (de TinyDB)",
    )


class TelemetryEventRecord(SQLModel, table=True):
    """Evento de telemetría inmutable almacenado para análisis."""

    __tablename__ = "telemetry_events"  # type: ignore[misc]

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    timestamp: datetime = Field(index=True)
    service: str
    event_type: str = Field(index=True)
    level: str = Field(default="info")
    value: float | None = Field(default=None)
    message: str | None = Field(default=None)
    tags: dict = Field(
        default_factory=dict,
        sa_column=Column(JSON().with_variant(JSONB(), "postgresql"), nullable=False),
    )


Index(
    "ix_telemetry_events_tags_gin",
    TelemetryEventRecord.tags,
    postgresql_using="gin",
)


class JobRun(SQLModel, table=True):
    """Orchestration record for independent background jobs."""

    __tablename__ = "job_runs"  # type: ignore[misc]
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'processing', 'completed', 'failed')",
            name="ck_job_runs_status",
        ),
        Index("ix_job_runs_job_name_target_date", "job_name", "target_date"),
        Index(
            "ux_job_runs_processing",
            "job_name",
            "target_date",
            unique=True,
            sqlite_where=text("status = 'processing'"),
            postgresql_where=text("status = 'processing'"),
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    job_name: str = Field(index=True, max_length=100)
    target_date: date = Field(index=True)
    status: str = Field(default="pending", max_length=20)
    started_at: datetime | None = None
    finished_at: datetime | None = None
    error_message: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class IncidentAnalysisTaskRecord(SQLModel, table=True):
    __tablename__ = "incident_analysis_tasks"  # type: ignore[misc]

    task_id: str = Field(primary_key=True, max_length=36)
    owner_id: int = Field(index=True)
    source_filename: str = Field(max_length=255)
    result_summary: dict | None = Field(
        default=None,
        sa_column=Column(JSON().with_variant(JSONB(), "postgresql"), nullable=True),
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )


class IncidentAnalysisDeadLetter(SQLModel, table=True):
    __tablename__ = "incident_analysis_dead_letters"  # type: ignore[misc]

    task_id: str = Field(primary_key=True, max_length=36)
    attempt_number: int = Field(gt=0)
    error_message: str = Field(sa_column=Column(Text, nullable=False))
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )

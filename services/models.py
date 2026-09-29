from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import Column, Index
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

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, field_validator


# ---------------------------------------------------------------------------
# Enums — shared by schemas
# ---------------------------------------------------------------------------


class ExitType(str, Enum):
    ALLOCATION = "allocation"
    CONSUMPTION = "consumption"


class AssetCategory(str, Enum):
    HARDWARE = "hardware"
    PERIPHERALS = "peripherals"
    OFFICE_SUPPLIES = "office_supplies"
    TRAINING_MATERIALS = "training_materials"


class Office(str, Enum):
    VALENCIA = "Valencia"
    MIAMI = "Miami"


# ===================================================================
# Asset (producto) — request / response schemas
# ===================================================================


class AssetCreate(BaseModel):
    """Request schema for creating a new asset."""

    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(min_length=1, description="Ej.: Portátil 14\" Business, Ratón ergonómico")
    sku: str = Field(min_length=1, description="Código único, ej.: NXV-IT-001")
    category: AssetCategory
    office: Office


class AssetUpdate(BaseModel):
    """Request schema for updating an existing asset."""

    model_config = ConfigDict(str_strip_whitespace=True)

    name: str | None = Field(default=None, min_length=1)
    sku: str | None = Field(default=None, min_length=1)
    category: AssetCategory | None = None
    office: Office | None = None


class AssetResponse(BaseModel):
    """Response schema for an asset, including calculated current_stock."""

    id: int
    name: str
    sku: str
    category: AssetCategory
    office: Office
    current_stock: int = 0


# ===================================================================
# AssetEntry (entrada / inbound order) — request / response schemas
# ===================================================================


class AssetEntryCreate(BaseModel):
    """Request schema for registering an inbound delivery.

    user_uuid se extrae del token JWT del usuario autenticado,
    no se lee del body de la petición.
    """

    model_config = ConfigDict(str_strip_whitespace=True)

    asset_id: int
    quantity: int = Field(gt=0, description="Unidades recibidas")
    supplier: str = Field(min_length=1)
    office: Office
    user_uuid: str | None = Field(
        default=None,
        description="IGNORADO — se sobreescribe con el UUID del usuario autenticado (JWT)",
    )


class AssetEntryResponse(BaseModel):
    """Response schema for an inbound order entry."""

    id: int
    asset_id: int
    quantity: int
    supplier: str
    office: Office
    created_at: str
    user_uuid: str


# ===================================================================
# AssetExit (salida / outbound order) — request / response schemas
# ===================================================================


class AssetExitCreate(BaseModel):
    """Request schema for registering an outbound allocation or consumption.

    user_uuid se extrae del token JWT del usuario autenticado,
    no se lee del body de la petición.
    """

    model_config = ConfigDict(str_strip_whitespace=True)

    asset_id: int
    quantity: int = Field(gt=0, description="Unidades asignadas o consumidas")
    exit_type: ExitType
    assigned_to: str | None = Field(
        default=None,
        description="Nombre o ID del empleado si exit_type=allocation. Nulo para consumos.",
    )
    office: Office
    user_uuid: str | None = Field(
        default=None,
        description="IGNORADO — se sobreescribe con el UUID del usuario autenticado (JWT)",
    )

    @field_validator("assigned_to")
    @classmethod
    def validate_assigned_to(cls, v: str | None, info) -> str | None:
        """assigned_to is required when exit_type=allocation, null when consumption."""
        values = info.data
        exit_type = values.get("exit_type") if values else None
        if exit_type == ExitType.ALLOCATION and not v:
            raise ValueError(
                "assigned_to is required when exit_type is 'allocation'."
            )
        if exit_type == ExitType.CONSUMPTION and v is not None:
            raise ValueError(
                "assigned_to must be null when exit_type is 'consumption'."
            )
        return v


class AssetExitResponse(BaseModel):
    """Response schema for an outbound order exit."""

    id: int
    asset_id: int
    quantity: int
    exit_type: ExitType
    assigned_to: str | None = None
    office: Office
    created_at: str
    user_uuid: str


# ===================================================================
# Combined order listing schema
# ===================================================================


class OrderResponse(BaseModel):
    """Combined response schema for GET /inventory/orders."""

    id: int
    type: str  # "entry" or "exit"
    asset_id: int
    asset_name: str
    asset_sku: str
    quantity: int
    office: Office
    user_uuid: str
    created_at: str
    # Entry-specific
    supplier: str | None = None
    # Exit-specific
    exit_type: ExitType | None = None
    assigned_to: str | None = None

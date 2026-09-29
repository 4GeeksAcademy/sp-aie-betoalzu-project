from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, field_validator


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class ExitType(str, Enum):
    ALLOCATION = "allocation"
    CONSUMPTION = "consumption"


class AssetCategory(str, Enum):
    HARDWARE = "hardware"
    PERIPHERALS = "peripherals"
    OFFICE_SUPPLIES = "office_supplies"
    TRAINING_MATERIALS = "training_materials"
    CERTIFICATION = "certification"
    ONBOARDING_EQUIPMENT = "onboarding_equipment"


class Office(str, Enum):
    VALENCIA = "Valencia"
    MIAMI = "Miami"


class Currency(str, Enum):
    USD = "USD"
    EUR = "EUR"


class Program(str, Enum):
    B2B_SALES = "ventas B2B"
    ONBOARDING = "Onboarding"
    LEADERSHIP_TRAINING = "formación de liderazgo"


# ---------------------------------------------------------------------------
# Asset
# ---------------------------------------------------------------------------


class AssetBase(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(min_length=1, description="Ej.: Portátil 14\" Business, Ratón ergonómico")
    sku: str = Field(min_length=1, description="Código único, ej.: NXV-IT-001")
    category: AssetCategory
    office: Office
    currency: Currency
    unit_cost: float | None = Field(default=None, description="Coste unitario del producto")
    program: str | None = Field(default=None, description="Programa asociado asignado según categoría")


class AssetCreate(AssetBase):
    pass


class AssetUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str | None = Field(default=None, min_length=1)
    sku: str | None = Field(default=None, min_length=1)
    category: AssetCategory | None = None
    office: Office | None = None
    currency: Currency | None = None
    unit_cost: float | None = None
    program: str | None = None


class AssetResponse(AssetBase):
    id: int
    current_stock: int = 0


# ---------------------------------------------------------------------------
# AssetEntry (Inbound)
# ---------------------------------------------------------------------------


class AssetEntryBase(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    asset_id: int
    quantity: int = Field(gt=0, description="Unidades recibidas")
    supplier: str = Field(min_length=1)
    office: Office
    user_uuid: str = Field(min_length=1, description="UUID del responsable de IT/operaciones (de TinyDB)")


class AssetEntryCreate(AssetEntryBase):
    pass


class AssetEntryResponse(AssetEntryBase):
    id: int
    created_at: str


# ---------------------------------------------------------------------------
# AssetExit (Outbound)
# ---------------------------------------------------------------------------


class AssetExitBase(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    asset_id: int
    quantity: int = Field(gt=0, description="Unidades asignadas o consumidas")
    exit_type: ExitType
    assigned_to: str | None = Field(
        default=None,
        description="Nombre o ID del empleado si exit_type=allocation. Nulo para consumos.",
    )
    office: Office
    user_uuid: str = Field(min_length=1, description="UUID del responsable que registró la salida (de TinyDB)")

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


class AssetExitCreate(AssetExitBase):
    pass


class AssetExitResponse(AssetExitBase):
    id: int
    created_at: str


# ---------------------------------------------------------------------------
# Order listing (combined)
# ---------------------------------------------------------------------------


class OrderResponse(BaseModel):
    """Combined response for GET /inventory/orders."""
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

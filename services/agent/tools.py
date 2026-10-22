from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from services.api.incidents.models import (
    IncidentBranch,
    IncidentCategory,
    IncidentOrigin,
    IncidentOut,
    IncidentStatus,
)
from services.api.inventory.models import AssetResponse

SourceStatus = Literal["success", "not_found", "failed"]
SourceError = Literal[
    "not_configured",
    "timeout",
    "service_error",
    "invalid_response",
    "authentication_failed",
    "authorization_failed",
]


class IncidentQuery(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    incident_id: int | None = Field(default=None, gt=0)
    ticket_id: str | None = Field(default=None, min_length=1, max_length=50)
    status: IncidentStatus | None = None
    category: IncidentCategory | None = None
    branch: IncidentBranch | None = None
    origin: IncidentOrigin | None = None


class IncidentResult(BaseModel):
    status: SourceStatus
    incidents: list[IncidentOut] = Field(default_factory=list)
    error: SourceError | None = None


class InventoryQuery(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    product_id: int | None = Field(default=None, gt=0)
    search: str | None = Field(default=None, min_length=1)


class InventoryResult(BaseModel):
    status: SourceStatus
    products: list[AssetResponse] = Field(default_factory=list)
    error: SourceError | None = None

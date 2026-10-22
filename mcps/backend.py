from __future__ import annotations

import os
from dataclasses import dataclass
from enum import Enum
from typing import Any
from urllib.parse import urlencode, urlsplit

import requests
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from services.api.incidents.models import (
    IncidentBranch,
    IncidentCategory,
    IncidentCreate,
    IncidentOrigin,
    IncidentOut,
    IncidentStatus,
    IncidentUpdate,
)
from services.api.inventory.models import AssetResponse

BACKEND_TIMEOUT = 5.0


class InventoryOperation(str, Enum):
    CREATE_PRODUCT = "create_product"
    UPDATE_PRODUCT = "update_product"
    DELETE_PRODUCT = "delete_product"
    CREATE_INBOUND_ORDER = "create_inbound_order"
    CREATE_OUTBOUND_ORDER = "create_outbound_order"


class IncidentCreateInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    title: str = Field(min_length=1, max_length=120, description="Título de la incidencia.")
    description: str | None = Field(default=None, description="Descripción detallada.")
    category: IncidentCategory = Field(description="Categoría de la incidencia.")
    origin: IncidentOrigin = Field(description="Origen: customer, branch o internal.")
    branch: IncidentBranch = Field(
        default=IncidentBranch.CENTRAL, description="Sede; por defecto central.",
    )
    reported_by: str | None = Field(default=None, max_length=255)
    assigned_to: str | None = Field(default=None, max_length=255)
    ticket_id: str | None = Field(default=None, max_length=50)

    @model_validator(mode="after")
    def reject_empty_title(self) -> IncidentCreateInput:
        if not self.title.strip():
            raise ValueError("title cannot be empty")
        return self

    def to_backend_model(self) -> IncidentCreate:
        return IncidentCreate.model_validate(self.model_dump(exclude_none=True))


class IncidentGetInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    incident_id: int | None = Field(default=None, gt=0, description="ID numérico positivo.")
    ticket_id: str | None = Field(default=None, min_length=1, max_length=50)
    status: IncidentStatus | None = None
    category: IncidentCategory | None = None
    branch: IncidentBranch | None = None
    origin: IncidentOrigin | None = None

    @model_validator(mode="after")
    def require_filter(self) -> IncidentGetInput:
        if not any(
            getattr(self, field) is not None
            for field in ("incident_id", "ticket_id", "status", "category", "branch", "origin")
        ):
            raise ValueError("Provide an incident_id or at least one filter.")
        return self


class IncidentUpdateInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    incident_id: int = Field(gt=0, description="ID numérico positivo.")
    title: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = None
    category: IncidentCategory | None = None
    origin: IncidentOrigin | None = None
    branch: IncidentBranch | None = None
    reported_by: str | None = Field(default=None, max_length=255)
    assigned_to: str | None = Field(default=None, max_length=255)
    ticket_id: str | None = Field(default=None, max_length=50)

    @model_validator(mode="after")
    def require_mutable_field(self) -> IncidentUpdateInput:
        mutable_fields = set(self.model_fields_set) - {"incident_id"}
        if not mutable_fields:
            raise ValueError("Provide at least one incident field to update.")
        return self

    def to_backend_model(self) -> IncidentUpdate:
        fields = self.model_dump(exclude={"incident_id"}, exclude_unset=True)
        return IncidentUpdate.model_validate(fields)


class IncidentTransitionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    incident_id: int = Field(gt=0, description="ID numérico positivo.")
    status: IncidentStatus


class InventoryGetInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    product_id: int | None = Field(default=None, gt=0, description="ID numérico positivo.")
    search: str | None = Field(default=None, min_length=1, description="Buscar en nombre o SKU.")


class InventoryWriteInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operation: InventoryOperation
    payload: dict[str, Any] | None = None


class BackendFailure(Exception):
    def __init__(self, code: str, message: str, status_code: int | None = None) -> None:
        self.code = code
        self.message = message
        self.status_code = status_code
        super().__init__(code)


@dataclass(frozen=True)
class BackendResponse:
    status_code: int
    payload: Any = None


def _backend_url() -> str:
    value = os.getenv("SUPPORT_AGENT_BACKEND_URL", "").strip().rstrip("/")
    parsed = urlsplit(value)
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
    ):
        raise BackendFailure(
            "BACKEND_NOT_CONFIGURED",
            "Backend URL must be an HTTP(S) URL without credentials or query parameters.",
        )
    return value


def _send(
    method: str,
    path: str,
    *,
    authenticated: bool = False,
    params: dict[str, str] | None = None,
    payload: dict[str, Any] | None = None,
) -> BackendResponse:
    base_url = _backend_url()
    headers: dict[str, str] = {}
    if authenticated:
        token = os.getenv("SUPPORT_AGENT_SERVICE_TOKEN", "").strip()
        if not token:
            raise BackendFailure(
                "BACKEND_NOT_CONFIGURED",
                "Service credentials for the incidents API are not configured.",
            )
        headers["Authorization"] = f"Bearer {token}"

    url = f"{base_url}{path}"
    if params:
        url = f"{url}?{urlencode(params)}"
    try:
        response = requests.request(
            method,
            url,
            headers=headers,
            json=payload,
            timeout=BACKEND_TIMEOUT,
            allow_redirects=False,
        )
    except requests.Timeout as exc:
        raise BackendFailure("UPSTREAM_TIMEOUT", "The backend request timed out.") from exc
    except requests.RequestException as exc:
        raise BackendFailure("UPSTREAM_ERROR", "The backend request failed.") from exc

    try:
        status_code = response.status_code
        if not 200 <= status_code < 300:
            return BackendResponse(status_code=status_code)
        try:
            return BackendResponse(status_code=status_code, payload=response.json())
        except (ValueError, requests.exceptions.JSONDecodeError) as exc:
            raise BackendFailure(
                "INVALID_UPSTREAM_RESPONSE",
                "The backend returned invalid JSON.",
                status_code,
            ) from exc
    finally:
        response.close()


def _incident_output(payload: Any) -> IncidentOut:
    try:
        return IncidentOut.model_validate(payload)
    except ValidationError as exc:
        raise BackendFailure(
            "INVALID_UPSTREAM_RESPONSE", "The backend returned an invalid incident.",
        ) from exc


def _product_output(payload: Any) -> AssetResponse:
    try:
        result = AssetResponse.model_validate(payload)
    except ValidationError as exc:
        raise BackendFailure(
            "INVALID_UPSTREAM_RESPONSE", "The backend returned an invalid product.",
        ) from exc
    if "current_stock" not in result.model_fields_set:
        raise BackendFailure(
            "INVALID_UPSTREAM_RESPONSE",
            "The backend product response omitted current_stock.",
        )
    return result


def create_incident(payload: IncidentCreateInput) -> IncidentOut:
    response = _send(
        "POST",
        "/api/incidents",
        authenticated=True,
        payload=payload.to_backend_model().model_dump(
            mode="json", exclude_none=True, exclude={"status"},
        ),
    )
    if response.status_code == 404:
        raise BackendFailure("UPSTREAM_ERROR", "The backend rejected incident creation.", 404)
    if not 200 <= response.status_code < 300:
        raise BackendFailure("UPSTREAM_ERROR", "The backend could not create the incident.", response.status_code)
    return _incident_output(response.payload)


def get_incidents(query: IncidentGetInput) -> list[IncidentOut]:
    if query.incident_id is not None:
        response = _send(
            "GET", f"/api/incidents/{query.incident_id}", authenticated=True,
        )
        if response.status_code == 404:
            raise BackendFailure("INCIDENT_NOT_FOUND", "No incident matched this ID.", 404)
        if not 200 <= response.status_code < 300:
            raise BackendFailure("UPSTREAM_ERROR", "The incidents API request failed.", response.status_code)
        incidents = [_incident_output(response.payload)]
    else:
        filters = {
            key: value.value
            for key in ("status", "category", "branch", "origin")
            if (value := getattr(query, key)) is not None
        }
        response = _send(
            "GET",
            "/api/incidents",
            authenticated=True,
            params=filters or None,
        )
        if not 200 <= response.status_code < 300:
            raise BackendFailure("UPSTREAM_ERROR", "The incidents API request failed.", response.status_code)
        try:
            incidents = [IncidentOut.model_validate(item) for item in response.payload]
        except (TypeError, ValidationError) as exc:
            raise BackendFailure(
                "INVALID_UPSTREAM_RESPONSE", "The backend returned an invalid incident list.",
            ) from exc

    if query.ticket_id is not None:
        incidents = [item for item in incidents if item.ticket_id == query.ticket_id]
    return [
        item for item in incidents
        if all(
            getattr(item, field) == value.value
            for field in ("status", "category", "branch", "origin")
            if (value := getattr(query, field)) is not None
        )
    ]


def update_incident(payload: IncidentUpdateInput) -> IncidentOut:
    response = _send(
        "PUT",
        f"/api/incidents/{payload.incident_id}",
        authenticated=True,
        payload=payload.to_backend_model().model_dump(
            mode="json", exclude_unset=True,
        ),
    )
    if response.status_code == 404:
        raise BackendFailure("INCIDENT_NOT_FOUND", "No incident matched this ID.", 404)
    if not 200 <= response.status_code < 300:
        raise BackendFailure("UPSTREAM_ERROR", "The incidents API request failed.", response.status_code)
    return _incident_output(response.payload)


def transition_incident(payload: IncidentTransitionInput) -> IncidentOut:
    response = _send(
        "PATCH",
        f"/api/incidents/{payload.incident_id}/status",
        authenticated=True,
        payload={"status": payload.status.value},
    )
    if response.status_code == 404:
        raise BackendFailure("INCIDENT_NOT_FOUND", "No incident matched this ID.", 404)
    if response.status_code in {400, 409}:
        raise BackendFailure(
            "INVALID_STATUS_TRANSITION",
            "The backend rejected this incident status transition.",
            response.status_code,
        )
    if not 200 <= response.status_code < 300:
        raise BackendFailure("UPSTREAM_ERROR", "The incidents API request failed.", response.status_code)
    return _incident_output(response.payload)


def get_products(query: InventoryGetInput) -> list[AssetResponse]:
    path = (
        f"/inventory/products/{query.product_id}"
        if query.product_id is not None
        else "/inventory/products"
    )
    response = _send("GET", path)
    if response.status_code == 404:
        raise BackendFailure("PRODUCT_NOT_FOUND", "No product matched this ID.", 404)
    if not 200 <= response.status_code < 300:
        raise BackendFailure("UPSTREAM_ERROR", "The inventory API request failed.", response.status_code)

    try:
        products = (
            [_product_output(response.payload)]
            if query.product_id is not None
            else [_product_output(item) for item in response.payload]
        )
    except (TypeError, ValidationError) as exc:
        raise BackendFailure(
            "INVALID_UPSTREAM_RESPONSE", "The backend returned an invalid product list.",
        ) from exc

    if query.search is not None:
        search = query.search.casefold()
        products = [
            product for product in products
            if search in product.name.casefold() or search in product.sku.casefold()
        ]
    return products

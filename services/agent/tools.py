from __future__ import annotations

import logging
import os
from typing import Literal
from urllib.parse import urlsplit

import requests
from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, ValidationError

from services.api.incidents.models import (
    IncidentBranch,
    IncidentCategory,
    IncidentOrigin,
    IncidentOut,
    IncidentStatus,
)
from services.api.inventory.models import AssetResponse

logger = logging.getLogger(__name__)

TOOL_TIMEOUT = 4.0
SourceStatus = Literal["success", "not_found", "failed"]
SourceError = Literal[
    "not_configured", "timeout", "service_error", "invalid_response",
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


class _SourceFailure(Exception):
    def __init__(self, code: SourceError) -> None:
        self.code = code
        super().__init__(code)


def _get(path: str, *, authenticated: bool) -> requests.Response:
    base_url = os.getenv(
        "SUPPORT_AGENT_BACKEND_URL", "http://127.0.0.1:8000",
    ).strip().rstrip("/")
    parsed = urlsplit(base_url)
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
    ):
        raise _SourceFailure("not_configured")
    headers = {}
    if authenticated:
        token = os.getenv("SUPPORT_AGENT_SERVICE_TOKEN", "").strip()
        if not token:
            raise _SourceFailure("not_configured")
        headers["Authorization"] = f"Bearer {token}"
    try:
        response = requests.get(
            f"{base_url}{path}",
            headers=headers,
            timeout=TOOL_TIMEOUT,
            allow_redirects=False,
        )
    except requests.Timeout as exc:
        raise _SourceFailure("timeout") from exc
    except requests.RequestException as exc:
        raise _SourceFailure("service_error") from exc
    if response.status_code != 404 and not 200 <= response.status_code < 300:
        response.close()
        raise _SourceFailure("service_error")
    return response


def query_incidents(query: IncidentQuery) -> IncidentResult:
    from urllib.parse import urlencode

    filters = {
        key: value.value
        for key in ("status", "category", "branch", "origin")
        if (value := getattr(query, key)) is not None
    }
    path = "/api/incidents"
    if query.incident_id is not None:
        path += f"/{query.incident_id}"
    elif filters:
        path += f"?{urlencode(filters)}"
    try:
        with _get(path, authenticated=True) as response:
            if response.status_code == 404:
                if query.incident_id is not None:
                    return IncidentResult(status="not_found")
                raise _SourceFailure("service_error")
            payload = response.json()
            incidents = (
                [IncidentOut.model_validate(payload)]
                if query.incident_id is not None
                else TypeAdapter(list[IncidentOut]).validate_python(payload)
            )
        # The API has no ticket_id filter; match its external ID exactly locally.
        incidents = [
            item for item in incidents
            if (query.ticket_id is None or item.ticket_id == query.ticket_id)
            and all(getattr(item, key) == value for key, value in filters.items())
        ]
        return IncidentResult(
            status="success" if incidents else "not_found", incidents=incidents,
        )
    except _SourceFailure as exc:
        error = exc.code
    except (ValueError, ValidationError):
        error = "invalid_response"
    logger.warning("Support-agent source failed (source=incidents, error=%s)", error)
    return IncidentResult(status="failed", error=error)


def query_inventory(query: InventoryQuery) -> InventoryResult:
    path = "/inventory/products"
    if query.product_id is not None:
        path += f"/{query.product_id}"
    try:
        with _get(path, authenticated=False) as response:
            if response.status_code == 404:
                if query.product_id is not None:
                    return InventoryResult(status="not_found")
                raise _SourceFailure("service_error")
            payload = response.json()
            products = (
                [AssetResponse.model_validate(payload)]
                if query.product_id is not None
                else TypeAdapter(list[AssetResponse]).validate_python(payload)
            )
        if query.search:
            search = query.search.casefold()
            products = [
                item for item in products
                if search in item.name.casefold() or search in item.sku.casefold()
            ]
        return InventoryResult(
            status="success" if products else "not_found", products=products,
        )
    except _SourceFailure as exc:
        error = exc.code
    except (ValueError, ValidationError):
        error = "invalid_response"
    logger.warning("Support-agent source failed (source=inventory, error=%s)", error)
    return InventoryResult(status="failed", error=error)

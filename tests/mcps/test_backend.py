from __future__ import annotations

from unittest.mock import Mock
from uuid import uuid4

import pytest
import requests
from pydantic import ValidationError

from mcps.backend import (
    BackendFailure,
    IncidentCreateInput,
    IncidentGetInput,
    IncidentTransitionInput,
    IncidentUpdateInput,
    InventoryGetInput,
    create_incident,
    get_incidents,
    get_products,
    transition_incident,
    update_incident,
)
from services.api.incidents.models import IncidentOut
from services.api.inventory.models import AssetResponse


@pytest.fixture
def backend(monkeypatch):
    monkeypatch.setenv("SUPPORT_AGENT_BACKEND_URL", "https://backend.example.test")
    monkeypatch.setenv("SUPPORT_AGENT_SERVICE_TOKEN", str(uuid4()))
    request = Mock()
    monkeypatch.setattr("mcps.backend.requests.request", request)
    return request


def response(status_code: int, payload=None):
    result = Mock(status_code=status_code)
    result.json.return_value = payload
    result.close = Mock()
    return result


@pytest.fixture
def incident():
    return IncidentOut(
        id=17,
        title="Consulta de prueba",
        description="Detalle",
        status="in_progress",
        category="technical_failure",
        origin="internal",
        branch="central",
        ticket_id="TKT-017",
        created_at="2026-10-21T09:00:00Z",
        updated_at="2026-10-21T10:00:00Z",
    )


@pytest.fixture
def product():
    return AssetResponse(
        id=3,
        name="Equipo de prueba",
        sku="NXV-IT-003",
        category="hardware",
        office="Valencia",
        currency="EUR",
        current_stock=8,
    )


def test_schemas_reject_unbounded_queries_and_forbidden_fields():
    with pytest.raises(ValidationError):
        IncidentGetInput()
    with pytest.raises(ValidationError):
        IncidentGetInput(incident_id=0)
    with pytest.raises(ValidationError):
        IncidentCreateInput(
            title="Incidente",
            category="technical_failure",
            origin="internal",
            status="resolved",
        )
    with pytest.raises(ValidationError):
        IncidentUpdateInput(incident_id=17, status="resolved")
    with pytest.raises(ValidationError):
        IncidentUpdateInput(incident_id=17)
    with pytest.raises(ValidationError):
        IncidentTransitionInput(incident_id=17, status="closed")
    with pytest.raises(ValidationError):
        InventoryGetInput(search="")


def test_create_uses_allowlisted_post_and_omits_status(backend, incident):
    backend.return_value = response(201, incident.model_dump(mode="json"))
    result = create_incident(IncidentCreateInput(
        title="Consulta de prueba",
        category="technical_failure",
        origin="internal",
    ))

    assert result == incident
    args, kwargs = backend.call_args
    assert args == ("POST", "https://backend.example.test/api/incidents")
    assert kwargs["json"]["title"] == "Consulta de prueba"
    assert "status" not in kwargs["json"]
    assert kwargs["allow_redirects"] is False
    assert kwargs["timeout"] > 0


def test_incident_read_uses_allowed_filters_and_exact_ticket_match(
    backend, incident,
):
    backend.return_value = response(200, [
        incident.model_dump(mode="json"),
        incident.model_copy(update={"ticket_id": "TKT-018"}).model_dump(mode="json"),
    ])
    result = get_incidents(IncidentGetInput(
        ticket_id="TKT-017", status="in_progress", branch="central",
    ))

    assert [item.ticket_id for item in result] == ["TKT-017"]
    args, kwargs = backend.call_args
    assert args == ("GET", "https://backend.example.test/api/incidents?status=in_progress&branch=central")
    assert kwargs["headers"]["Authorization"].startswith("Bearer ")


def test_incident_detail_and_not_found(backend, incident):
    backend.return_value = response(200, incident.model_dump(mode="json"))
    assert get_incidents(IncidentGetInput(incident_id=17)) == [incident]
    assert backend.call_args.args == (
        "GET", "https://backend.example.test/api/incidents/17",
    )

    backend.return_value = response(404)
    with pytest.raises(BackendFailure) as error:
        get_incidents(IncidentGetInput(incident_id=99))
    assert error.value.code == "INCIDENT_NOT_FOUND"


def test_update_uses_put_without_status(backend, incident):
    backend.return_value = response(200, incident.model_dump(mode="json"))
    update_incident(IncidentUpdateInput(incident_id=17, title="Nuevo título"))

    args, kwargs = backend.call_args
    assert args == ("PUT", "https://backend.example.test/api/incidents/17")
    assert kwargs["json"] == {"title": "Nuevo título"}


def test_status_transition_uses_dedicated_patch_and_maps_business_error(
    backend, incident,
):
    backend.return_value = response(200, incident.model_dump(mode="json"))
    transition_incident(IncidentTransitionInput(
        incident_id=17, status="in_progress",
    ))
    args, kwargs = backend.call_args
    assert args == (
        "PATCH", "https://backend.example.test/api/incidents/17/status",
    )
    assert kwargs["json"] == {"status": "in_progress"}

    backend.return_value = response(400)
    with pytest.raises(BackendFailure) as error:
        transition_incident(IncidentTransitionInput(
            incident_id=17, status="resolved",
        ))
    assert error.value.code == "INVALID_STATUS_TRANSITION"


def test_inventory_uses_get_only_and_searches_name_or_sku(backend, product):
    backend.return_value = response(200, [
        product.model_dump(mode="json"),
        product.model_copy(update={"sku": "OTHER"}).model_dump(mode="json"),
    ])
    result = get_products(InventoryGetInput(search="nxv-it-003"))

    assert [item.sku for item in result] == ["NXV-IT-003"]
    assert backend.call_args.args == (
        "GET", "https://backend.example.test/inventory/products",
    )
    assert backend.call_args.kwargs["headers"] == {}

    backend.return_value = response(200, product.model_dump(mode="json"))
    assert get_products(InventoryGetInput(product_id=3)) == [product]
    assert backend.call_args.args == (
        "GET", "https://backend.example.test/inventory/products/3",
    )


def test_backend_timeout_and_invalid_json_are_distinct(backend):
    backend.side_effect = requests.Timeout()
    with pytest.raises(BackendFailure) as error:
        get_products(InventoryGetInput(product_id=3))
    assert error.value.code == "UPSTREAM_TIMEOUT"

    backend.side_effect = None
    invalid = response(200)
    invalid.json.side_effect = ValueError("invalid")
    backend.return_value = invalid
    with pytest.raises(BackendFailure) as error:
        get_products(InventoryGetInput(product_id=3))
    assert error.value.code == "INVALID_UPSTREAM_RESPONSE"


def test_upstream_server_error_and_missing_stock_are_not_success(backend, product):
    backend.return_value = response(503)
    with pytest.raises(BackendFailure) as error:
        get_products(InventoryGetInput(product_id=3))
    assert error.value.code == "UPSTREAM_ERROR"

    incomplete = product.model_dump(mode="json")
    del incomplete["current_stock"]
    backend.return_value = response(200, incomplete)
    with pytest.raises(BackendFailure) as error:
        get_products(InventoryGetInput(product_id=3))
    assert error.value.code == "INVALID_UPSTREAM_RESPONSE"

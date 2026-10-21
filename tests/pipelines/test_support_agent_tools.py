from __future__ import annotations

import math
import os
from unittest.mock import Mock
from uuid import uuid4

import pytest
import requests

from services.agent.tools import (
    TOOL_TIMEOUT,
    IncidentQuery,
    InventoryQuery,
    query_incidents,
    query_inventory,
)
from services.api.incidents.models import IncidentOut
from services.api.inventory.models import AssetResponse


@pytest.fixture
def http_get(monkeypatch):
    response = Mock(status_code=200)
    response.__enter__ = Mock(return_value=response)
    response.__exit__ = Mock(return_value=False)
    get = Mock(return_value=response)
    monkeypatch.setattr("services.agent.tools.requests.get", get)
    monkeypatch.setenv("SUPPORT_AGENT_BACKEND_URL", "http://backend:8000")
    monkeypatch.setenv("SUPPORT_AGENT_SERVICE_TOKEN", str(uuid4()))
    return get


@pytest.fixture
def incident():
    return IncidentOut(
        id=17, title="Consulta de prueba", status="in_progress",
        category="technical_failure", origin="internal", branch="central",
        ticket_id="TKT-017", created_at="2026-10-21T09:00:00Z",
        updated_at="2026-10-21T10:00:00Z",
    ).model_dump(mode="json")


@pytest.fixture
def product():
    return AssetResponse(
        id=3, name="Equipo de prueba", sku="NXV-IT-003",
        category="hardware", office="Valencia", currency="EUR", current_stock=8,
    ).model_dump(mode="json")


def test_incident_detail_uses_real_schema_get_auth_and_finite_timeout(
    http_get, incident,
):
    http_get.return_value.json.return_value = incident
    result = query_incidents(IncidentQuery(incident_id=17))

    assert result.status == "success"
    assert result.incidents[0] == IncidentOut.model_validate(incident)
    assert 0 < TOOL_TIMEOUT == 4.0 and math.isfinite(TOOL_TIMEOUT)
    http_get.assert_called_once_with(
        "http://backend:8000/api/incidents/17",
        headers={"Authorization": f"Bearer {os.environ['SUPPORT_AGENT_SERVICE_TOKEN']}"},
        timeout=4.0, allow_redirects=False,
    )


def test_incident_filters_and_external_ticket_id(http_get, incident):
    http_get.return_value.json.return_value = [incident]
    result = query_incidents(IncidentQuery(
        ticket_id="TKT-017", status="in_progress", branch="central",
    ))
    assert result.status == "success"
    assert result.incidents[0].ticket_id == "TKT-017"
    assert http_get.call_args.args[0] == (
        "http://backend:8000/api/incidents?status=in_progress&branch=central"
    )
    assert query_incidents(IncidentQuery(ticket_id="TKT-018")).status == "not_found"


def test_incident_detail_applies_filters_too(http_get, incident):
    http_get.return_value.json.return_value = incident
    assert query_incidents(
        IncidentQuery(incident_id=17, origin="customer"),
    ).status == "not_found"


@pytest.mark.parametrize("tool,query", [
    (query_incidents, IncidentQuery(incident_id=17)),
    (query_inventory, InventoryQuery(product_id=3)),
])
@pytest.mark.parametrize("failure,error", [
    (requests.Timeout(), "timeout"),
    (requests.ConnectionError(), "service_error"),
])
def test_transport_failures_are_explicit(http_get, tool, query, failure, error):
    http_get.side_effect = failure
    result = tool(query)
    assert result.status == "failed"
    assert result.error == error
    assert not getattr(result, "incidents", getattr(result, "products", []))
    assert http_get.call_args.kwargs["timeout"] == 4.0


@pytest.mark.parametrize("tool,detail,listing", [
    (query_incidents, IncidentQuery(incident_id=17), IncidentQuery()),
    (query_inventory, InventoryQuery(product_id=3), InventoryQuery()),
])
def test_not_found_empty_and_service_error_are_distinct(
    http_get, tool, detail, listing,
):
    response = http_get.return_value
    response.status_code = 404
    assert tool(detail).status == "not_found"
    assert tool(listing).status == "failed"
    response.status_code = 200
    response.json.return_value = []
    assert tool(listing).status == "not_found"
    for status in (301, 401, 403, 500):
        response.status_code = status
        result = tool(detail)
        assert result.status == "failed"
        assert result.error == "service_error"


@pytest.mark.parametrize("tool,query", [
    (query_incidents, IncidentQuery()),
    (query_inventory, InventoryQuery()),
])
def test_invalid_contract_is_not_success(http_get, tool, query):
    http_get.return_value.json.return_value = {"unexpected": "shape"}
    result = tool(query)
    assert result.status == "failed"
    assert result.error == "invalid_response"


def test_missing_auth_does_not_issue_request(http_get, monkeypatch):
    monkeypatch.delenv("SUPPORT_AGENT_SERVICE_TOKEN")
    result = query_incidents(IncidentQuery())
    assert result.status == "failed"
    assert result.error == "not_configured"
    http_get.assert_not_called()


def test_inventory_real_schema_without_auth_and_local_search(http_get, product):
    http_get.return_value.json.return_value = [product]
    result = query_inventory(InventoryQuery(search="NXV-IT-003"))
    assert result.status == "success"
    assert result.products[0].current_stock == 8
    http_get.assert_called_once_with(
        "http://backend:8000/inventory/products", headers={},
        timeout=4.0, allow_redirects=False,
    )
    assert query_inventory(InventoryQuery(search="missing")).status == "not_found"


def test_inventory_detail_contract(http_get, product):
    http_get.return_value.json.return_value = product
    result = query_inventory(InventoryQuery(product_id=3))
    assert result.products[0] == AssetResponse.model_validate(product)
    assert http_get.call_args.args[0].endswith("/inventory/products/3")

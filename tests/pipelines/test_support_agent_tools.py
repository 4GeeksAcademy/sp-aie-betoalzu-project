from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import Mock

import httpx
import pytest

from services.agent.mcp_tools import query_incidents, query_inventory
from services.agent.tools import IncidentQuery, InventoryQuery
from services.api.incidents.models import IncidentOut
from services.api.inventory.models import AssetResponse


@pytest.fixture
def incident():
    return IncidentOut(
        id=17,
        title="Consulta de prueba",
        status="in_progress",
        category="technical_failure",
        origin="internal",
        branch="central",
        ticket_id="TKT-017",
        created_at="2026-10-21T09:00:00Z",
        updated_at="2026-10-21T10:00:00Z",
    ).model_dump(mode="json")


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
    ).model_dump(mode="json")


def install_fake_client(monkeypatch, *, payload=None, error=None, tool_name=None):
    calls = {}
    name = tool_name

    class FakeTool:
        def __init__(self):
            self.name = name

        async def ainvoke(self, arguments):
            calls["arguments"] = arguments
            if error is not None:
                raise error
            return (
                json.dumps(payload),
                SimpleNamespace(structured_content=payload),
            )

    class FakeClient:
        def __init__(self, connections, **kwargs):
            calls["connections"] = connections
            calls["client_options"] = kwargs

        async def get_tools(self, *, server_name):
            calls["server_name"] = server_name
            return [FakeTool()]

    monkeypatch.setattr(
        "services.agent.mcp_tools.MultiServerMCPClient",
        FakeClient,
    )
    monkeypatch.setenv("SUPPORT_AGENT_MCP_URL", "https://mcp.example.test/mcp")
    monkeypatch.setenv("SUPPORT_AGENT_MCP_ACCESS_TOKEN", "dummy-access-token")
    return calls


def test_incident_queries_use_mcp_adapter_and_oauth_access_token(
    monkeypatch, incident,
):
    calls = install_fake_client(
        monkeypatch,
        payload={"status": "success", "incidents": [incident]},
        tool_name="incidents_get",
    )
    result = query_incidents(IncidentQuery(incident_id=17))

    assert result.status == "success"
    assert result.incidents[0].id == 17
    assert calls["server_name"] == "nexova"
    assert calls["arguments"] == {"incident_id": 17}
    connection = calls["connections"]["nexova"]
    assert connection["transport"] == "streamable_http"
    assert connection["url"] == "https://mcp.example.test/mcp"
    assert connection["headers"] == {
        "Authorization": "Bearer dummy-access-token",
    }
    assert connection["timeout"] == 4.0
    assert calls["client_options"] == {
        "tool_name_prefix": False,
        "handle_tool_errors": False,
    }


def test_ticket_filter_and_product_results_are_passed_through_mcp(
    monkeypatch, incident, product,
):
    calls = install_fake_client(
        monkeypatch,
        payload={"status": "success", "incidents": [incident]},
        tool_name="incidents_get",
    )
    result = query_incidents(IncidentQuery(ticket_id="TKT-017"))
    assert result.incidents[0].ticket_id == "TKT-017"
    assert calls["arguments"] == {"ticket_id": "TKT-017"}

    calls = install_fake_client(
        monkeypatch,
        payload={"status": "success", "products": [product]},
        tool_name="inventory_get_products",
    )
    result = query_inventory(InventoryQuery(search="NXV-IT-003"))
    assert result.status == "success"
    assert result.products[0].current_stock == 8
    assert calls["arguments"] == {"search": "NXV-IT-003"}


def test_not_found_and_invalid_stock_are_distinct(monkeypatch, product):
    install_fake_client(
        monkeypatch,
        payload={"error_code": "PRODUCT_NOT_FOUND", "message": "No product."},
        tool_name="inventory_get_products",
    )
    assert query_inventory(InventoryQuery(product_id=99)).status == "not_found"

    del product["current_stock"]
    install_fake_client(
        monkeypatch,
        payload={"status": "success", "products": [product]},
        tool_name="inventory_get_products",
    )
    result = query_inventory(InventoryQuery(product_id=3))
    assert result.status == "failed"
    assert result.error == "invalid_response"


@pytest.mark.parametrize(
    "error,expected",
    [
        (TimeoutError(), "timeout"),
        (
            httpx.HTTPStatusError(
                "unauthorized",
                request=httpx.Request("POST", "https://mcp.example.test/mcp"),
                response=httpx.Response(
                    401,
                    request=httpx.Request("POST", "https://mcp.example.test/mcp"),
                ),
            ),
            "authentication_failed",
        ),
        (
            httpx.HTTPStatusError(
                "forbidden",
                request=httpx.Request("POST", "https://mcp.example.test/mcp"),
                response=httpx.Response(
                    403,
                    request=httpx.Request("POST", "https://mcp.example.test/mcp"),
                ),
            ),
            "authorization_failed",
        ),
        (
            httpx.HTTPStatusError(
                "upstream failure",
                request=httpx.Request("POST", "https://mcp.example.test/mcp"),
                response=httpx.Response(
                    503,
                    request=httpx.Request("POST", "https://mcp.example.test/mcp"),
                ),
            ),
            "service_error",
        ),
    ],
)
def test_mcp_failures_are_reported_without_backend_fallback(
    monkeypatch, error, expected,
):
    install_fake_client(
        monkeypatch,
        error=error,
        tool_name="incidents_get",
    )
    backend_request = Mock(side_effect=AssertionError("direct backend fallback"))
    monkeypatch.setattr("requests.get", backend_request)

    result = query_incidents(IncidentQuery(incident_id=17))

    assert result.status == "failed"
    assert result.error == expected
    backend_request.assert_not_called()


def test_missing_mcp_configuration_or_invalid_tool_result_fails_explicitly(
    monkeypatch,
):
    client = Mock(side_effect=AssertionError("MCP must not start without config"))
    monkeypatch.setattr("services.agent.mcp_tools.MultiServerMCPClient", client)
    monkeypatch.delenv("SUPPORT_AGENT_MCP_URL", raising=False)
    monkeypatch.delenv("SUPPORT_AGENT_MCP_ACCESS_TOKEN", raising=False)
    result = query_incidents(IncidentQuery(incident_id=17))
    assert result.status == "failed"
    assert result.error == "not_configured"
    client.assert_not_called()

    install_fake_client(
        monkeypatch,
        payload="not a valid tool response",
        tool_name="incidents_get",
    )
    result = query_incidents(IncidentQuery(incident_id=17))
    assert result.status == "failed"
    assert result.error == "invalid_response"

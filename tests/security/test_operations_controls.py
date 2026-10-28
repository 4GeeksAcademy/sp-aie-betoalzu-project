from unittest.mock import Mock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError

from mcps.backend import BackendFailure, IncidentTransitionInput, transition_incident
from services.agent.routes import agent_api
from services.api.incidents import services as incident_services
from services.api.incidents.models import IncidentCreate, IncidentStatusUpdate
from services.api.incidents.routes import incidents_api
from services.api.inventory import routes as inventory_routes
from services.api.users.auth import get_current_user
from services.api.users.models import Role, UserInDB
from services.cache import backend_cache


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(inventory_routes.inventory_api)
    app.include_router(incidents_api)
    app.include_router(agent_api)
    with TestClient(app) as test_client:
        yield test_client


def authenticate(client, role):
    user = UserInDB(
        id=1,
        email="operator@example.test",
        hashed_password="synthetic-unused-hash",
        is_active=True,
        role=role,
        created_at="2026-10-28T00:00:00Z",
    )
    client.app.dependency_overrides[get_current_user] = lambda: user


@pytest.mark.parametrize("method,path,payload", [
    ("GET", "/inventory/products", None),
    ("GET", "/inventory/orders", None),
    ("PUT", "/inventory/products/1", {"name": "Synthetic asset"}),
    ("GET", "/api/incidents", None),
    ("GET", "/agent/guardrails/summary", None),
])
def test_anonymous_access_is_denied(client, method, path, payload):
    assert client.request(method, path, json=payload).status_code == 401


@pytest.mark.parametrize("method,path,payload", [
    ("PUT", "/inventory/products/1", {"name": "Synthetic asset"}),
    ("GET", "/api/incidents", None),
    ("GET", "/api/incidents/summary", None),
    ("GET", "/api/incidents/1", None),
    ("GET", "/agent/guardrails/summary", None),
    ("POST", "/agent/query", {"question": "Consulta de tickets"}),
])
def test_regular_user_cannot_access_operations(client, method, path, payload):
    authenticate(client, Role.USER)
    assert client.request(method, path, json=payload).status_code == 403


@pytest.mark.parametrize("role", [Role.ADMIN, Role.MANAGER])
def test_operator_can_update_inventory(client, monkeypatch, role):
    authenticate(client, role)
    asset = Mock()
    asset.model_dump.return_value = {"id": 1, "name": "Synthetic asset"}
    update = Mock(return_value=asset)
    monkeypatch.setattr(inventory_routes, "update_asset", update)

    response = client.put("/inventory/products/1", json={"name": "Synthetic asset"})

    assert response.status_code == 200
    update.assert_called_once()


@pytest.fixture
def pending_incident(tmp_path, monkeypatch):
    monkeypatch.setattr(
        incident_services, "_INCIDENTS_DB_PATH", tmp_path / "incidents.json",
    )
    backend_cache.clear()
    incident = incident_services.create_incident(IncidentCreate(
        title="Synthetic complaint",
        category="client_complaint",
        origin="customer",
    ))
    incident_services.update_incident_status(
        incident.id, IncidentStatusUpdate(status="in_progress"),
    )
    yield incident.id
    backend_cache.clear()


def test_resolution_requires_explicit_confirmation_and_records_actor(
    client, pending_incident,
):
    authenticate(client, Role.MANAGER)
    path = f"/api/incidents/{pending_incident}/status"

    assert client.patch(path, json={"status": "resolved"}).status_code == 400
    assert client.patch(path, json={
        "status": "resolved", "confirm_resolution": "true",
    }).status_code == 422
    assert incident_services.get_incident(pending_incident).status == "in_progress"

    response = client.patch(path, json={
        "status": "resolved", "confirm_resolution": True,
    })

    assert response.status_code == 200
    persisted = incident_services.get_incident(pending_incident)
    assert persisted.status == "resolved"
    assert persisted.resolved_by == "1"
    assert persisted.resolution_confirmed_at


def test_resolution_cannot_bypass_confirmation_at_service_layer(pending_incident):
    with pytest.raises(ValueError, match="human confirmation"):
        incident_services.update_incident_status(
            pending_incident,
            IncidentStatusUpdate(status="resolved", confirm_resolution=True),
        )


@pytest.mark.parametrize("status", ["in_progress", "resolved", "discarded"])
def test_new_incident_cannot_bypass_workflow(status):
    with pytest.raises(ValidationError):
        IncidentCreate(
            title="Synthetic incident", category="other", origin="internal",
            status=status,
        )


def test_mcp_cannot_resolve_even_with_write_scope(monkeypatch):
    request = Mock(side_effect=AssertionError("MCP resolution must not call HTTP"))
    monkeypatch.setattr("mcps.backend.requests.request", request)

    with pytest.raises(BackendFailure) as error:
        transition_incident(IncidentTransitionInput(incident_id=1, status="resolved"))

    assert error.value.code == "HUMAN_CONFIRMATION_REQUIRED"
    request.assert_not_called()

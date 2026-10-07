"""Contract tests for the /knowledge FastAPI router.

Uses TestClient with mocked auth and RAG pipeline so no
real credentials, Qdrant or LLM are required.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from server import app


def _make_user(*, role_value: str = "admin") -> SimpleNamespace:
    """Build a minimal user stub that satisfies FastAPI auth dependencies.

    ``current_user.role.value`` must return the role string; the real
    ``UserInDB.role`` is an Enum, so we use a nested SimpleNamespace to
    emulate the ``.value`` attribute access.
    """
    return SimpleNamespace(
        is_active=True,
        role=SimpleNamespace(value=role_value),
    )


ADMIN_USER = _make_user(role_value="admin")
NORMAL_USER = _make_user(role_value="user")


def _override_get_current_user():
    return NORMAL_USER


def _override_get_admin_user():
    return ADMIN_USER


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture
def auth_client(client: TestClient) -> TestClient:
    """Override auth to return a normal authenticated user."""
    app.dependency_overrides.clear()
    # We patch the auth dependency globally
    from services.api.users.auth import get_current_user

    app.dependency_overrides[get_current_user] = lambda: NORMAL_USER
    yield client
    app.dependency_overrides.clear()


@pytest.fixture
def admin_client(client: TestClient) -> TestClient:
    """Override auth to return an admin user."""
    app.dependency_overrides.clear()
    from services.api.users.auth import get_admin_user, get_current_user

    app.dependency_overrides[get_current_user] = lambda: ADMIN_USER
    app.dependency_overrides[get_admin_user] = lambda: ADMIN_USER
    yield client
    app.dependency_overrides.clear()


# ── POST /knowledge/query ────────────────────────────────────────────────

class TestQueryEndpoint:
    def test_query_returns_answer(self, auth_client: TestClient) -> None:
        with patch("services.api.knowledge.routes.rag_query", return_value="Respuesta simulada."):
            resp = auth_client.post("/knowledge/query", json={"question": "¿Cuál es la tarifa?"})

        assert resp.status_code == 200
        body = resp.json()
        assert "answer" in body
        assert body["answer"] == "Respuesta simulada."

    def test_query_rejects_empty_question(self, auth_client: TestClient) -> None:
        resp = auth_client.post("/knowledge/query", json={"question": ""})

        assert resp.status_code == 422  # Validation error

    def test_query_rejects_too_long_question(self, auth_client: TestClient) -> None:
        resp = auth_client.post("/knowledge/query", json={"question": "¿" * 2001})

        assert resp.status_code == 422

    def test_query_requires_auth(self, client: TestClient) -> None:
        resp = client.post("/knowledge/query", json={"question": "¿Hola?"})

        assert resp.status_code == 401

    def test_query_returns_502_on_runtime_error(self, auth_client: TestClient) -> None:
        with patch(
            "services.api.knowledge.routes.rag_query",
            side_effect=RuntimeError("LLM unavailable"),
        ):
            resp = auth_client.post("/knowledge/query", json={"question": "¿Precio?"})

        assert resp.status_code == 502


# ── POST /knowledge/index ────────────────────────────────────────────────

class TestIndexEndpoint:
    def test_index_requires_admin(self, auth_client: TestClient) -> None:
        """Normal user should get 403."""
        resp = auth_client.post("/knowledge/index")

        assert resp.status_code == 403

    def test_index_returns_status(self, admin_client: TestClient) -> None:
        with patch(
            "services.api.knowledge.routes.index_setup",
            return_value={"nexova-pricing-model": 4, "nexova-service-lines": 3},
        ):
            resp = admin_client.post("/knowledge/index")

        assert resp.status_code == 201
        body = resp.json()
        assert body["status"] == "ok"
        assert body["indexed"]["nexova-pricing-model"] == 4

    def test_index_requires_auth(self, client: TestClient) -> None:
        resp = client.post("/knowledge/index")

        assert resp.status_code == 401
from unittest.mock import Mock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from services.api.users import routes
from services.api.users.models import Role, UserInDB


@pytest.fixture
def client(monkeypatch):
    user = UserInDB(
        id=1,
        email="operator@example.com",
        hashed_password="synthetic-unused-hash",
        is_active=True,
        role=Role.USER,
        created_at="2026-10-28T00:00:00Z",
    )
    monkeypatch.setattr(routes, "get_user_by_email", Mock(return_value=user))
    monkeypatch.setattr(routes, "verify_password", Mock(return_value=True))
    monkeypatch.setattr(routes, "create_access_token", Mock(return_value="synthetic-token"))
    app = FastAPI()
    app.include_router(routes.users_api)
    with TestClient(app) as test_client:
        yield test_client


def test_login_accepts_json_without_credentials_in_url(client):
    response = client.post("/login", json={
        "email": "operator@example.com", "password": "synthetic-password",
    })

    assert response.status_code == 200
    assert response.json() == {
        "access_token": "synthetic-token", "token_type": "bearer",
    }
    assert response.request.url.query == b""
    routes.verify_password.assert_called_once_with(
        "synthetic-password", "synthetic-unused-hash",
    )


def test_query_only_credentials_are_not_accepted(client):
    response = client.post("/login", params={
        "email": "operator@example.com", "password": "synthetic-password",
    })

    assert response.status_code == 422
    routes.get_user_by_email.assert_not_called()


@pytest.mark.parametrize("registered,password_valid,active,expected", [
    (False, True, True, 401),
    (True, False, True, 401),
    (True, True, False, 403),
])
def test_login_preserves_authentication_failures(
    client, registered, password_valid, active, expected,
):
    if not registered:
        routes.get_user_by_email.return_value = None
    elif not active:
        routes.get_user_by_email.return_value.is_active = False
    routes.verify_password.return_value = password_valid

    response = client.post("/login", json={
        "email": "operator@example.com", "password": "synthetic-password",
    })

    assert response.status_code == expected
    assert "access_token" not in response.json()

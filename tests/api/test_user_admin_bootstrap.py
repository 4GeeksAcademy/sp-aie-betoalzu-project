from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("SECRET_KEY", "test-secret")

from fastapi import FastAPI
from fastapi.testclient import TestClient

from services.api.users import routes
from services.api.users.routes import users_api
from services.api.users.services import get_user_by_email


def _client(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(
        "services.api.users.services._USERS_DB_PATH",
        tmp_path / "users.json",
    )
    monkeypatch.setattr(
        routes,
        "ADMIN_BOOTSTRAP_LOCK",
        tmp_path / "admin-bootstrap.lock",
    )
    app = FastAPI()
    app.include_router(users_api)
    return TestClient(app)


def test_public_registration_cannot_self_assign_admin_role(monkeypatch, tmp_path):
    client = _client(monkeypatch, tmp_path)
    response = client.post(
        "/users",
        json={
            "email": "self-promoted@example.com",
            "password": "long-enough-password",
            "role": "admin",
            "profile": {"name": "Javier Almeida"},
        },
    )

    assert response.status_code == 201
    assert response.json()["role"] == "user"
    stored = get_user_by_email("self-promoted@example.com")
    assert stored is not None
    assert stored.role.value == "user"


def test_admin_bootstrap_is_secret_protected_and_one_time(
    monkeypatch, tmp_path
):
    client = _client(monkeypatch, tmp_path)
    secret = "bootstrap-secret-for-tests"
    monkeypatch.setattr(routes, "ADMIN_BOOTSTRAP_TOKEN", secret)
    payload = {
        "token": secret,
        "email": "initial-admin@example.com",
        "password": "long-enough-password",
        "profile": {"name": "Operations Admin"},
    }

    rejected = client.post(
        "/auth/bootstrap-admin",
        json={**payload, "token": "incorrect"},
    )
    assert rejected.status_code == 401

    created = client.post("/auth/bootstrap-admin", json=payload)
    assert created.status_code == 201
    assert created.json()["role"] == "admin"
    assert secret not in created.text

    repeated = client.post("/auth/bootstrap-admin", json=payload)
    assert repeated.status_code == 409
    assert (tmp_path / "admin-bootstrap.lock").exists()
    assert secret not in (tmp_path / "admin-bootstrap.lock").read_text(
        errors="ignore"
    )

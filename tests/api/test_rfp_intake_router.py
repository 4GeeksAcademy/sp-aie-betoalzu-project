from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

os.environ.setdefault("SECRET_KEY", "test-secret")

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from data_project.pipelines.rfp_intake.graph import RfpIntakeError
from services import database
from services.api.rfp_intake import routes
from services.api.rfp_intake.models import RfpTicket
from services.api.rfp_intake.routes import rfp_intake_api
from services.api.users.auth import get_current_user

USER = SimpleNamespace(id=101, role=SimpleNamespace(value="user"))


def _successful_result(ticket_id: str) -> dict:
    handoff = {
        "schema_version": "1.0",
        "ticket_id": ticket_id,
        "metadata": {"client_name": "Cliente de prueba"},
        "active_workstreams": [],
        "key_aspects": {},
        "open_questions": [],
        "summary": "Listo para Ventas.",
    }
    return {
        "status": "analisis_completo",
        "classification": {
            "is_rfp": True,
            "reason": "Solicita una propuesta.",
            "evidence": "Buscamos una propuesta.",
        },
        "metadata": {
            "client_name": "Cliente de prueba",
            "client_hq": "España",
            "services_requested": ["búsqueda"],
            "service_types": ["headhunting"],
            "scope": "Cinco posiciones",
            "deadline": None,
            "budget_range": None,
            "currency": "EUR",
            "departments_needed": ["seleccion"],
            "department_extracts": {"seleccion": "Cinco posiciones"},
            "explicitly_requests_recruitment": False,
            "open_questions": ["Falta presupuesto."],
            "field_evidence": {"scope": "Cinco posiciones"},
            "readability_metrics": {
                "word_count": 4,
                "sentence_count": 1,
                "unit": "count",
                "limitation": "heuristic",
            },
        },
        "sections": [
            {
                "department_id": "seleccion",
                "contact": "Javier Almeida",
                "key_aspects": [
                    {"aspect": "Volumen", "value": "Cinco posiciones", "evidence": "Cinco"}
                ],
                "open_questions": [],
            }
        ],
        "handoff": handoff,
    }


def _install_pipeline(monkeypatch, outcomes: list[object]) -> None:
    def run(_pdf_path: str, ticket_id: str) -> dict:
        outcome = outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        result = dict(outcome)
        result["handoff"] = {**result["handoff"], "ticket_id": ticket_id}
        return result

    monkeypatch.setattr(
        "data_project.pipelines.rfp_intake.run_rfp_intake",
        run,
    )


def _client_fixture(tmp_path, monkeypatch) -> TestClient:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    monkeypatch.setattr(database, "engine", engine)
    SQLModel.metadata.create_all(engine)
    monkeypatch.setattr(routes, "RAW_DIR", tmp_path / "raw")

    app = FastAPI()
    app.include_router(rfp_intake_api)
    app.dependency_overrides[get_current_user] = lambda: USER

    def override_database():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[database.get_db] = override_database
    return TestClient(app)


def _upload(client: TestClient, name: str = "request.pdf", content: bytes = b"%PDF-1.7\ntext"):
    return client.post(
        "/rfp-intake/tickets",
        files={"file": (name, content, "application/pdf")},
    )


def test_upload_persists_analysis_and_handoff_transactionally(tmp_path, monkeypatch):
    client = _client_fixture(tmp_path, monkeypatch)
    _install_pipeline(monkeypatch, [_successful_result("ignored")])

    response = _upload(client)

    assert response.status_code == 202
    ticket_id = response.json()["ticket_id"]
    assert response.json()["status"] == "analizando"

    detail = client.get(f"/rfp-intake/tickets/{ticket_id}")
    assert detail.status_code == 200
    data = detail.json()
    assert data["status"] == "analisis_completo"
    assert data["metadata"]["currency"] == "EUR"
    assert data["sections"][0]["department_id"] == "seleccion"
    assert data["handoff"]["schema_version"] == "1.0"
    assert data["handoff"]["ticket_id"] == ticket_id

    pdf_path = routes.RAW_DIR / f"{ticket_id}.pdf"
    assert pdf_path.read_bytes().startswith(b"%PDF-")
    assert pdf_path.stat().st_mode & 0o777 == 0o600


def test_processing_failure_is_visible_and_retryable_without_duplicate_rows(
    tmp_path, monkeypatch
):
    client = _client_fixture(tmp_path, monkeypatch)
    _install_pipeline(
        monkeypatch,
        [RfpIntakeError("private document content"), _successful_result("ignored")],
    )

    response = _upload(client)
    ticket_id = response.json()["ticket_id"]
    failed = client.get(f"/rfp-intake/tickets/{ticket_id}").json()
    assert failed["status"] == "analizando"
    assert failed["retry_available"] is True
    assert "private document content" not in failed["processing_error"]

    retry = client.post(f"/rfp-intake/tickets/{ticket_id}/retry")
    assert retry.status_code == 202
    complete = client.get(f"/rfp-intake/tickets/{ticket_id}").json()
    assert complete["status"] == "analisis_completo"
    assert complete["retry_count"] == 1
    assert len(complete["sections"]) == 1


def test_upload_rejects_non_pdf_and_oversized_content(tmp_path, monkeypatch):
    client = _client_fixture(tmp_path, monkeypatch)
    invalid_type = client.post(
        "/rfp-intake/tickets",
        files={"file": ("request.txt", b"%PDF-1.7", "text/plain")},
    )
    assert invalid_type.status_code == 415

    monkeypatch.setattr(routes, "MAX_UPLOAD_BYTES", 8)
    too_large = _upload(client, content=b"%PDF-1.7" + b"x")
    assert too_large.status_code == 413


def test_ticket_is_not_visible_to_another_user(tmp_path, monkeypatch):
    client = _client_fixture(tmp_path, monkeypatch)
    _install_pipeline(monkeypatch, [_successful_result("ignored")])
    ticket_id = _upload(client).json()["ticket_id"]

    app = client.app
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=202)
    response = client.get(f"/rfp-intake/tickets/{ticket_id}")
    assert response.status_code == 404


def test_stale_analysis_becomes_recoverable(tmp_path, monkeypatch):
    client = _client_fixture(tmp_path, monkeypatch)
    ticket = RfpTicket(
        ticket_id="8f996eda-0de9-49ae-93a4-3147ad375a6a",
        rfp_id="e7941798-6a47-45fa-a95a-063289b66f48",
        raw_pdf_path=str(tmp_path / "raw" / "stale.pdf"),
        created_by=str(USER.id),
        processing_started_at=datetime.now(UTC) - timedelta(hours=1),
    )
    ticket_id = ticket.ticket_id
    with Session(database.engine) as session:
        session.add(ticket)
        session.commit()

    detail = client.get(f"/rfp-intake/tickets/{ticket_id}").json()
    assert detail["retry_available"] is True
    assert "interrumpió" in detail["processing_error"]

from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

os.environ.setdefault("SECRET_KEY", "test-secret")

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from data_project.pipelines.rfp_intake import responses
from data_project.pipelines.rfp_intake.graph import RfpIntakeError
from services import database
from services.api.rfp_intake import routes
from services.api.rfp_intake.models import RfpTicket
from services.api.rfp_intake.routes import rfp_intake_api
from services.api.users.auth import get_current_user

USER = SimpleNamespace(id=101, role=SimpleNamespace(value="user"))


def _successful_result(ticket_id: str) -> dict:
    key_aspects = [
        {"aspect": "Volumen", "value": "Cinco posiciones", "evidence": "Cinco"}
    ]
    handoff = {
        "schema_version": "1.0",
        "ticket_id": ticket_id,
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
            "open_questions": ["Falta presupuesto."],
        },
        "active_workstreams": [
            {
                "department_id": "seleccion",
                "contact": "Javier Almeida",
                "key_aspects": key_aspects,
                "open_questions": [],
            }
        ],
        "key_aspects": {"seleccion": key_aspects},
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
                "key_aspects": key_aspects,
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


def _install_response_agents(monkeypatch, fail_relevance_once: bool = False) -> None:
    relevance_failures_remaining = int(fail_relevance_once)

    def invoke(agent_name, _instruction, _payload, _response_model):
        nonlocal relevance_failures_remaining
        if agent_name.startswith("generator_"):
            return responses.DraftOutput(
                draft_content=(
                    "Incluye la garantía de satisfacción de Nexova a 90 días. "
                    "La propuesta se expresa en EUR y estima un cierre en 15 días hábiles."
                )
            )
        if agent_name.startswith("relevance_evaluator_"):
            if relevance_failures_remaining:
                relevance_failures_remaining -= 1
                raise RfpIntakeError("evaluador no disponible")
            return responses.RelevanceResult.model_validate(
                {"pass": True, "missing_aspects": []}
            )
        raise AssertionError(f"Unexpected response agent: {agent_name}")

    monkeypatch.setattr(responses, "_invoke_json_agent", invoke)


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


def test_stale_response_generation_returns_ticket_to_analysis_complete(tmp_path):
    ticket = RfpTicket(
        ticket_id="ed44133c-d904-42f2-a66f-824c591d640b",
        rfp_id="672667b8-8e09-4f15-a5d6-d6764604dbee",
        status="en-evaluación",
        raw_pdf_path=str(tmp_path / "raw" / "stale.pdf"),
        created_by=str(USER.id),
        processing_started_at=datetime.now(UTC) - timedelta(hours=1),
    )

    assert routes._mark_if_stale(ticket) is True
    assert ticket.status == "analisis_completo"
    assert ticket.processing_started_at is None
    assert "interrumpió" in ticket.processing_error


def test_response_generation_persists_evaluation_and_versioned_handoff(
    tmp_path, monkeypatch
):
    client = _client_fixture(tmp_path, monkeypatch)
    _install_pipeline(monkeypatch, [_successful_result("ignored")])
    _install_response_agents(monkeypatch)
    ticket_id = _upload(client).json()["ticket_id"]

    response = client.post(f"/rfp-intake/tickets/{ticket_id}/generate")

    assert response.status_code == 202
    assert response.json()["status"] == "generando_borrador"
    detail_response = client.get(f"/rfp-intake/tickets/{ticket_id}")
    assert detail_response.status_code == 200
    detail = detail_response.json()
    assert detail["status"] == "en-evaluación"
    assert detail["processing_error"] is None
    assert detail["sections"][0]["draft_content"].startswith("Incluye la garantía")
    evaluation = detail["sections"][0]["evaluation_results"]
    assert evaluation["schema_version"] == "1.0"
    assert evaluation["iteration_count"] == 1
    assert evaluation["result"]["overall_pass"] is True
    assert len(evaluation["result"]["draft_sha256"]) == 64
    assert detail["handoff"]["schema_version"] == "2.0"
    workstream = detail["handoff"]["active_workstreams"][0]
    assert workstream["section_status"] == "ready_for_approval"
    assert workstream["draft_content"] == detail["sections"][0]["draft_content"]
    assert workstream["evaluation_result"] == evaluation["result"]
    duplicate = client.post(f"/rfp-intake/tickets/{ticket_id}/generate")
    assert duplicate.status_code == 409


def test_response_technical_failure_can_retry_without_counting_invalid_evaluation(
    tmp_path, monkeypatch
):
    client = _client_fixture(tmp_path, monkeypatch)
    _install_pipeline(monkeypatch, [_successful_result("ignored")])
    _install_response_agents(monkeypatch, fail_relevance_once=True)
    ticket_id = _upload(client).json()["ticket_id"]

    failed_run = client.post(f"/rfp-intake/tickets/{ticket_id}/generate")
    assert failed_run.status_code == 202
    failed = client.get(f"/rfp-intake/tickets/{ticket_id}").json()
    assert failed["status"] == "analisis_completo"
    assert "evaluador no disponible" not in failed["processing_error"]
    assert failed["sections"][0]["draft_content"] is None
    assert failed["sections"][0]["evaluation_results"] is None

    retry = client.post(f"/rfp-intake/tickets/{ticket_id}/generate")
    assert retry.status_code == 202
    completed = client.get(f"/rfp-intake/tickets/{ticket_id}").json()
    assert completed["status"] == "en-evaluación"
    assert completed["sections"][0]["evaluation_results"]["iteration_count"] == 1

from __future__ import annotations

import hashlib
import os
from types import SimpleNamespace

os.environ.setdefault("SECRET_KEY", "test-secret")

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

from services import database
from services.api.rfp_intake import routes
from services.api.rfp_intake.models import (
    RfpApprovalBranch,
    RfpApprovalDecision,
    RfpDepartmentSection,
    RfpFinalDocument,
    RfpHandoff,
    RfpMetadataRecord,
    RfpTicket,
)
from services.api.rfp_intake.routes import rfp_intake_api
from services.api.users.auth import get_current_user

TICKET_ID = "8f996eda-0de9-49ae-93a4-3147ad375a6a"


def _user(name: str = "Javier Almeida", role: str = "user"):
    return SimpleNamespace(
        id=101,
        email="reviewer@nexova.test",
        role=SimpleNamespace(value=role),
        profile={"name": name},
    )


def _client(tmp_path, monkeypatch, user=None):
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    monkeypatch.setattr(database, "engine", engine)
    SQLModel.metadata.create_all(engine)
    app = FastAPI()
    app.include_router(rfp_intake_api)
    app.dependency_overrides[get_current_user] = lambda: user or _user()

    def override_database():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[database.get_db] = override_database
    return TestClient(app), engine


def _seed_ticket(engine, departments=("seleccion",), iteration_count=1):
    metadata = {
        "client_name": "Cliente de prueba",
        "client_hq": "España",
        "services_requested": ["búsqueda"],
        "service_types": ["headhunting"],
        "scope": "Solicitud de prueba",
        "deadline": None,
        "budget_range": None,
        "currency": "EUR",
        "departments_needed": list(departments),
        "department_extracts": {},
        "explicitly_requests_recruitment": False,
        "open_questions": [],
        "field_evidence": {},
        "readability_metrics": {},
    }
    workstreams = []
    key_aspects = {}
    sections = []
    for department_id in departments:
        draft = (
            "Garantía de satisfacción de Nexova a 90 días. "
            "La propuesta se cotiza en EUR."
        )
        digest = hashlib.sha256(draft.encode()).hexdigest()
        evaluation = {
            "schema_version": "1.0",
            "iteration_count": iteration_count,
            "section_status": "ready_for_approval",
            "result": {
                "section_id": department_id,
                "readability": {"pass": True, "score": 100, "details": "correcta"},
                "relevance": {"pass": True, "missing_aspects": []},
                "compliance": {
                    "pass": True,
                    "rule_ids": ["currency_matches_client_hq"],
                    "violations": [],
                },
                "overall_pass": True,
                "feedback_for_generator": "Sin defectos.",
                "draft_sha256": digest,
            },
        }
        aspects = [{"aspect": "Roles", "value": "Cinco", "evidence": "Cinco"}]
        key_aspects[department_id] = aspects
        workstreams.append(
            {
                "department_id": department_id,
                "contact": "Javier Almeida",
                "key_aspects": aspects,
                "open_questions": [],
                "draft_content": draft,
                "evaluation_results": evaluation,
                "draft_sha256": digest,
                "draft_version": iteration_count,
                "section_status": "ready_for_approval",
            }
        )
        sections.append(
            RfpDepartmentSection(
                ticket_id=TICKET_ID,
                department_id=department_id,
                key_aspects=aspects,
                draft_content=draft,
                evaluation_results=evaluation,
            )
        )
    handoff = {
        "schema_version": "2.0",
        "ticket_id": TICKET_ID,
        "metadata": metadata,
        "active_workstreams": workstreams,
        "key_aspects": key_aspects,
        "open_questions": [],
        "response_generation": {"status": "ready_for_part_3"},
    }
    with Session(engine) as session:
        session.add(
            RfpTicket(
                ticket_id=TICKET_ID,
                rfp_id="e7941798-6a47-45fa-a95a-063289b66f48",
                status="en-evaluación",
                raw_pdf_path="/tmp/test.pdf",
                created_by="101",
            )
        )
        session.add(
            RfpMetadataRecord(
                ticket_id=TICKET_ID,
                client_name=metadata["client_name"],
                client_hq=metadata["client_hq"],
                services_requested=metadata["services_requested"],
                service_types=metadata["service_types"],
                scope=metadata["scope"],
                currency=metadata["currency"],
                departments_needed=metadata["departments_needed"],
            )
        )
        session.add_all(sections)
        session.add(
            RfpHandoff(
                ticket_id=TICKET_ID,
                schema_version="2.0",
                status="ready_for_part_3",
                payload=handoff,
            )
        )
        session.commit()
    return workstreams


def test_independent_approval_branches_and_final_document(tmp_path, monkeypatch):
    client, engine = _client(tmp_path, monkeypatch, _user(role="admin"))
    workstreams = _seed_ticket(engine, ("seleccion", "soporte"))

    started = client.post(f"/rfp-intake/tickets/{TICKET_ID}/approvals/start")
    assert started.status_code == 202
    assert started.json()["status"] == "esperando_aprobación"
    repeated_start = client.post(
        f"/rfp-intake/tickets/{TICKET_ID}/approvals/start"
    )
    assert repeated_start.status_code == 202
    branches = client.get(f"/rfp-intake/tickets/{TICKET_ID}").json()[
        "approval_branches"
    ]
    assert {branch["thread_id"] for branch in branches} == {
        f"rfp-{TICKET_ID}:seleccion",
        f"rfp-{TICKET_ID}:soporte",
    }

    second = workstreams[1]
    response = client.post(
        f"/rfp-intake/tickets/{TICKET_ID}/approvals/soporte/decision",
        json={
            "action": "approve",
            "draft_sha256": second["draft_sha256"],
            "draft_version": second["draft_version"],
        },
    )
    assert response.status_code == 200
    detail = client.get(f"/rfp-intake/tickets/{TICKET_ID}").json()
    branch_states = {item["department_id"]: item["status"] for item in detail["approval_branches"]}
    assert branch_states == {"seleccion": "pending", "soporte": "approved"}
    assert detail["final_document"] is None

    first = workstreams[0]
    approved = client.post(
        f"/rfp-intake/tickets/{TICKET_ID}/approvals/seleccion/decision",
        json={
            "action": "approve",
            "draft_sha256": first["draft_sha256"],
            "draft_version": first["draft_version"],
        },
    )
    assert approved.status_code == 200
    assert approved.json()["ticket"]["status"] == "terminado"
    final_doc = client.get(f"/rfp-intake/tickets/{TICKET_ID}/final-document")
    assert final_doc.status_code == 200
    assert final_doc.headers["content-type"].startswith("application/json")
    assert len(final_doc.json()["sections"]) == 2
    assert len(final_doc.json()["section_digests"]) == 2

    repeated = client.post(
        f"/rfp-intake/tickets/{TICKET_ID}/approvals/seleccion/decision",
        json={
            "action": "approve",
            "draft_sha256": first["draft_sha256"],
            "draft_version": first["draft_version"],
        },
    )
    assert repeated.status_code == 200
    with Session(engine) as session:
        assert len(session.exec(select(RfpApprovalDecision)).all()) == 2
        assert len(session.exec(select(RfpFinalDocument)).all()) == 1


def test_structured_sla_conflict_is_audited_and_reopened_without_llm(
    tmp_path, monkeypatch
):
    client, engine = _client(tmp_path, monkeypatch, _user(role="admin"))
    _seed_ticket(engine, ("soporte",))
    with Session(engine) as session:
        section = session.get(
            RfpDepartmentSection, (TICKET_ID, "soporte")
        )
        handoff = session.get(RfpHandoff, TICKET_ID)
        bundle = {
            **section.evaluation_results,
            "result": {
                **section.evaluation_results["result"],
                "compliance": {
                    "pass": False,
                    "rule_ids": ["outsourced_support_sla_24_hours"],
                    "violations": [
                        "Menciona explícitamente el SLA de respuesta de 24 horas."
                    ],
                    "currencies_mentioned": ["EUR"],
                },
            },
        }
        section.evaluation_results = bundle
        workstreams = [
            {
                **handoff.payload["active_workstreams"][0],
                "evaluation_results": bundle,
            }
        ]
        handoff.payload = {**handoff.payload, "active_workstreams": workstreams}
        session.add(section)
        session.add(handoff)
        session.commit()

    scheduled: list[str] = []
    monkeypatch.setattr(
        routes,
        "process_rfp_response_generation",
        lambda ticket_id: scheduled.append(ticket_id),
    )
    started = client.post(f"/rfp-intake/tickets/{TICKET_ID}/approvals/start")

    assert started.status_code == 202
    assert started.json()["status"] == "generando_borrador"
    assert scheduled == [TICKET_ID]
    detail = client.get(f"/rfp-intake/tickets/{TICKET_ID}").json()
    assert detail["arbitrations"][0]["trigger_id"] == "support-sla-missing"
    assert detail["arbitrations"][0]["arbitrator"] == "Roberto Díaz"
    assert detail["approval_branches"][0]["status"] == "revision_requested"
    assert detail["sections"][0]["evaluation_results"]["section_status"] == "needs_revision"


def test_interrupted_approval_revision_can_be_resumed_by_admin(tmp_path, monkeypatch):
    client, engine = _client(tmp_path, monkeypatch)
    _seed_ticket(engine)
    client.post(f"/rfp-intake/tickets/{TICKET_ID}/approvals/start")
    scheduled: list[str] = []
    monkeypatch.setattr(
        routes,
        "process_rfp_response_generation",
        lambda ticket_id: scheduled.append(ticket_id),
    )
    with Session(engine) as session:
        ticket = session.get(RfpTicket, TICKET_ID)
        section = session.get(RfpDepartmentSection, (TICKET_ID, "seleccion"))
        branch = session.get(RfpApprovalBranch, (TICKET_ID, "seleccion"))
        handoff = session.get(RfpHandoff, TICKET_ID)
        evaluation = {
            **section.evaluation_results,
            "section_status": "needs_revision",
            "result": {
                **section.evaluation_results["result"],
                "overall_pass": False,
                "feedback_for_generator": "Aclarar el alcance.",
            },
        }
        section.evaluation_results = evaluation
        section.approval_status = "revision_requested"
        branch.status = "revision_requested"
        ticket.status = "needs_human_review"
        ticket.processing_error = "La generación se interrumpió."
        ticket.processing_started_at = None
        workstream = {
            **handoff.payload["active_workstreams"][0],
            "evaluation_results": evaluation,
            "section_status": "needs_revision",
        }
        handoff.payload = {
            **handoff.payload,
            "active_workstreams": [workstream],
        }
        session.add_all([ticket, section, branch, handoff])
        session.commit()

    denied = client.post(
        f"/rfp-intake/tickets/{TICKET_ID}/approvals/seleccion/resume"
    )
    assert denied.status_code == 403
    client.app.dependency_overrides[get_current_user] = lambda: _user(role="admin")
    resumed = client.post(
        f"/rfp-intake/tickets/{TICKET_ID}/approvals/seleccion/resume"
    )

    assert resumed.status_code == 202
    assert resumed.json()["status"] == "generando_borrador"
    assert resumed.json()["processing_error"] is None
    assert scheduled == [TICKET_ID]


def test_invalid_or_unauthorized_decision_does_not_change_branch(tmp_path, monkeypatch):
    client, engine = _client(tmp_path, monkeypatch, _user("No autorizado"))
    workstreams = _seed_ticket(engine)
    client.post(f"/rfp-intake/tickets/{TICKET_ID}/approvals/start")
    result = workstreams[0]
    payload = {
        "action": "approve",
        "draft_sha256": result["draft_sha256"],
        "draft_version": result["draft_version"],
    }
    denied = client.post(
        f"/rfp-intake/tickets/{TICKET_ID}/approvals/seleccion/decision",
        json=payload,
    )
    assert denied.status_code == 403
    client.app.dependency_overrides[get_current_user] = lambda: _user(role="admin")
    invalid = client.post(
        f"/rfp-intake/tickets/{TICKET_ID}/approvals/seleccion/decision",
        json={**payload, "draft_sha256": "0" * 64},
    )
    assert invalid.status_code == 409
    detail = client.get(f"/rfp-intake/tickets/{TICKET_ID}").json()
    assert detail["approval_branches"][0]["status"] == "pending"
    assert detail["approval_decisions"] == []


def test_request_changes_requires_comment_and_stops_at_generation_limit(
    tmp_path, monkeypatch
):
    client, engine = _client(tmp_path, monkeypatch, _user(role="admin"))
    workstreams = _seed_ticket(engine, iteration_count=3)
    client.post(f"/rfp-intake/tickets/{TICKET_ID}/approvals/start")
    result = workstreams[0]
    no_comment = client.post(
        f"/rfp-intake/tickets/{TICKET_ID}/approvals/seleccion/decision",
        json={
            "action": "request_changes",
            "draft_sha256": result["draft_sha256"],
            "draft_version": result["draft_version"],
        },
    )
    assert no_comment.status_code == 422
    requested = client.post(
        f"/rfp-intake/tickets/{TICKET_ID}/approvals/seleccion/decision",
        json={
            "action": "request_changes",
            "comment": "Debe aclararse el alcance.",
            "draft_sha256": result["draft_sha256"],
            "draft_version": result["draft_version"],
        },
    )
    assert requested.status_code == 200
    assert requested.json()["ticket"]["status"] == "needs_human_review"
    detail = client.get(f"/rfp-intake/tickets/{TICKET_ID}").json()
    assert detail["sections"][0]["draft_content"] == result["draft_content"]
    assert detail["approval_branches"][0]["status"] == "needs_human_review"

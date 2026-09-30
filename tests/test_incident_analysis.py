from __future__ import annotations

import io
import os
from pathlib import Path
from types import SimpleNamespace

os.environ.setdefault("SECRET_KEY", "test-secret-key-for-incident-analysis")

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.pool import NullPool
from sqlmodel import SQLModel, Session, create_engine, select

from services.api.incident_analyzer import analyze_csv_stream, build_metrics_csv, build_summary
from services.api.incident_analyzer import routes as incident_routes
from services.api.users.auth import get_current_user
from services.api.users.models import Role, UserInDB
from services.incident_analysis import IncidentAnalysisTask
from services.models import IncidentAnalysisDeadLetter, IncidentAnalysisTaskRecord


CSV_CONTENT = (
    "ticket_id,date,client_company,category,description,agent_id,status,customer_email,satisfaction_score\n"
    "T-1,2026-09-01,Acme,TECHNICAL,Network issue,AGT-01,CLOSED,user@example.com,5\n"
)


@pytest.fixture
def test_engine(tmp_path: Path):
    database_engine = create_engine(f"sqlite:///{tmp_path / 'incident-analysis.db'}", poolclass=NullPool)
    SQLModel.metadata.create_all(database_engine)
    return database_engine


@pytest.fixture
def client(test_engine, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    user = UserInDB(
        id=17,
        email="owner@example.com",
        hashed_password="unused",
        is_active=True,
        role=Role.USER,
        created_at="2026-01-01T00:00:00+00:00",
    )
    app = FastAPI()
    app.include_router(incident_routes.incidents_api)
    app.dependency_overrides[get_current_user] = lambda: user
    monkeypatch.setattr(incident_routes, "engine", test_engine)
    monkeypatch.setattr(incident_routes, "UPLOAD_DIR", tmp_path / "uploads")
    with TestClient(app) as test_client:
        yield test_client


def test_csv_analysis_streams_rows_and_exports_serializable_summary():
    analysis = analyze_csv_stream(io.StringIO(CSV_CONTENT), "incidents.csv")
    summary = build_summary(analysis)

    assert summary["total_records"] == 1
    assert summary["valid_records"] == 1
    assert summary["average_score"] == 5.0
    assert "average_score,5.0" in build_metrics_csv(summary)


def test_upload_queues_only_shared_file_reference(client: TestClient, monkeypatch: pytest.MonkeyPatch):
    published = {}

    def publish(task_name, **kwargs):
        published.update(task_name=task_name, **kwargs)

    monkeypatch.setattr(incident_routes.celery_app, "send_task", publish)
    response = client.post(
        "/api/incidents/analyze",
        files={"file": ("incidents.csv", CSV_CONTENT.encode(), "text/csv")},
    )

    assert response.status_code == 202
    task_id = response.json()["task_id"]
    assert published["task_name"] == "services.incident_analysis.analyze_incident_csv"
    assert len(published["args"]) == 1
    reference = published["args"][0]
    assert reference.endswith(".csv")
    assert CSV_CONTENT not in repr(published)
    assert (incident_routes.UPLOAD_DIR / reference).read_text(encoding="utf-8") == CSV_CONTENT
    with Session(incident_routes.engine) as session:
        task = session.get(IncidentAnalysisTaskRecord, task_id)
    assert task is not None and task.owner_id == 17


def test_task_status_uses_celery_state_and_hides_other_owners(client: TestClient, test_engine, monkeypatch):
    task_id = "a" * 36
    with Session(test_engine) as session:
        session.add(
            IncidentAnalysisTaskRecord(
                task_id=task_id,
                owner_id=17,
                source_filename="incidents.csv",
            )
        )
        session.commit()

    monkeypatch.setattr(
        incident_routes,
        "AsyncResult",
        lambda task_id, app: SimpleNamespace(state="STARTED", result=None),
    )
    response = client.get(f"/tasks/{task_id}")
    assert response.json() == {"task_id": task_id, "status": "started", "result": None}

    with Session(test_engine) as session:
        session.add(
            IncidentAnalysisTaskRecord(
                task_id="b" * 36,
                owner_id=99,
                source_filename="private.csv",
            )
        )
        session.commit()
    assert client.get(f"/tasks/{'b' * 36}").status_code == 404


def test_successful_task_result_and_export_use_requested_task_id(client: TestClient, test_engine, monkeypatch):
    task_id = "d" * 36
    summary = {
        "source_file": "incidents.csv",
        "total_records": 1,
        "valid_records": 1,
        "invalid_records": 0,
        "invalid_rules": {
            "missing_client_company": 0,
            "invalid_category": 0,
            "invalid_description": 0,
            "invalid_agent": 0,
            "invalid_status": 0,
            "invalid_email": 0,
            "closed_no_score": 0,
            "score_out_of_range": 0,
        },
        "categories": {"TECHNICAL": 1},
        "statuses": {"CLOSED": 1},
        "scores": {"5": 1},
        "closed_tickets": 1,
        "scored_tickets": 1,
        "average_score": 5.0,
    }
    with Session(test_engine) as session:
        session.add(
            IncidentAnalysisTaskRecord(
                task_id=task_id,
                owner_id=17,
                source_filename="incidents.csv",
            )
        )
        session.commit()

    monkeypatch.setattr(
        incident_routes,
        "AsyncResult",
        lambda task_id, app: SimpleNamespace(state="SUCCESS", result=summary),
    )
    status = client.get(f"/tasks/{task_id}")
    export = client.get(f"/api/incidents/results/export?task_id={task_id}")

    assert status.json() == {"task_id": task_id, "status": "success", "result": summary}
    assert export.status_code == 200
    assert "incidents-metrics.csv" in export.headers["content-disposition"]
    assert "average_score,5.0" in export.text


def test_terminal_failure_writes_idempotent_dlq_with_fourth_attempt(test_engine, monkeypatch):
    import services.incident_analysis as analysis_tasks

    monkeypatch.setattr(analysis_tasks, "engine", test_engine)
    task = IncidentAnalysisTask()
    task_id = "c" * 36
    task.request_stack = SimpleNamespace(top=SimpleNamespace(retries=3))
    error = OSError("temporary storage unavailable")
    task.on_failure(error, task_id, (), {}, None)
    task.on_failure(error, task_id, (), {}, None)

    with Session(test_engine) as session:
        dead_letters = session.exec(select(IncidentAnalysisDeadLetter)).all()
    assert len(dead_letters) == 1
    assert dead_letters[0].task_id == task_id
    assert dead_letters[0].attempt_number == 4
    assert dead_letters[0].error_message == "temporary storage unavailable"
    assert dead_letters[0].created_at is not None
import sys
from pathlib import Path
from uuid import uuid4

from datetime import datetime, timezone

from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from server import app
from services.api.telemetry.routes import get_db
from services.models import TelemetryEventRecord


engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
SQLModel.metadata.create_all(engine)


def get_test_db():
    with Session(engine) as session:
        yield session


app.dependency_overrides[get_db] = get_test_db
client = TestClient(app)


def test_telemetry_events_stores_valid_events_and_rejects_invalid_ones():
    payload = {
        "events": [
            {
                "eventId": str(uuid4()),
                "timestamp": "2026-09-01T10:00:00.000Z",
                "sessionId": str(uuid4()),
                "userId": "user-123",
                "event_type": "page_viewed",
                "schemaVersion": "1.0",
                "requestId": str(uuid4()),
                "properties": {"page_name": "/inventory", "private": "discard me"},
            },
            {
                "eventId": "invalid",
                "timestamp": "not-a-timestamp",
                "properties": {},
            }
        ]
    }

    response = client.post("/telemetry/events", json=payload)

    assert response.status_code == 200
    assert response.json() == {"received": 2, "stored": 1, "rejected": 1}

    with Session(engine) as session:
        stored = session.exec(select(TelemetryEventRecord)).all()

    assert len(stored) == 1
    assert stored[0].event_type == "page_viewed"
    assert stored[0].service == "backoffice"
    assert stored[0].tags == {"page_name": "/inventory"}


def test_telemetry_report_returns_operational_metrics():
    with Session(engine) as session:
        session.add_all(
            [
                TelemetryEventRecord(
                    timestamp=datetime(2026, 9, 1, 8, 0, tzinfo=timezone.utc),
                    service="backoffice",
                    event_type="page_viewed",
                    level="info",
                    value=None,
                    tags={"page_name": "/inventory"},
                ),
                TelemetryEventRecord(
                    timestamp=datetime(2026, 9, 1, 9, 0, tzinfo=timezone.utc),
                    service="backoffice",
                    event_type="login_failed",
                    level="error",
                    value=None,
                    tags={"failure_reason": "bad_password"},
                ),
                TelemetryEventRecord(
                    timestamp=datetime(2026, 9, 2, 10, 0, tzinfo=timezone.utc),
                    service="backoffice",
                    event_type="user_login_failed",
                    level="error",
                    value=None,
                    tags={"failure_reason": "bad_password"},
                ),
                TelemetryEventRecord(
                    timestamp=datetime(2026, 9, 2, 11, 0, tzinfo=timezone.utc),
                    service="backoffice",
                    event_type="user_login_succeeded",
                    level="info",
                    value=None,
                    tags={"login_method": "password"},
                ),
                TelemetryEventRecord(
                    timestamp=datetime(2026, 9, 2, 12, 0, tzinfo=timezone.utc),
                    service="backoffice",
                    event_type="api_error_returned",
                    level="error",
                    value=None,
                    tags={"endpoint": "/inventory/products", "http_status": 500},
                ),
                TelemetryEventRecord(
                    timestamp=datetime(2026, 9, 2, 13, 0, tzinfo=timezone.utc),
                    service="backoffice",
                    event_type="page_viewed",
                    level="info",
                    value=None,
                    tags={"page_name": "/inventory"},
                ),
            ]
        )
        session.commit()

    response = client.get(
        "/telemetry/report?start_date=2026-09-01T00:00:00Z&end_date=2026-09-03T00:00:00Z"
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["period"]["from"] == "2026-09-01T00:00:00Z"
    assert payload["period"]["to"] == "2026-09-03T00:00:00Z"
    metrics = payload["metrics"]
    assert any(item["date"] == "2026-09-01" for item in metrics["events_per_day"])
    assert any(item["event_type"] == "login_failed" for item in metrics["error_rate_by_type"])
    assert any(item["date"] == "2026-09-02" for item in metrics["auth_failure_rate"])
    assert metrics["auth_failure_rate"][0]["failure_rate"] > 0

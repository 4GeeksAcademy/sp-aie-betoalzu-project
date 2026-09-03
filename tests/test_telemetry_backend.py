import sys
from pathlib import Path
from uuid import uuid4

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

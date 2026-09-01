import sys
from pathlib import Path

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from server import app


client = TestClient(app)


def test_telemetry_events_receives_batch():
    payload = {
        "events": [
            {
                "eventId": "123e4567-e89b-42d3-a456-426614174000",
                "timestamp": "2026-09-01T10:00:00.000Z",
                "sessionId": "123e4567-e89b-42d3-a456-426614174001",
                "userId": "user-123",
                "event_type": "page_viewed",
                "schemaVersion": "1.0",
                "requestId": "123e4567-e89b-42d3-a456-426614174002",
                "properties": {"page": "/inventory"},
            }
        ]
    }

    response = client.post("/telemetry/events", json=payload)

    assert response.status_code == 200
    assert response.json() == {"received": 1}

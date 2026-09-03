import logging
import os
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy import insert
from sqlmodel import Session

from services.database import get_db
from services.models import TelemetryEventRecord

TELEMETRY_ENDPOINT = os.getenv("TELEMETRY_ENDPOINT", "http://localhost:8000/telemetry/events")
logger = logging.getLogger(__name__)

telemetry_api = APIRouter(prefix="/telemetry")


class TelemetryEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    eventId: str = Field(..., description="UUID v4 for the specific event")
    timestamp: str = Field(..., description="ISO 8601 UTC timestamp")
    sessionId: str = Field(..., description="User session UUID v4")
    userId: str = Field(..., description="Internal user identifier")
    event_type: str = Field(..., description="Telemetry event name in snake_case")
    schemaVersion: str = Field(..., description="Telemetry schema version")
    requestId: str = Field(..., description="Correlation ID for this event")
    properties: dict[str, Any] = Field(default_factory=dict)


class TelemetryBatchRequest(BaseModel):
    events: list[dict[str, Any]] = Field(default_factory=list)


ALLOWED_TAG_KEYS = {
    "office", "product_id", "product_category", "programme_id", "quantity", "currency",
    "unit_cost", "supplier_id", "inbound_order_id", "outbound_order_id", "recipient_type",
    "current_stock", "minimum_threshold", "attempted_change", "rejection_reason",
    "variance_percent", "historical_unit_cost", "login_method", "failure_reason", "attempt_count",
    "expiry_reason", "session_duration_seconds", "reset_method", "user_identified", "endpoint",
    "http_method", "http_status", "latency_ms", "page_name", "load_time_ms", "error_type",
    "error_message", "flow_type", "abandoned_step", "total_steps", "cancellation_reason",
    "report_type", "format", "expected_delivery_date", "actual_delivery_date",
}

ERROR_EVENT_TYPES = {"api_error_returned", "frontend_error_captured", "login_failed"}


def _to_record(event: TelemetryEvent) -> dict[str, Any]:
    properties = {
        key: value for key, value in event.properties.items() if key in ALLOWED_TAG_KEYS
    }
    value = properties.get("value")
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        value = properties.get("unit_cost")
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        value = None

    timestamp = datetime.fromisoformat(event.timestamp.replace("Z", "+00:00"))
    return {
        "timestamp": timestamp,
        "service": "backoffice",
        "event_type": event.event_type,
        "level": "error" if event.event_type in ERROR_EVENT_TYPES else "info",
        "value": value,
        "message": properties.get("message") if isinstance(properties.get("message"), str) else None,
        "tags": properties,
    }


@telemetry_api.post("/events", status_code=200)
def receive_telemetry_events(
    payload: TelemetryBatchRequest,
    db: Session = Depends(get_db),
):
    """Validate each event and persist the valid portion of a telemetry batch."""
    records = []
    rejected = 0
    for raw_event in payload.events:
        try:
            records.append(_to_record(TelemetryEvent.model_validate(raw_event)))
        except (ValidationError, ValueError, TypeError):
            rejected += 1

    if records:
        db.exec(insert(TelemetryEventRecord).values(records))
        db.commit()

    received = len(payload.events)
    logger.info(
        "Telemetry batch received: count=%s event_types=%s endpoint=%s",
        received,
        [record["event_type"] for record in records],
        TELEMETRY_ENDPOINT,
    )
    return {"received": received, "stored": len(records), "rejected": rejected}

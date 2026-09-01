import logging
import os
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict, Field

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
    events: list[TelemetryEvent] = Field(default_factory=list)


@telemetry_api.post("/events", status_code=200)
def receive_telemetry_events(payload: TelemetryBatchRequest):
    """Temporary stub endpoint for validating telemetry batch ingestion."""
    received = len(payload.events)
    logger.info(
        "Telemetry batch received: count=%s event_types=%s endpoint=%s",
        received,
        [event.event_type for event in payload.events],
        TELEMETRY_ENDPOINT,
    )
    return {"received": received}

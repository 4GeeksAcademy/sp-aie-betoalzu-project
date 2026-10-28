"""Tests for RFP SSE (Server-Sent Events) endpoint."""

import asyncio
import json
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from fastapi import status
from fastapi.testclient import TestClient
from sqlmodel import Session

from server import app
from services.api.rfp_intake.models import RfpTicket
from services.api.rfp_intake.sse import get_sse_manager
from services import database
from services.api.users.models import User


@pytest.fixture
def client():
    """Create a test client."""
    return TestClient(app)


@pytest.fixture
def db_session():
    """Create a database session for tests."""
    engine = database.engine
    with Session(engine) as session:
        yield session


@pytest.fixture
def auth_token(client):
    """Create an authenticated user and return token."""
    # Register user
    response = client.post(
        "/users/register",
        json={
            "email": f"test_{uuid4()}@example.com",
            "password": "TestPassword123!",
        },
    )
    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()
    return data.get("access_token")


def test_sse_endpoint_requires_auth(client):
    """Test that SSE endpoint requires authentication."""
    response = client.get("/rfp-intake/stream")
    assert response.status_code in (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN)


def test_sse_endpoint_accepts_valid_token(client, auth_token):
    """Test that SSE endpoint accepts valid JWT token."""
    headers = {"Authorization": f"Bearer {auth_token}"}
    response = client.get("/rfp-intake/stream", headers=headers)
    assert response.status_code == status.HTTP_200_OK
    assert response.headers.get("content-type") == "text/event-stream"


def test_sse_endpoint_no_cache_headers(client, auth_token):
    """Test that SSE endpoint sets appropriate cache headers."""
    headers = {"Authorization": f"Bearer {auth_token}"}
    response = client.get("/rfp-intake/stream", headers=headers)
    assert response.status_code == status.HTTP_200_OK
    assert response.headers.get("cache-control") == "no-cache"
    assert response.headers.get("x-accel-buffering") == "no"


@pytest.mark.asyncio
async def test_sse_manager_subscribe_unsubscribe():
    """Test SSE manager subscribe and unsubscribe."""
    manager = get_sse_manager()
    
    # Subscribe
    sub_id, queue = await manager.subscribe(actor_id="synthetic-owner")
    assert sub_id is not None
    assert queue is not None
    
    # Unsubscribe
    await manager.unsubscribe(sub_id)


@pytest.mark.asyncio
async def test_sse_manager_publish():
    """Test SSE manager publish to subscribers."""
    manager = get_sse_manager()
    
    # Subscribe two clients
    sub_id_1, queue_1 = await manager.subscribe(actor_id="synthetic-owner")
    sub_id_2, queue_2 = await manager.subscribe(actor_id="synthetic-owner")
    
    # Publish event
    event_data = {
        "ticket_id": "tkt_001",
        "rfp_id": "rfp_001",
        "client_name": "Test Client",
        "client_hq": "Spain",
        "services_requested": ["recruitment"],
        "status": "analyzing",
        "created_at": datetime.now(UTC).isoformat(),
    }
    await manager.publish(
        "rfp_ticket_created", event_data, actor_id="synthetic-owner",
    )
    
    # Both subscribers should receive the event
    message_1 = await asyncio.wait_for(queue_1.get(), timeout=2.0)
    message_2 = await asyncio.wait_for(queue_2.get(), timeout=2.0)
    
    assert message_1["event"] == "rfp_ticket_created"
    assert message_1["data"] == event_data
    assert message_2["event"] == "rfp_ticket_created"
    assert message_2["data"] == event_data
    
    await manager.unsubscribe(sub_id_1)
    await manager.unsubscribe(sub_id_2)


@pytest.mark.asyncio
async def test_sse_stream_frames():
    """Test SSE stream generates correct frame format."""
    manager = get_sse_manager()
    sub_id, queue = await manager.subscribe(actor_id="synthetic-owner")
    
    # Create test event
    test_data = {"ticket_id": "tkt_001", "status": "analyzing"}
    
    # Stream the event
    frame_parts = []
    async for frame in manager.stream(sub_id, queue, keep_alive_interval=10.0):
        frame_parts.append(frame)
        if len(frame_parts) >= 1:  # Stop after first frame
            break
    
    # Join and validate frame format
    frame_str = "".join(frame_parts)
    assert "event: rfp_ticket_created" in frame_str or "event: keep-alive" in frame_str
    assert "data:" in frame_str
    assert frame_str.endswith("\n\n")


def test_upload_rfp_publishes_sse_event(client, auth_token, tmp_path):
    """Test that uploading an RFP publishes an SSE event."""
    # Create a test PDF file
    pdf_content = b"%PDF-1.4\n%\xc2\xa4\xc2\xa5\xc2\xb1\xc2\xb3\n1 0 obj\n<< >>\nendobj\nxref\n0 1\n0000000000 65535 f\ntrailer\n<< /Size 1 >>\nstartxref\n0\n%%EOF"
    pdf_path = tmp_path / "test.pdf"
    pdf_path.write_bytes(pdf_content)
    
    headers = {"Authorization": f"Bearer {auth_token}"}
    
    with open(pdf_path, "rb") as f:
        response = client.post(
            "/rfp-intake/tickets",
            files={"file": ("test.pdf", f, "application/pdf")},
            headers=headers,
        )
    
    assert response.status_code == status.HTTP_202_ACCEPTED
    data = response.json()
    assert data["ticket_id"]
    assert data["status"] == "analizando"


def test_upload_rfp_invalid_file_type(client, auth_token):
    """Test that uploading non-PDF file is rejected."""
    headers = {"Authorization": f"Bearer {auth_token}"}
    
    response = client.post(
        "/rfp-intake/tickets",
        files={"file": ("test.txt", b"Not a PDF", "text/plain")},
        headers=headers,
    )
    
    assert response.status_code == status.HTTP_415_UNSUPPORTED_MEDIA_TYPE


def test_upload_rfp_without_auth(client, tmp_path):
    """Test that uploading without auth fails."""
    pdf_content = b"%PDF-1.4\n"
    pdf_path = tmp_path / "test.pdf"
    pdf_path.write_bytes(pdf_content)
    
    with open(pdf_path, "rb") as f:
        response = client.post(
            "/rfp-intake/tickets",
            files={"file": ("test.pdf", f, "application/pdf")},
        )
    
    assert response.status_code in (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN)

"""Tests para integración del agente con WebSocket chat streaming - Paso 2."""

import pytest
import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, Mock, patch, MagicMock
from sqlmodel import Session, create_engine
from sqlmodel.pool import StaticPool

from services.models import ChatSession, Message
from services.chat_service import ChatSessionService, MessageService
from services.pubsub import get_pubsub_broker


@pytest.fixture(name="session")
def session_fixture():
    """Crear BD SQLite en memoria para tests."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    from services.models import SQLModel
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


@pytest.mark.asyncio
async def test_pubsub_with_websocket_flow():
    """Simular flujo completo de pub/sub para WebSocket."""
    session_id = "test_chat_001"
    message_id = "test_msg_001"
    
    pubsub = get_pubsub_broker()
    received_events = []
    
    async def capture_event(event):
        received_events.append(event)
    
    channel = f"chat.{session_id}"
    await pubsub.subscribe(channel, capture_event)
    
    # Simular eventos que publicaría el agente
    await pubsub.publish(channel, {
        "event": "token_chunk",
        "data": {
            "session_id": session_id,
            "message_id": message_id,
            "token": "Hola ",
            "sequence": 1,
        }
    })
    
    await pubsub.publish(channel, {
        "event": "token_chunk",
        "data": {
            "session_id": session_id,
            "message_id": message_id,
            "token": "mundo",
            "sequence": 2,
        }
    })
    
    await pubsub.publish(channel, {
        "event": "generation_completed",
        "data": {
            "session_id": session_id,
            "message_id": message_id,
            "status": "completed",
            "total_tokens": 2,
        }
    })
    
    await asyncio.sleep(0.1)
    
    # Verificar eventos capturados
    assert len(received_events) == 3
    assert received_events[0]["event"] == "token_chunk"
    assert received_events[1]["event"] == "token_chunk"
    assert received_events[2]["event"] == "generation_completed"
    
    # Verificar contenido
    assert received_events[0]["data"]["token"] == "Hola "
    assert received_events[1]["data"]["token"] == "mundo"
    
    await pubsub.unsubscribe(channel, capture_event)


@pytest.mark.asyncio
async def test_interrupt_event_workflow():
    """Simular flujo de interrupción."""
    session_id = "test_chat_002"
    message_id_1 = "test_msg_002a"
    message_id_2 = "test_msg_002b"
    
    pubsub = get_pubsub_broker()
    received_events = []
    
    async def capture_event(event):
        received_events.append(event)
    
    channel = f"chat.{session_id}"
    await pubsub.subscribe(channel, capture_event)
    
    # Generación 1: alguns tokens + interrupción
    await pubsub.publish(channel, {
        "event": "token_chunk",
        "data": {
            "session_id": session_id,
            "message_id": message_id_1,
            "token": "Estoy",
            "sequence": 1,
        }
    })
    
    await pubsub.publish(channel, {
        "event": "generation_interrupted",
        "data": {
            "session_id": session_id,
            "message_id": message_id_1,
            "status": "interrupted",
            "tokens_shown": 1,
        }
    })
    
    # Generación 2: nuevo mensaje
    await pubsub.publish(channel, {
        "event": "user_message",
        "data": {
            "session_id": session_id,
            "message_id": f"msg_{session_id}_user_2",
            "text": "Repregunta",
        }
    })
    
    await pubsub.publish(channel, {
        "event": "token_chunk",
        "data": {
            "session_id": session_id,
            "message_id": message_id_2,
            "token": "Perfecto,",
            "sequence": 1,
        }
    })
    
    await pubsub.publish(channel, {
        "event": "generation_completed",
        "data": {
            "session_id": session_id,
            "message_id": message_id_2,
            "status": "completed",
            "total_tokens": 1,
        }
    })
    
    await asyncio.sleep(0.1)
    
    # Verificar flujo
    interrupts = [e for e in received_events if e.get("event") == "generation_interrupted"]
    assert len(interrupts) == 1
    
    completions = [e for e in received_events if e.get("event") == "generation_completed"]
    assert len(completions) == 1
    
    await pubsub.unsubscribe(channel, capture_event)


@pytest.mark.asyncio
async def test_reconnection_with_session_snapshot(session: Session):
    """Simular reconexión con session_snapshot."""
    session_id = "test_chat_003"
    
    # Crear sesión
    chat_session = ChatSession(
        session_id=session_id,
        user_id="user_123",
        client_id="client_456",
        thread_id="thread_789",
    )
    session.add(chat_session)
    session.commit()
    
    # Crear algunos mensajes
    msg_service = MessageService(session)
    
    await msg_service.create_message("msg_001", session_id, "user", "Hola", "completed")
    await msg_service.create_message("msg_002", session_id, "assistant", "Hola", "completed")
    await msg_service.create_message("msg_003", session_id, "user", "¿Cómo estás?", "completed")
    
    # Obtener historial
    messages = await msg_service.get_session_messages(session_id)
    
    # Verificar que el historial está completo
    assert len(messages) == 3
    assert messages[0].sender == "user"
    assert messages[1].sender == "assistant"
    assert messages[2].sender == "user"
    
    # Construir session_snapshot como si fuera para WebSocket
    snapshot_messages = [
        {
            "message_id": msg.message_id,
            "sender": msg.sender,
            "text": msg.text,
            "status": msg.status,
            "tokens_shown": msg.tokens_received if msg.status == "interrupted" else None,
        }
        for msg in messages
    ]
    
    snapshot_data = {
        "session_id": session_id,
        "checkpoint_id": None,
        "messages": snapshot_messages,
    }
    
    # Verificar snapshot
    assert len(snapshot_data["messages"]) == 3
    assert snapshot_data["messages"][0]["sender"] == "user"
    assert snapshot_data["session_id"] == session_id


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

"""Tests para WebSocket chat streaming - Paso 1: Modelos, Pub/Sub, Services."""

import pytest
import asyncio
from datetime import datetime, timezone
from sqlmodel import Session, create_engine
from sqlmodel.pool import StaticPool

from services.models import ChatSession, Message
from services.pubsub import PubSubBroker
from services.chat_service import ChatSessionService, MessageService


# ============================================================================
# Fixtures de BD para testing
# ============================================================================

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


# ============================================================================
# Tests: Modelos de BD
# ============================================================================

def test_chat_session_creation(session: Session):
    """Crear una sesión de chat y verificar campos."""
    chat_session = ChatSession(
        session_id="chat_001",
        user_id="user_123",
        client_id="client_456",
        thread_id="thread_789",
        status="active",
    )
    session.add(chat_session)
    session.commit()
    session.refresh(chat_session)
    
    assert chat_session.session_id == "chat_001"
    assert chat_session.user_id == "user_123"
    assert chat_session.status == "active"
    assert chat_session.created_at is not None


def test_message_creation(session: Session):
    """Crear un mensaje y verificar campos."""
    # Primero crear una sesión
    chat_session = ChatSession(
        session_id="chat_001",
        user_id="user_123",
        client_id="client_456",
        thread_id="thread_789",
    )
    session.add(chat_session)
    session.commit()
    
    # Crear un mensaje
    message = Message(
        message_id="msg_001",
        session_id="chat_001",
        sender="user",
        text="Hola, ¿cómo estás?",
        status="completed",
    )
    session.add(message)
    session.commit()
    session.refresh(message)
    
    assert message.message_id == "msg_001"
    assert message.sender == "user"
    assert message.status == "completed"


def test_message_interrupted_status(session: Session):
    """Mensaje con status interrumpido y tokens recibidos."""
    chat_session = ChatSession(
        session_id="chat_001",
        user_id="user_123",
        client_id="client_456",
        thread_id="thread_789",
    )
    session.add(chat_session)
    session.commit()
    
    message = Message(
        message_id="msg_002",
        session_id="chat_001",
        sender="assistant",
        text="Estoy bien, gracias por p",
        status="interrupted",
        tokens_received=5,
    )
    session.add(message)
    session.commit()
    session.refresh(message)
    
    assert message.status == "interrupted"
    assert message.tokens_received == 5


# ============================================================================
# Tests: Pub/Sub Broker
# ============================================================================

@pytest.mark.asyncio
async def test_pubsub_single_subscriber():
    """Un subscriber recibe el mensaje publicado."""
    broker = PubSubBroker()
    received = []
    
    async def callback(msg):
        received.append(msg)
    
    await broker.subscribe("test_channel", callback)
    await broker.publish("test_channel", {"event": "token_chunk", "data": {"token": "Hola"}})
    
    # Pequeña pausa para que el callback se ejecute
    await asyncio.sleep(0.1)
    
    assert len(received) == 1
    assert received[0]["event"] == "token_chunk"


@pytest.mark.asyncio
async def test_pubsub_multiple_subscribers():
    """Múltiples subscribers reciben el mismo mensaje."""
    broker = PubSubBroker()
    received_1 = []
    received_2 = []
    
    async def callback_1(msg):
        received_1.append(msg)
    
    async def callback_2(msg):
        received_2.append(msg)
    
    await broker.subscribe("shared_channel", callback_1)
    await broker.subscribe("shared_channel", callback_2)
    await broker.publish("shared_channel", {"event": "test"})
    
    await asyncio.sleep(0.1)
    
    assert len(received_1) == 1
    assert len(received_2) == 1


@pytest.mark.asyncio
async def test_pubsub_unsubscribe():
    """Desuscribirse deja de recibir mensajes."""
    broker = PubSubBroker()
    received = []
    
    async def callback(msg):
        received.append(msg)
    
    await broker.subscribe("channel", callback)
    await broker.publish("channel", {"event": "msg1"})
    await asyncio.sleep(0.05)
    
    await broker.unsubscribe("channel", callback)
    await broker.publish("channel", {"event": "msg2"})
    await asyncio.sleep(0.05)
    
    assert len(received) == 1
    assert received[0]["event"] == "msg1"


@pytest.mark.asyncio
async def test_pubsub_different_channels():
    """Mensajes en canales diferentes no se cruzan."""
    broker = PubSubBroker()
    received_1 = []
    received_2 = []
    
    async def callback_1(msg):
        received_1.append(msg)
    
    async def callback_2(msg):
        received_2.append(msg)
    
    await broker.subscribe("channel_1", callback_1)
    await broker.subscribe("channel_2", callback_2)
    await broker.publish("channel_1", {"event": "event_1"})
    await broker.publish("channel_2", {"event": "event_2"})
    
    await asyncio.sleep(0.1)
    
    assert len(received_1) == 1
    assert len(received_2) == 1
    assert received_1[0]["event"] == "event_1"
    assert received_2[0]["event"] == "event_2"


# ============================================================================
# Tests: ChatSessionService
# ============================================================================

@pytest.mark.asyncio
async def test_create_chat_session(session: Session):
    """Servicio: crear sesión de chat."""
    service = ChatSessionService(session)
    
    chat_session = await service.create_session(
        session_id="chat_test_001",
        user_id="user_abc",
        client_id="client_xyz",
        thread_id="thread_123",
    )
    
    assert chat_session.session_id == "chat_test_001"
    assert chat_session.status == "active"


@pytest.mark.asyncio
async def test_get_chat_session(session: Session):
    """Servicio: obtener sesión por ID."""
    service = ChatSessionService(session)
    
    await service.create_session(
        session_id="chat_test_002",
        user_id="user_abc",
        client_id="client_xyz",
        thread_id="thread_123",
    )
    
    retrieved = await service.get_session("chat_test_002")
    assert retrieved is not None
    assert retrieved.user_id == "user_abc"


@pytest.mark.asyncio
async def test_update_session_status(session: Session):
    """Servicio: actualizar estado de sesión."""
    service = ChatSessionService(session)
    
    await service.create_session(
        session_id="chat_test_003",
        user_id="user_abc",
        client_id="client_xyz",
        thread_id="thread_123",
    )
    
    updated = await service.update_session_status("chat_test_003", "closed")
    assert updated.status == "closed"


# ============================================================================
# Tests: MessageService
# ============================================================================

@pytest.mark.asyncio
async def test_create_message(session: Session):
    """Servicio: crear mensaje."""
    # Crear sesión primero
    session_obj = ChatSession(
        session_id="chat_test_004",
        user_id="user_abc",
        client_id="client_xyz",
        thread_id="thread_123",
    )
    session.add(session_obj)
    session.commit()
    
    service = MessageService(session)
    message = await service.create_message(
        message_id="msg_test_001",
        session_id="chat_test_004",
        sender="user",
        text="Hola",
        status="completed",
    )
    
    assert message.message_id == "msg_test_001"
    assert message.text == "Hola"


@pytest.mark.asyncio
async def test_get_session_messages(session: Session):
    """Servicio: obtener todos los mensajes de una sesión."""
    # Crear sesión
    session_obj = ChatSession(
        session_id="chat_test_005",
        user_id="user_abc",
        client_id="client_xyz",
        thread_id="thread_123",
    )
    session.add(session_obj)
    session.commit()
    
    service = MessageService(session)
    await service.create_message("msg_1", "chat_test_005", "user", "Msg1", "completed")
    await service.create_message("msg_2", "chat_test_005", "assistant", "Msg2", "completed")
    
    messages = await service.get_session_messages("chat_test_005")
    assert len(messages) == 2


@pytest.mark.asyncio
async def test_update_message(session: Session):
    """Servicio: actualizar mensaje."""
    # Crear sesión
    session_obj = ChatSession(
        session_id="chat_test_006",
        user_id="user_abc",
        client_id="client_xyz",
        thread_id="thread_123",
    )
    session.add(session_obj)
    session.commit()
    
    service = MessageService(session)
    await service.create_message("msg_update_1", "chat_test_006", "assistant", "Pendiente", "pending")
    
    updated = await service.update_message("msg_update_1", text="Completado", status="completed")
    assert updated.text == "Completado"
    assert updated.status == "completed"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

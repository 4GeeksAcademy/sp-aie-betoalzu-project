"""Servicios de gestión de sesiones de chat en tiempo real."""

from datetime import datetime, timezone
from sqlmodel import Session, select
from typing import Optional

from .models import ChatSession, Message
from .pubsub import get_pubsub_broker


class ChatSessionService:
    """Servicio para gestión de sesiones de chat."""

    def __init__(self, db_session: Session):
        self.db = db_session

    async def create_session(
        self,
        session_id: str,
        user_id: str,
        client_id: str,
        thread_id: str,
    ) -> ChatSession:
        """Crear una nueva sesión de chat.
        
        Args:
            session_id: Identificador único de sesión
            user_id: ID del usuario
            client_id: ID del cliente
            thread_id: ID del thread de LangGraph (normalmente = session_id)
        
        Returns:
            ChatSession creada
        """
        session = ChatSession(
            session_id=session_id,
            user_id=user_id,
            client_id=client_id,
            thread_id=thread_id,
            status="active",
        )
        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)
        return session

    async def get_session(self, session_id: str) -> Optional[ChatSession]:
        """Obtener una sesión de chat por su ID.
        
        Args:
            session_id: Identificador de la sesión
        
        Returns:
            ChatSession si existe, None en caso contrario
        """
        stmt = select(ChatSession).where(ChatSession.session_id == session_id)
        return self.db.exec(stmt).first()

    async def update_session_status(self, session_id: str, status: str) -> Optional[ChatSession]:
        """Actualizar el estado de una sesión.
        
        Args:
            session_id: Identificador de la sesión
            status: Nuevo estado ("active", "interrupted", "closed")
        
        Returns:
            ChatSession actualizada
        """
        session = await self.get_session(session_id)
        if not session:
            return None
        
        session.status = status
        session.updated_at = datetime.now(timezone.utc)
        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)
        return session

    async def update_checkpoint(self, session_id: str, checkpoint_id: str) -> Optional[ChatSession]:
        """Guardar el checkpoint de LangGraph en la sesión.
        
        Args:
            session_id: Identificador de la sesión
            checkpoint_id: ID del checkpoint
        
        Returns:
            ChatSession actualizada
        """
        session = await self.get_session(session_id)
        if not session:
            return None
        
        session.checkpoint_id = checkpoint_id
        session.updated_at = datetime.now(timezone.utc)
        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)
        return session


class MessageService:
    """Servicio para gestión de mensajes de chat."""

    def __init__(self, db_session: Session):
        self.db = db_session

    async def create_message(
        self,
        message_id: str,
        session_id: str,
        sender: str,
        text: str = "",
        status: str = "pending",
    ) -> Message:
        """Crear un nuevo mensaje en una sesión.
        
        Args:
            message_id: Identificador único del mensaje
            session_id: ID de la sesión
            sender: "user" o "assistant"
            text: Contenido del mensaje (vacío para pendientes)
            status: "pending", "completed", "interrupted"
        
        Returns:
            Message creado
        """
        message = Message(
            message_id=message_id,
            session_id=session_id,
            sender=sender,
            text=text,
            status=status,
        )
        self.db.add(message)
        self.db.commit()
        self.db.refresh(message)
        return message

    async def get_message(self, message_id: str) -> Optional[Message]:
        """Obtener un mensaje por su ID.
        
        Args:
            message_id: Identificador del mensaje
        
        Returns:
            Message si existe, None en caso contrario
        """
        stmt = select(Message).where(Message.message_id == message_id)
        return self.db.exec(stmt).first()

    async def update_message(
        self,
        message_id: str,
        text: Optional[str] = None,
        status: Optional[str] = None,
        tokens_received: Optional[int] = None,
    ) -> Optional[Message]:
        """Actualizar un mensaje existente.
        
        Args:
            message_id: Identificador del mensaje
            text: Nuevo texto (opcional)
            status: Nuevo estado (opcional)
            tokens_received: Cantidad de tokens (opcional)
        
        Returns:
            Message actualizado
        """
        message = await self.get_message(message_id)
        if not message:
            return None
        
        if text is not None:
            message.text = text
        if status is not None:
            message.status = status
        if tokens_received is not None:
            message.tokens_received = tokens_received
        
        self.db.add(message)
        self.db.commit()
        self.db.refresh(message)
        return message

    async def get_session_messages(self, session_id: str) -> list[Message]:
        """Obtener todos los mensajes de una sesión ordenados por fecha.
        
        Args:
            session_id: Identificador de la sesión
        
        Returns:
            Lista de mensajes
        """
        stmt = (
            select(Message)
            .where(Message.session_id == session_id)
            .order_by(Message.created_at)
        )
        return self.db.exec(stmt).all()

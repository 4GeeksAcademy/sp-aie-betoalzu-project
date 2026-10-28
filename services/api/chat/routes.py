"""WebSocket routes para el chat en tiempo real con streaming de tokens.

Endpoint: WebSocket /ws/chat/{session_id}
Autenticación: JWT en query param (?token=<JWT>) o en primer frame
"""

from fastapi import APIRouter, WebSocketDisconnect, Query, WebSocket, Depends, status
from fastapi.exceptions import WebSocketException
import json
import asyncio
from uuid import uuid4

from services.chat_service import ChatSessionService, MessageService
from services.pubsub import get_pubsub_broker
from services.database import get_session
from services.api.users.auth import verify_jwt_token
from services.agent_chat_service import invoke_agent_for_chat

chat_api = APIRouter()


async def authenticate_websocket(
    token: str = Query(None),
    first_frame: dict = None,
) -> dict:
    """Validar JWT desde query param o primer frame.
    
    Args:
        token: JWT en query string
        first_frame: Primer frame del WebSocket con posible token
    
    Returns:
        Dict con user_id, client_id si válido
    
    Raises:
        WebSocketException si inválido
    """
    jwt_token = token or (first_frame.get("token") if first_frame else None)
    
    if not jwt_token:
        raise WebSocketException(code=status.WS_1008_POLICY_VIOLATION, reason="Missing JWT")
    
    try:
        payload = verify_jwt_token(jwt_token)
        if not payload:
            raise WebSocketException(code=status.WS_1008_POLICY_VIOLATION, reason="Invalid JWT")
        
        user_id = payload.get("sub")
        client_id = payload.get("client_id")
        
        if not user_id or not client_id:
            raise WebSocketException(code=status.WS_1008_POLICY_VIOLATION, reason="Missing claims")
        
        return {"user_id": user_id, "client_id": client_id}
    except Exception as e:
        raise WebSocketException(code=status.WS_1008_POLICY_VIOLATION, reason=str(e))


@chat_api.websocket("/ws/chat/{session_id}")
async def websocket_chat(websocket: WebSocket, session_id: str, token: str = Query(None)):
    """WebSocket endpoint para streaming de chat en tiempo real.
    
    Protocolo:
    1. Cliente se conecta con JWT en query (?token=<JWT>)
    2. Backend valida JWT y autorización (user_id debe ser propietario de session_id)
    3. Si válido → Aceptar conexión, emitir session_snapshot
    4. Si inválido → Rechazar (403/401)
    
    Eventos del cliente:
    - user_message: {text, session_id}
    - interrupt_requested: {session_id, new_input}
    
    Eventos del servidor:
    - session_snapshot: {session_id, checkpoint_id, messages[]}
    - token_chunk: {session_id, message_id, token, sequence}
    - generation_completed: {session_id, message_id, status, total_tokens}
    - generation_interrupted: {session_id, message_id, status, tokens_shown}
    - user_message: {session_id, message_id, text}
    - error: {code, message}
    """
    
    # 1. Autenticar
    try:
        auth = await authenticate_websocket(token=token)
        user_id = auth["user_id"]
        client_id = auth["client_id"]
    except WebSocketException as e:
        await websocket.close(code=1008, reason=e.reason)
        return
    
    # 2. Aceptar conexión
    await websocket.accept()
    
    # 3. Obtener sesión de BD
    db = get_session()
    chat_service = ChatSessionService(db)
    message_service = MessageService(db)
    pubsub = get_pubsub_broker()
    
    session = await chat_service.get_session(session_id)
    
    if not session:
        await websocket.send_json({
            "event": "error",
            "data": {"code": 404, "message": f"Session {session_id} not found"}
        })
        await websocket.close(code=1000)
        return
    
    # 4. Validar autorización (user_id es propietario)
    if session.user_id != user_id or session.client_id != client_id:
        await websocket.send_json({
            "event": "error",
            "data": {"code": 403, "message": "Unauthorized: session does not belong to this user"}
        })
        await websocket.close(code=1008)
        return
    
    # 5. Cargar historial y emitir session_snapshot
    messages = await message_service.get_session_messages(session_id)
    
    snapshot_messages = []
    for msg in messages:
        snapshot_messages.append({
            "message_id": msg.message_id,
            "sender": msg.sender,
            "text": msg.text,
            "status": msg.status,
            "tokens_shown": msg.tokens_received if msg.status == "interrupted" else None,
        })
    
    await websocket.send_json({
        "event": "session_snapshot",
        "data": {
            "session_id": session_id,
            "checkpoint_id": session.checkpoint_id,
            "messages": snapshot_messages,
        }
    })
    
    # 6. Suscribirse al canal pub/sub
    channel = f"chat.{session_id}"
    
    async def handle_pubsub_message(message: dict):
        """Callback para eventos del pub/sub."""
        try:
            await websocket.send_json(message)
        except Exception:
            # Conexión cerrada o error de envío, ignorar
            pass
    
    await pubsub.subscribe(channel, handle_pubsub_message)
    
    # 7. Escuchar eventos del cliente
    current_generation_task: asyncio.Task | None = None  # Para rastrear y abortar si es necesario
    current_message_id: str | None = None
    
    try:
        while True:
            data = await websocket.receive_json()
            event = data.get("event")
            event_data = data.get("data", {})
            
            if event == "user_message":
                # Usuario envía un mensaje
                text = event_data.get("text", "").strip()
                if not text or len(text) > 10000:
                    await websocket.send_json({
                        "event": "error",
                        "data": {"code": 400, "message": "Invalid text length"}
                    })
                    continue
                
                # Crear mensaje de usuario
                user_message_id = f"msg_{uuid4().hex[:8]}"
                await message_service.create_message(
                    message_id=user_message_id,
                    session_id=session_id,
                    sender="user",
                    text=text,
                    status="completed",
                )
                
                # Notificar al pub/sub
                await pubsub.publish(channel, {
                    "event": "user_message",
                    "data": {
                        "session_id": session_id,
                        "message_id": user_message_id,
                        "text": text,
                    }
                })
                
                # Crear mensaje de asistente (pendiente)
                assistant_message_id = f"msg_{uuid4().hex[:8]}"
                await message_service.create_message(
                    message_id=assistant_message_id,
                    session_id=session_id,
                    sender="assistant",
                    text="",
                    status="pending",
                )
                
                current_message_id = assistant_message_id
                
                # Invocar el agente en background
                if current_generation_task and not current_generation_task.done():
                    current_generation_task.cancel()
                
                current_generation_task = asyncio.create_task(
                    invoke_agent_for_chat(
                        question=text,
                        session_id=session_id,
                        message_id=assistant_message_id,
                        user_id=user_id,
                        client_id=client_id,
                    )
                )
                
            elif event == "interrupt_requested":
                # Usuario quiere interrumpir la generación actual
                new_input = event_data.get("new_input", "").strip()
                if not new_input or len(new_input) > 10000:
                    await websocket.send_json({
                        "event": "error",
                        "data": {"code": 400, "message": "Invalid new_input"}
                    })
                    continue
                
                # Cancelar generación actual
                if current_generation_task and not current_generation_task.done():
                    current_generation_task.cancel()
                    try:
                        await current_generation_task
                    except asyncio.CancelledError:
                        pass
                
                # Emitir generación interrumpida
                if current_message_id:
                    await pubsub.publish(channel, {
                        "event": "generation_interrupted",
                        "data": {
                            "session_id": session_id,
                            "message_id": current_message_id,
                            "status": "interrupted",
                            "tokens_shown": 0,
                        }
                    })
                
                # Crear nuevo turno con new_input
                user_message_id = f"msg_{uuid4().hex[:8]}"
                await message_service.create_message(
                    message_id=user_message_id,
                    session_id=session_id,
                    sender="user",
                    text=new_input,
                    status="completed",
                )
                
                await pubsub.publish(channel, {
                    "event": "user_message",
                    "data": {
                        "session_id": session_id,
                        "message_id": user_message_id,
                        "text": new_input,
                    }
                })
                
                # Crear nuevo mensaje de asistente
                assistant_message_id = f"msg_{uuid4().hex[:8]}"
                await message_service.create_message(
                    message_id=assistant_message_id,
                    session_id=session_id,
                    sender="assistant",
                    text="",
                    status="pending",
                )
                
                current_message_id = assistant_message_id
                
                # Invocar agente con nuevo input
                current_generation_task = asyncio.create_task(
                    invoke_agent_for_chat(
                        question=new_input,
                        session_id=session_id,
                        message_id=assistant_message_id,
                        user_id=user_id,
                        client_id=client_id,
                    )
                )
    
    except WebSocketDisconnect:
        pass
    finally:
        # Cancelar generación en curso
        if current_generation_task and not current_generation_task.done():
            current_generation_task.cancel()
        
        # Desuscribirse al cerrar
        await pubsub.unsubscribe(channel, handle_pubsub_message)
        db.close()

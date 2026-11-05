"""Servicio de integración del agente de soporte con WebSocket streaming.

Maneja la invocación del agente con captura de eventos de token streaming.
"""

import asyncio
from typing import AsyncGenerator, Optional
from sqlmodel import Session

from services.agent.support import SupportAgent, get_support_agent
from services.pubsub import get_pubsub_broker
from services.chat_service import MessageService, ChatSessionService
from services.database import engine


async def stream_agent_response(
    agent: SupportAgent,
    question: str,
    session_id: str,
    message_id: str,
    conversation_id: Optional[str] = None,
    customer_id: Optional[str] = None,
    actor_id: str = "",
    actor_role: str = "",
) -> AsyncGenerator[dict, None]:
    """Ejecutar el agente y transmitir la respuesta terminada por fragmentos.
    
    Publicará eventos en el canal pub/sub chat.{session_id}:
    - token_chunk: cada token generado
    - generation_completed: cuando termina
    - generation_interrupted: si se cancela
    
    Args:
        agent: Instancia del SupportAgent
        question: Pregunta del usuario
        session_id: ID de la sesión de chat
        message_id: ID del mensaje que generará la respuesta
        conversation_id: ID de conversación (opcional, derivado del session_id)
        customer_id: ID del cliente (opcional)
        actor_id: ID del actor (usuario)
        actor_role: Rol del actor
        
    Yields:
        Eventos de token a medida que se generan
    """
    pubsub = get_pubsub_broker()
    channel = f"chat.{session_id}"
    
    conversation = conversation_id or session_id
    
    try:
        # Inicializar el contador de tokens
        token_count = 0
        # invoke conserva los controles del agente y su checkpoint sincronico.
        result = await asyncio.to_thread(
            agent.invoke,
            question,
            conversation_id=conversation,
            customer_id=customer_id,
            actor_id=actor_id,
            actor_role=actor_role,
        )
        if result.get("error"):
            raise RuntimeError(result["error"])
        answer = result.get("answer")
        if not isinstance(answer, str) or not answer.strip():
            raise RuntimeError("Support agent returned an empty answer")

        for offset in range(0, len(answer), 80):
            token = answer[offset:offset + 80]
            token_count += 1
            await pubsub.publish(channel, {
                "event": "token_chunk",
                "data": {
                    "session_id": session_id,
                    "message_id": message_id,
                    "token": token,
                    "sequence": token_count,
                }
            })
            yield {"type": "token", "content": token}

        await pubsub.publish(channel, {
            "event": "generation_completed",
            "data": {
                "session_id": session_id,
                "message_id": message_id,
                "status": "completed",
                "total_tokens": token_count,
            }
        })
            
    except asyncio.CancelledError:
        # Streaming cancelado por el usuario
        await pubsub.publish(channel, {
            "event": "generation_interrupted",
            "data": {
                "session_id": session_id,
                "message_id": message_id,
                "status": "interrupted",
                "tokens_shown": token_count,
            }
        })
        yield {"type": "interrupted"}
    except Exception as e:
        # Error durante el streaming
        await pubsub.publish(channel, {
            "event": "error",
            "data": {
                "code": 500,
                "message": f"Error generating response: {str(e)}",
            }
        })
        yield {"type": "error", "message": str(e)}


async def invoke_agent_for_chat(
    question: str,
    session_id: str,
    message_id: str,
    user_id: str,
    client_id: str,
    conversation_id: Optional[str] = None,
    customer_id: Optional[str] = None,
) -> None:
    """Invocar el agente y guardar la respuesta completa.
    
    Esta función:
    1. Obtiene el agente de soporte
    2. Invoca el agente con streaming
    3. Acumula la respuesta
    4. Guarda el mensaje completo en BD
    
    Args:
        question: Pregunta del usuario
        session_id: ID de la sesión
        message_id: ID del mensaje
        user_id: ID del usuario (del JWT)
        client_id: ID del cliente (del JWT)
        conversation_id: ID de conversación (opcional)
        customer_id: ID del cliente en el sistema (opcional)
    """
    agent = get_support_agent()
    
    with Session(engine) as db:
        message_service = MessageService(db)
        chat_service = ChatSessionService(db)
        
        try:
            # Acumular respuesta durante streaming
            full_response = ""
            
            async for event in stream_agent_response(
                agent,
                question,
                session_id,
                message_id,
                conversation_id=conversation_id,
                customer_id=customer_id,
                actor_id=user_id,
                actor_role="customer",
            ):
                if event.get("type") == "token":
                    full_response += event.get("content", "")
                elif event.get("type") == "interrupted":
                    # Marcar como interrumpido
                    await message_service.update_message(
                        message_id,
                        text=full_response,
                        status="interrupted",
                        tokens_received=len(full_response.split()),
                    )
                    return
                elif event.get("type") == "error":
                    # Guardar error
                    await message_service.update_message(
                        message_id,
                        text="",
                        status="pending",
                    )
                    return
            
            # Guardar respuesta completa
            await message_service.update_message(
                message_id,
                text=full_response,
                status="completed",
            )
            
            # Actualizar timestamp de sesión
            await chat_service.update_session_status(session_id, "active")
            
        except Exception as e:
            # Error no capturado
            await message_service.update_message(message_id, text="", status="pending")

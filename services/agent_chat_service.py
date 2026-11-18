"""Servicio de integración del agente de soporte con WebSocket streaming.

Maneja la invocación del agente con captura de eventos de token streaming real.
"""

import asyncio
from typing import AsyncGenerator, Optional
from sqlmodel import Session

from services.agent.support import SupportAgent, get_support_agent
from services.pubsub import get_pubsub_broker
from services.chat_service import MessageService, ChatSessionService
from services.database import engine
from data_project.pipelines.rag import generate_answer_stream, retrieve


async def stream_agent_response(
    agent: SupportAgent,
    question: str,
    session_id: str,
    message_id: str,
    conversation_id: Optional[str] = None,
    customer_id: Optional[str] = None,
    actor_id: str = "",
    actor_role: str = "",
    cancel_event: Optional[asyncio.Event] = None,
) -> AsyncGenerator[dict, None]:
    """Ejecutar el agente y transmitir tokens conforme se generan.
    
    Publica eventos en el canal pub/sub chat.{session_id}:
    - token_chunk: cada token generado en tiempo real
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
        cancel_event: asyncio.Event para señalar cancelación
        
    Yields:
        Eventos de token a medida que se generan
    """
    pubsub = get_pubsub_broker()
    channel = f"chat.{session_id}"
    
    conversation = conversation_id or session_id
    
    if cancel_event is None:
        cancel_event = asyncio.Event()
    
    try:
        # Inicializar el contador de tokens
        token_count = 0
        accumulated_text = ""
        
        # Recuperar contexto RAG
        context = await asyncio.to_thread(retrieve, question)
        
        # Generar respuesta con streaming real
        async for token in generate_answer_stream(question, context):
            # Verificar si se solicita cancelación
            if cancel_event.is_set():
                raise asyncio.CancelledError("Cancelado por el usuario")
            
            token_count += 1
            accumulated_text += token
            
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
        
        yield {"type": "completed", "total_tokens": token_count, "content": accumulated_text}
            
    except asyncio.CancelledError:
        # Streaming cancelado genuinamente
        await pubsub.publish(channel, {
            "event": "generation_interrupted",
            "data": {
                "session_id": session_id,
                "message_id": message_id,
                "status": "interrupted",
                "tokens_shown": token_count,
            }
        })
        yield {"type": "interrupted", "tokens_shown": token_count, "content": accumulated_text}
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
    cancel_event: Optional[asyncio.Event] = None,
) -> None:
    """Invocar el agente y guardar la respuesta.
    
    Esta función:
    1. Obtiene contexto RAG
    2. Transmite tokens conforme se generan
    3. Guarda el mensaje completo en BD
    4. Respeta cancelaciones genuinas
    
    Args:
        question: Pregunta del usuario
        session_id: ID de la sesión
        message_id: ID del mensaje
        user_id: ID del usuario (del JWT)
        client_id: ID del cliente (del JWT)
        conversation_id: ID de conversación (opcional)
        customer_id: ID del cliente en el sistema (opcional)
        cancel_event: asyncio.Event para señalar cancelación
    """
    if cancel_event is None:
        cancel_event = asyncio.Event()
    
    with Session(engine) as db:
        message_service = MessageService(db)
        chat_service = ChatSessionService(db)
        
        try:
            # Acumular respuesta durante streaming
            full_response = ""
            
            async for event in stream_agent_response(
                None,
                question,
                session_id,
                message_id,
                conversation_id=conversation_id,
                customer_id=customer_id,
                actor_id=user_id,
                actor_role="customer",
                cancel_event=cancel_event,
            ):
                if event.get("type") == "token":
                    full_response += event.get("content", "")
                elif event.get("type") == "completed":
                    # Respuesta completada con éxito
                    await message_service.update_message(
                        message_id,
                        text=full_response,
                        status="completed",
                    )
                    # Actualizar timestamp de sesión
                    await chat_service.update_session_status(session_id, "active")
                    return
                elif event.get("type") == "interrupted":
                    # Guardado genuino de respuesta parcial
                    await message_service.update_message(
                        message_id,
                        text=full_response,
                        status="interrupted",
                        tokens_received=len(full_response.split()),
                    )
                    return
                elif event.get("type") == "error":
                    # Guardar sin contenido en caso de error
                    await message_service.update_message(
                        message_id,
                        text="",
                        status="pending",
                    )
                    return
            
        except Exception as e:
            # Error no capturado
            await message_service.update_message(message_id, text="", status="pending")
